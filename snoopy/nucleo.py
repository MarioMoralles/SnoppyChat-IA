"""
Núcleo do Snoopy — Orquestrador principal
Coordena todos os módulos: Voz, IA, Automação, Memória
"""

import asyncio
from typing import Optional
from pathlib import Path

from .voz.ouvinte import Ouvinte
from .voz.sintetizador import Sintetizador
from .ia.processador import ProcessadorIA
from .ia.intencao import DetectorIntencao
from .automacao.gerenciador_tarefas import GerenciadorTarefas
from .memoria.gerenciador_memoria import GerenciadorMemoria
from .utils.logger import obter_logger
from .utils.config import Configuracao

logger = obter_logger("nucleo")


class Snoopy:
    """
    Classe principal que orquestra todos os componentes do assistente.
    """

    PALAVRA_ATIVACAO = "snoopy"

    def __init__(self, modo: str = "voz", sem_voz: bool = False):
        self.modo = modo
        self.sem_voz = sem_voz
        self.rodando = False
        self.config = Configuracao.carregar()

        # Componentes principais (inicializados em iniciar())
        self.ouvinte: Optional[Ouvinte] = None
        self.sintetizador: Optional[Sintetizador] = None
        self.processador_ia: Optional[ProcessadorIA] = None
        self.detector_intencao: Optional[DetectorIntencao] = None
        self.gerenciador_tarefas: Optional[GerenciadorTarefas] = None
        self.memoria: Optional[GerenciadorMemoria] = None

        # Contexto conversacional temporário (últimas N trocas)
        self._contexto_conversa = []
        self._max_contexto = self.config.get("max_contexto_conversa", 10)

    async def iniciar(self):
        """Inicializa todos os componentes e começa a escutar."""
        logger.info("Iniciando Snoopy...")

        # 1. Memória
        self.memoria = GerenciadorMemoria(self.config)
        await self.memoria.inicializar()
        logger.info("✅ Memória carregada")

        # 2. Processador de IA (Ollama/LM Studio)
        self.processador_ia = ProcessadorIA(self.config, self.memoria)
        await self.processador_ia.inicializar()
        logger.info("✅ Modelo de linguagem carregado")

        # 3. Detector de intenção
        self.detector_intencao = DetectorIntencao(self.config)
        logger.info("✅ Detector de intenção pronto")

        # 4. Gerenciador de tarefas em segundo plano
        self.gerenciador_tarefas = GerenciadorTarefas(
            processador_ia=self.processador_ia,
            callback_notificacao=self._notificar_conclusao
        )
        await self.gerenciador_tarefas.inicializar()
        logger.info("✅ Gerenciador de tarefas em segundo plano pronto")

        # 5. Síntese de voz
        if not self.sem_voz:
            self.sintetizador = Sintetizador(self.config)
            await self.sintetizador.inicializar()
            logger.info("✅ Sintetizador de voz pronto")

        # 6. Reconhecimento de voz
        if self.modo in ("voz", "ditado"):
            self.ouvinte = Ouvinte(
                config=self.config,
                palavra_ativacao=self.PALAVRA_ATIVACAO,
                callback=self._processar_entrada
            )
            await self.ouvinte.inicializar()
            # Conecta o ouvinte ao sintetizador para silenciar o mic durante a fala
            if self.sintetizador:
                self.sintetizador.ouvinte = self.ouvinte
            logger.info("✅ Ouvinte de voz pronto")

        self.rodando = True

        await self._falar(
            "Olá! Snoopy aqui. Pode falar comigo quando quiser — é só dizer meu nome."
        )

        logger.info(f"🐾 Snoopy está pronto no modo: {self.modo}")
        print(f"\n🐾 Snoopy está ouvindo... (modo: {self.modo})")
        print("   Diga 'Snoopy' + seu comando para ativar")
        print("   Ctrl+C para encerrar\n")

        await self._loop_principal()

    async def _loop_principal(self):
        """Loop principal de execução."""
        if self.modo == "texto":
            await self._loop_modo_texto()
        else:
            # Modo voz: o ouvinte chama o callback automaticamente
            while self.rodando:
                await asyncio.sleep(0.1)

    async def _loop_modo_texto(self):
        """Loop de entrada por texto no terminal."""
        print("💬 Modo texto ativo. Digite sua mensagem (ou 'sair' para encerrar):\n")
        loop = asyncio.get_event_loop()
        while self.rodando:
            try:
                texto = await loop.run_in_executor(
                    None, lambda: input("Você: ").strip()
                )
                if texto.lower() in ("sair", "exit", "quit"):
                    await self.encerrar()
                    break
                if texto:
                    await self._processar_entrada(texto)
            except (EOFError, KeyboardInterrupt):
                await self.encerrar()
                break

    async def _processar_entrada(self, texto: str):
        """
        Pipeline principal de processamento de uma entrada do usuário.
        1. Detecta intenção
        2. Verifica se é tarefa em segundo plano ou resposta imediata
        3. Processa e responde
        """
        if not texto.strip():
            return

        logger.info(f"Entrada recebida: '{texto}'")

        # Adiciona ao contexto conversacional
        self._adicionar_contexto("usuario", texto)

        # Detecta a intenção para decidir o fluxo
        intencao = await self.detector_intencao.detectar(texto, self._contexto_conversa)
        logger.debug(f"Intenção detectada: {intencao}")

        if intencao.get("tipo") == "tarefa_background":
            # Tarefa pesada que deve rodar em segundo plano
            descricao = intencao.get("descricao", texto)
            id_tarefa = await self.gerenciador_tarefas.agendar(
                descricao=descricao,
                contexto=self._contexto_conversa.copy()
            )
            resposta = (
                f"Certo! Estou processando isso em segundo plano. "
                f"Tarefa #{id_tarefa} iniciada. Vou te avisar quando terminar."
            )
            print(f"\n🐾 Snoopy: {resposta}\n")
            await self._falar(resposta)
        else:
            # Resposta imediata
            resposta = await self.processador_ia.processar(
                mensagem=texto,
                contexto=self._contexto_conversa,
                intencao=intencao
            )
            self._adicionar_contexto("assistente", resposta)
            print(f"\n🐾 Snoopy: {resposta}\n")
            await self._falar(resposta)

    async def _notificar_conclusao(self, id_tarefa: int, resultado: str):
        """Callback chamado quando uma tarefa em background termina."""
        mensagem = f"Snoopy aqui! A tarefa número {id_tarefa} foi concluída. {resultado}"
        logger.info(f"Tarefa #{id_tarefa} concluída")
        print(f"\n🔔 [Snoopy - Tarefa #{id_tarefa} concluída]: {resultado}\n")
        await self._falar(mensagem)
        # Salva o resultado na memória
        await self.memoria.salvar(
            conteudo=f"Tarefa #{id_tarefa} concluída: {resultado}",
            tipo="resultado_tarefa"
        )

    async def _falar(self, texto: str):
        """Fala um texto usando o sintetizador, se disponível."""
        if self.sintetizador and not self.sem_voz:
            await self.sintetizador.falar(texto)

    def _adicionar_contexto(self, papel: str, conteudo: str):
        """Adiciona uma mensagem ao contexto conversacional temporário."""
        self._contexto_conversa.append({
            "papel": papel,
            "conteudo": conteudo
        })
        # Mantém apenas as últimas N trocas
        if len(self._contexto_conversa) > self._max_contexto * 2:
            self._contexto_conversa = self._contexto_conversa[-(self._max_contexto * 2):]

    async def encerrar(self):
        """Encerra o assistente graciosamente."""
        if not self.rodando:
            return
        self.rodando = False
        logger.info("Encerrando Snoopy...")
        await self._falar("Até logo! Estarei aqui quando precisar.")

        if self.ouvinte:
            await self.ouvinte.parar()
        if self.gerenciador_tarefas:
            await self.gerenciador_tarefas.encerrar()
        if self.memoria:
            await self.memoria.fechar()

        logger.info("Snoopy encerrado com sucesso.")
        print("\n👋 Snoopy encerrado. Até logo!\n")