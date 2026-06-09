"""
Módulo de Escuta de Voz — Reescrito para robustez
Usa Whisper offline para reconhecimento de fala.
Arquitetura: thread de áudio → fila → thread de transcrição → asyncio seguro
"""

import asyncio
import queue
import threading
import re
import time
import numpy as np
from typing import Callable, Optional
from pathlib import Path

from ..utils.logger import obter_logger
from ..utils.config import Configuracao

logger = obter_logger("voz.ouvinte")

# Variações fonéticas de "Snoopy" que o Whisper costuma gerar em pt-BR
# (coletadas de testes reais com sotaque brasileiro)
VARIACOES_SNOOPY = [
    "snoopy", "snoop", "snoopi", "snopi", "snuppy",
    "znupi", "znuppi", "eznupi", "isnupi", "snupi",
    "snúpi", "snoppy", "snoppe", "znoop", "eznoop",
    "snoupie", "eznupy", "eznupe", "snupe", "snupe",
    "snupy", "esnoopy", "isnoop", "znupy", "snoupe",
]


def _detectar_ativacao(texto: str, variacoes: list) -> tuple:
    """
    Detecta se alguma variação da palavra de ativação está no texto.
    Retorna (encontrado: bool, posicao_fim: int)
    """
    texto_lower = texto.lower()
    melhor_pos = -1

    for variacao in variacoes:
        padrao = re.compile(r'\b' + re.escape(variacao) + r'\b', re.IGNORECASE)
        match = padrao.search(texto_lower)
        if match:
            # Pega a posição mais à esquerda encontrada
            if melhor_pos == -1 or match.end() < melhor_pos:
                melhor_pos = match.end()

    if melhor_pos > -1:
        return True, melhor_pos
    return False, -1


