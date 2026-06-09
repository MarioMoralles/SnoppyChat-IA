"""
Núcleo do Snoopy — Orquestrador principal (versão completa)
Integra: Voz, Wake Word, IA, Ferramentas, Imagens, Memória, Obsidian,
Embeddings, Proatividade e Interface Gráfica.
"""

import asyncio
import base64
import tempfile
from pathlib import Path
from typing import Optional

from .voz.ouvinte import Ouvinte
from .voz.sintetizador import Sintetizador
from .ia.processador import ProcessadorIA
from .ia.intencao import DetectorIntencao
from .ia.proatividade import MotorProatividade
from .automacao.gerenciador_tarefas import GerenciadorTarefas
from .automacao.ferramentas import CaixaDeFerramentas
from .automacao.gerador_imagens import GeradorImagens
from .memoria.gerenciador_memoria import GerenciadorMemoria
from .memoria.embeddings import MotorEmbeddings
from .memoria.obsidian import CofreObsidian
from .utils.logger import obter_logger
from .utils.config import Configuracao

logger = obter_logger("nucleo")


class Snoopy:
    PALAVRA_ATIVACAO = "snoopy"

    def __init__(self, modo: str = "voz", sem_voz: bool = False):
        self.modo = modo
        self.sem_voz = sem_voz
        self.rodando = False
        self.config = Configuracao.carregar()

        self.ouvinte: Optional[Ouvinte] = None
        self.sintetizador: Optional[Sintetizador] = None
        self.processador_ia: Optional[ProcessadorIA] = None
        self.detector_intencao: Optional[DetectorIntencao] = None
        self.gerenciador_tarefas: Optional[GerenciadorTarefas] = None
        self.memoria: Optional[GerenciadorMemoria] = None
        self.embeddings: Optional[MotorEmbeddings] = None
        self.obsidian: Optional[CofreObsidian] = None
        self.ferramentas: Optional[CaixaDeFerramentas] = None
        self.gerador_imagens: Optional[GeradorImagens] = None
        self.proatividade: Optional[MotorProatividade] = None
        self.servidor: Optional[object] = None

        self._contexto_conversa = []
        self._max_contexto = self.config.get("max_contexto_conversa", 10)

    async def iniciar(self):
        logger.info("Iniciando Snoopy...")

        # Memória base
        self.memoria = GerenciadorMemoria(self.config)
        await self.memoria.inicializar()
        logger.info("✅ Memória carregada")

        # Memória semântica (embeddings)
        self.embeddings = MotorEmbeddings(self.config)
        await self.embeddings.inicializar()

        # Obsidian
        self.obsidian = CofreObsidian(self.config)
        await self.obsidian.inicializar()

        # Ferramentas (controle da máquina)
        self.ferramentas = CaixaDeFerramentas()

        # Gerador de imagens
        self.gerador_imagens = GeradorImagens(self.config)
        await self.gerador_imagens.inicializar()
        # Registra ferramenta de geração de imagem se disponível
        if self.gerador_imagens.disponivel:
            self.ferramentas.registrar(
                "gerar_imagem",
                "Gera uma imagem a partir de uma descrição em texto.",
                {"descricao": "string - o que desenhar"},
                lambda descricao: self._wrap_gerar_imagem(descricao)
            )

        # Proatividade
        self.proatividade = MotorProatividade(self.config)

        # Processador de IA (com tudo integrado)
        self.processador_ia = ProcessadorIA(
            self.config, self.memoria,
            caixa_ferramentas=self.ferramentas,
            embeddings=self.embeddings,
            proatividade=self.proatividade,
        )
        await self.processador_ia.inicializar()
        logger.info("✅ Modelo de linguagem carregado")

        # Detector de intenção
        self.detector_intencao = DetectorIntencao(self.config)
        logger.info("✅ Detector de intenção pronto")

        # Tarefas em segundo plano
        self.gerenciador_tarefas = GerenciadorTarefas(
            processador_ia=self.processador_ia,
            callback_notificacao=self._notificar_conclusao
        )
        await self.gerenciador_tarefas.inicializar()
        logger.info("✅ Gerenciador de tarefas pronto")

        # Síntese de voz
        if not self.sem_voz:
            self.sintetizador = Sintetizador(self.config)
            await self.sintetizador.inicializar()
            logger.info("✅ Sintetizador de voz pronto")

        # Voz / wake word (só nos modos de voz)
        if self.modo in ("voz", "ditado"):
            self.ouvinte = Ouvinte(
                config=self.config,
                palavra_ativacao=self.PALAVRA_ATIVACAO,
                callback=self._processar_entrada
            )
            await self.ouvinte.inicializar()
            if self.sintetizador:
                self.sintetizador.ouvinte = self.ouvinte
            logger.info("✅ Ouvinte de voz pronto")

        self.rodando = True
        await self._falar("Olá! Snoopy aqui, pronto pra ajudar.")
        logger.info(f"🐾 Snoopy pronto no modo: {self.modo}")

        if self.modo == "interface":
            await self._iniciar_interface()
        else:
            print(f"\n🐾 Snoopy está ativo (modo: {self.modo})")
            print("   Ctrl+C para encerrar\n")
            await self._loop_principal()

    async def _wrap_gerar_imagem(self, descricao: str) -> str:
        caminho = await self.gerador_imagens.gerar(descricao)
        return f"Imagem gerada e salva em: {caminho}"

    async def _iniciar_interface(self):
        from .interface.servidor import ServidorInterface
        porta = self.config.get("interface_porta", 8000)
        self.servidor = ServidorInterface(self, porta=porta)
        await self.servidor.iniciar()

    async def _loop_principal(self):
        if self.modo == "texto":
            await self._loop_modo_texto()
        else:
            while self.rodando:
                await asyncio.sleep(0.1)

    async def _loop_modo_texto(self):
        print("💬 Modo texto. Digite (ou 'sair'):\n")
        loop = asyncio.get_event_loop()
        while self.rodando:
            try:
                texto = await loop.run_in_executor(None, lambda: input("Você: ").strip())
                if texto.lower() in ("sair", "exit", "quit"):
                    await self.encerrar()
                    break
                if texto:
                    await self._processar_entrada(texto)
            except (EOFError, KeyboardInterrupt):
                await self.encerrar()
                break

    async def _processar_entrada(self, texto: str):
        if not texto.strip():
            return
        logger.info(f"Entrada recebida: '{texto}'")
        try:
            self._adicionar_contexto("usuario", texto)
            intencao = await self.detector_intencao.detectar(texto, self._contexto_conversa)
            logger.info(f"Intenção: {intencao.get('tipo')}")

            if intencao.get("tipo") == "tarefa_background":
                descricao = intencao.get("descricao", texto)
                id_tarefa = await self.gerenciador_tarefas.agendar(
                    descricao=descricao, contexto=self._contexto_conversa.copy()
                )
                resposta = (f"Certo! Processando em segundo plano. "
                            f"Tarefa número {id_tarefa} iniciada. Aviso quando terminar.")
                print(f"\n🐾 Snoopy: {resposta}\n")
                await self._falar(resposta)
            else:
                resposta = await self.processador_ia.processar(
                    mensagem=texto, contexto=self._contexto_conversa, intencao=intencao
                )
                self._adicionar_contexto("assistente", resposta)
                print(f"\n🐾 Snoopy: {resposta}\n")
                await self._falar(resposta)
                # Registra no Obsidian
                if self.obsidian and self.obsidian.ativo:
                    await self.obsidian.registrar_conversa(texto, resposta)
        except Exception as e:
            logger.error(f"ERRO ao processar: {e}", exc_info=True)
            await self._falar("Desculpe, tive um problema ao processar isso.")

    # ---- Métodos usados pela INTERFACE GRÁFICA ---- #
    async def processar_para_interface(self, texto: str) -> str:
        """Processa texto da interface e retorna a resposta (sem falar via TTS local)."""
        if not texto.strip():
            return ""
        self._adicionar_contexto("usuario", texto)
        intencao = await self.detector_intencao.detectar(texto, self._contexto_conversa)

        if intencao.get("tipo") == "tarefa_background":
            id_t = await self.gerenciador_tarefas.agendar(
                descricao=intencao.get("descricao", texto),
                contexto=self._contexto_conversa.copy()
            )
            return f"Processando em segundo plano (tarefa #{id_t}). Aviso quando terminar."

        resposta = await self.processador_ia.processar(
            mensagem=texto, contexto=self._contexto_conversa, intencao=intencao
        )
        self._adicionar_contexto("assistente", resposta)
        if self.obsidian and self.obsidian.ativo:
            await self.obsidian.registrar_conversa(texto, resposta)
        return resposta

    async def transcrever_audio_interface(self, audio_b64: str) -> str:
        """Transcreve áudio (base64) vindo do navegador usando o Whisper."""
        try:
            audio_bytes = base64.b64decode(audio_b64)
            with tempfile.NamedTemporaryFile(suffix=".webm", delete=False) as f:
                f.write(audio_bytes)
                caminho = f.name
            # Usa o modelo Whisper já carregado no ouvinte, ou cria um temporário
            import numpy as np
            try:
                from faster_whisper import WhisperModel
                modelo = WhisperModel(
                    self.config.get("whisper_modelo", "base"),
                    device="cpu", compute_type="int8"
                )
                segmentos, _ = modelo.transcribe(caminho, language="pt")
                texto = " ".join(s.text for s in segmentos).strip()
                Path(caminho).unlink(missing_ok=True)
                return texto
            except Exception as e:
                logger.error(f"Erro ao transcrever áudio da interface: {e}")
                return ""
        except Exception as e:
            logger.error(f"Erro ao decodificar áudio: {e}")
            return ""

    async def _notificar_conclusao(self, id_tarefa: int, resultado: str):
        mensagem = f"Snoopy aqui! Tarefa {id_tarefa} concluída. {resultado}"
        logger.info(f"Tarefa #{id_tarefa} concluída")
        print(f"\n🔔 [Tarefa #{id_tarefa}]: {resultado}\n")
        await self._falar(mensagem)
        await self.memoria.salvar(
            conteudo=f"Tarefa #{id_tarefa}: {resultado}", tipo="resultado_tarefa"
        )
        if self.servidor:
            await self.servidor.transmitir({
                "tipo": "resposta",
                "conteudo": f"✅ Tarefa #{id_tarefa} concluída: {resultado}"
            })

    async def _falar(self, texto: str):
        if self.sintetizador and not self.sem_voz:
            await self.sintetizador.falar(texto)

    def _adicionar_contexto(self, papel: str, conteudo: str):
        self._contexto_conversa.append({"papel": papel, "conteudo": conteudo})
        if len(self._contexto_conversa) > self._max_contexto * 2:
            self._contexto_conversa = self._contexto_conversa[-(self._max_contexto * 2):]

    async def encerrar(self):
        if not self.rodando:
            return
        self.rodando = False
        logger.info("Encerrando Snoopy...")
        await self._falar("Até logo!")
        if self.ouvinte:
            await self.ouvinte.parar()
        if self.gerenciador_tarefas:
            await self.gerenciador_tarefas.encerrar()
        if self.memoria:
            await self.memoria.fechar()
        if self.processador_ia:
            await self.processador_ia.fechar()
        logger.info("Snoopy encerrado.")
        print("\n👋 Snoopy encerrado. Até logo!\n")