class Ouvinte:
    """
    Ouvinte de voz com pipeline robusto:
    sounddevice → fila_chunks → thread_deteccao_vad → thread_transcricao → asyncio
    """

    def __init__(
        self,
        config: Configuracao,
        palavra_ativacao: str,
        callback: Callable
    ):
        self.config = config
        self.palavra_ativacao = palavra_ativacao.lower()
        self.callback = callback
        self.ativo = False
        self.silenciado = False  # True enquanto o Snoopy está falando

        # Configurações de áudio
        self.taxa_amostragem = config.get("audio_taxa_amostragem", 16000)
        self.tamanho_chunk = config.get("audio_tamanho_chunk", 1024)
        self.limiar_silencio = config.get("audio_limiar_silencio", 0.015)
        self.duracao_silencio = config.get("audio_duracao_silencio_seg", 1.2)
        self.duracao_max_frase = config.get("audio_duracao_max_frase_seg", 12)
        self.duracao_min_frase = config.get("audio_duracao_min_frase_seg", 0.4)

        # Modelo Whisper
        self._tamanho_modelo = config.get("whisper_modelo", "base")
        self._idioma = config.get("whisper_idioma", "pt")
        self._modelo = None
        self._usar_whisper_padrao = False

        # Variações fonéticas para detecção flexível
        self._variacoes = VARIACOES_SNOOPY if self.palavra_ativacao == "snoopy" \
            else [self.palavra_ativacao]

        # Filas e threads
        self._fila_chunks: queue.Queue = queue.Queue()
        self._fila_segmentos: queue.Queue = queue.Queue()
        self._loop: Optional[asyncio.AbstractEventLoop] = None

    async def inicializar(self):
        """Carrega o modelo e inicia o pipeline."""
        self._loop = asyncio.get_running_loop()

        logger.info(f"Carregando Whisper '{self._tamanho_modelo}'...")
        await self._loop.run_in_executor(None, self._carregar_modelo)
        logger.info("Modelo Whisper pronto.")

        self.ativo = True
        self._iniciar_threads()

    def _carregar_modelo(self):
        try:
            from faster_whisper import WhisperModel
            cache = Path.home() / ".cache" / "snoopy" / "whisper"
            cache.mkdir(parents=True, exist_ok=True)
            self._modelo = WhisperModel(
                self._tamanho_modelo,
                device="cpu",
                compute_type="int8",
                download_root=str(cache)
            )
            logger.info("✅ faster-whisper carregado (CPU/int8)")
        except ImportError:
            try:
                import whisper  # type: ignore[import-untyped]
                self._modelo = whisper.load_model(self._tamanho_modelo)
                self._usar_whisper_padrao = True
                logger.info("✅ whisper padrão carregado")
            except ImportError:
                raise RuntimeError(
                    "Nenhum Whisper instalado.\n"
                    "Execute: pip install faster-whisper"
                )

    def _iniciar_threads(self):
        threading.Thread(
            target=self._thread_captura,
            daemon=True, name="snoopy-audio-captura"
        ).start()
        threading.Thread(
            target=self._thread_vad,
            daemon=True, name="snoopy-audio-vad"
        ).start()
        threading.Thread(
            target=self._thread_transcricao,
            daemon=True, name="snoopy-audio-transcricao"
        ).start()
        logger.info("🎙️  Ouvinte ativo. Aguardando 'Snoopy'...")

    # ------------------------------------------------------------------ #
    #  THREAD 1 — Captura contínua de áudio                               #
    # ------------------------------------------------------------------ #
    def _thread_captura(self):
        try:
            import sounddevice as sd

            def _cb(indata, frames, time_info, status):
                if self.ativo and not self.silenciado:
                    self._fila_chunks.put(indata.copy())

            with sd.InputStream(
                samplerate=self.taxa_amostragem,
                channels=1,
                dtype="float32",
                blocksize=self.tamanho_chunk,
                callback=_cb
            ):
                while self.ativo:
                    time.sleep(0.05)
        except Exception as e:
            logger.error(f"Erro na captura de áudio: {e}")

    # ------------------------------------------------------------------ #
    #  THREAD 2 — VAD simples: agrupa chunks em segmentos de fala         #
    # ------------------------------------------------------------------ #
    def _thread_vad(self):
        buffer = []
        ultimo_som = time.time()
        gravando = False

        while self.ativo:
            try:
                chunk = self._fila_chunks.get(timeout=0.1)
            except queue.Empty:
                # Verifica timeout de silêncio mesmo sem novos chunks
                if gravando and (time.time() - ultimo_som) > self.duracao_silencio:
                    gravando = False
                    duracao = len(buffer) * self.tamanho_chunk / self.taxa_amostragem
                    if duracao >= self.duracao_min_frase:
                        self._fila_segmentos.put(list(buffer))
                    buffer = []
                continue

            nivel = float(np.abs(chunk).mean())

            if nivel > self.limiar_silencio:
                ultimo_som = time.time()
                if not gravando:
                    gravando = True
                    buffer = []
                    logger.debug("🔴 Fala detectada")

            if gravando:
                buffer.append(chunk)
                duracao = len(buffer) * self.tamanho_chunk / self.taxa_amostragem

                silencio = (time.time() - ultimo_som) > self.duracao_silencio
                muito_longo = duracao > self.duracao_max_frase

                if silencio or muito_longo:
                    gravando = False
                    logger.debug(f"⏹️  Segmento: {duracao:.1f}s")
                    if duracao >= self.duracao_min_frase:
                        self._fila_segmentos.put(list(buffer))
                    buffer = []

    # ------------------------------------------------------------------ #
    #  THREAD 3 — Transcrição e detecção da palavra de ativação           #
    # ------------------------------------------------------------------ #
    def _thread_transcricao(self):
        while self.ativo:
            try:
                segmento = self._fila_segmentos.get(timeout=0.5)
            except queue.Empty:
                continue

            try:
                audio_np = np.concatenate(segmento, axis=0).flatten()
                texto = self._transcrever(audio_np)

                if not texto:
                    continue

                logger.info(f"📝 Transcrito: '{texto}'")

                ativado, pos_fim = _detectar_ativacao(texto, self._variacoes)

                if not ativado:
                    logger.debug("Palavra de ativação não detectada.")
                    continue

                # Extrai o comando — tudo depois da palavra de ativação
                comando = texto[pos_fim:].strip()
                comando = re.sub(r'^[\s,\.!?:;\-]+', '', comando).strip()

                # Remove ocorrências extras da palavra de ativação no comando
                for v in self._variacoes:
                    comando = re.sub(
                        r'\b' + re.escape(v) + r'\b', '', comando,
                        flags=re.IGNORECASE
                    ).strip()

                comando = re.sub(r'\s{2,}', ' ', comando).strip()

                if len(comando) > 2:
                    logger.info(f"✅ Comando: '{comando}'")
                    asyncio.run_coroutine_threadsafe(
                        self.callback(comando), self._loop
                    )
                else:
                    logger.info("Ativação sem comando — cumprimentando")
                    asyncio.run_coroutine_threadsafe(
                        self.callback("olá"), self._loop
                    )

            except Exception as e:
                logger.error(f"Erro na transcrição/detecção: {e}", exc_info=True)

    def _transcrever(self, audio_np: np.ndarray) -> str:
        if self._modelo is None:
            return ""
        try:
            if not self._usar_whisper_padrao:
                segs, _ = self._modelo.transcribe(
                    audio_np,
                    language=self._idioma,
                    beam_size=5,
                    vad_filter=True,
                    vad_parameters={"min_silence_duration_ms": 300},
                    initial_prompt="Snoopy"   # dica para o modelo
                )
                return " ".join(s.text for s in segs).strip()
            else:
                import whisper  # type: ignore[import-untyped]
                r = self._modelo.transcribe(
                    audio_np, language=self._idioma, fp16=False,
                    initial_prompt="Snoopy"
                )
                return r["text"].strip()
        except Exception as e:
            logger.error(f"Erro no Whisper: {e}")
            return ""

    async def parar(self):
        self.ativo = False
        logger.info("Ouvinte parado.")
