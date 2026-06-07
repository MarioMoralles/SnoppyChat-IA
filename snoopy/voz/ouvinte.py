"""
Módulo de Escuta de Voz
Usa Whisper (offline) para reconhecimento de fala.
Detecta a palavra de ativação 'Snoopy' em qualquer parte da frase.
"""

import asyncio
import queue
import threading
import numpy as np
from typing import Callable, Optional
from pathlib import Path

from ..utils.logger import obter_logger
from ..utils.config import Configuracao

logger = obter_logger("voz.ouvinte")


class Ouvinte:
    """
    Ouvinte de voz contínuo com detecção de palavra de ativação.
    
    Usa:
    - faster-whisper (versão otimizada do Whisper) para transcrição offline
    - sounddevice para captura de áudio
    - Detecção de silêncio para segmentar frases
    """

    def __init__(
        self,
        config: Configuracao,
        palavra_ativacao: str,
        callback: Callable[[str], None]
    ):
        self.config = config
        self.palavra_ativacao = palavra_ativacao.lower()
        self.callback = callback
        self.ativo = False

        # Configurações de áudio
        self.taxa_amostragem = config.get("audio_taxa_amostragem", 16000)
        self.tamanho_chunk = config.get("audio_tamanho_chunk", 1024)
        self.limiar_silencio = config.get("audio_limiar_silencio", 0.01)
        self.duracao_silencio = config.get("audio_duracao_silencio_seg", 1.5)
        self.duracao_max_frase = config.get("audio_duracao_max_frase_seg", 15)

        # Modelo Whisper
        self.modelo_whisper_tamanho = config.get("whisper_modelo", "base")
        self.modelo_whisper_idioma = config.get("whisper_idioma", "pt")
        self._modelo = None

        self._fila_audio = queue.Queue()
        self._thread_escuta: Optional[threading.Thread] = None
        self._thread_processamento: Optional[threading.Thread] = None
        # Referência ao loop principal — capturada em inicializar() e usada nas threads
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        # Flag para silenciar a captura enquanto o Snoopy está falando (evita eco)
        self.silenciado = False

    async def inicializar(self):
        """Carrega o modelo Whisper e inicia a captura de áudio."""
        # Captura o loop do asyncio AQUI, enquanto ainda estamos na corrotina principal.
        # As threads secundárias não têm event loop próprio, então precisam desta referência.
        self._loop = asyncio.get_running_loop()

        logger.info(
            f"Carregando Whisper ({self.modelo_whisper_tamanho})... "
            "Isso pode levar alguns segundos na primeira vez."
        )
        await self._loop.run_in_executor(None, self._carregar_modelo_whisper)
        logger.info("Modelo Whisper carregado.")
        self.ativo = True
        self._iniciar_threads()

    def _carregar_modelo_whisper(self):
        """Carrega o modelo faster-whisper localmente."""
        try:
            from faster_whisper import WhisperModel
            caminho_modelos = Path.home() / ".cache" / "snoopy" / "whisper"
            caminho_modelos.mkdir(parents=True, exist_ok=True)
            self._modelo = WhisperModel(
                self.modelo_whisper_tamanho,
                device="cpu",
                compute_type="int8",
                download_root=str(caminho_modelos)
            )
            logger.info("✅ faster-whisper carregado (CPU, int8)")
        except ImportError:
            logger.warning(
                "faster-whisper não encontrado. "
                "Tentando whisper padrão..."
            )
            self._carregar_whisper_padrao()

    def _carregar_whisper_padrao(self):
        """Fallback para o Whisper original da OpenAI (offline)."""
        try:
            import whisper
            self._modelo = whisper.load_model(self.modelo_whisper_tamanho)
            self._usar_whisper_padrao = True
            logger.info("✅ Whisper padrão carregado")
        except ImportError:
            raise RuntimeError(
                "Nenhum modelo Whisper encontrado.\n"
                "Instale: pip install faster-whisper\n"
                "ou:       pip install openai-whisper"
            )

    def _iniciar_threads(self):
        """Inicia as threads de captura e processamento de áudio."""
        self._thread_escuta = threading.Thread(
            target=self._loop_captura_audio,
            daemon=True,
            name="snoopy-captura-audio"
        )
        self._thread_processamento = threading.Thread(
            target=self._loop_processamento_audio,
            daemon=True,
            name="snoopy-processamento-audio"
        )
        self._thread_escuta.start()
        self._thread_processamento.start()
        logger.info("🎙️  Ouvinte ativo. Aguardando 'Snoopy'...")

    def _loop_captura_audio(self):
        """Loop de captura contínua de áudio do microfone."""
        try:
            import sounddevice as sd

            def callback_audio(indata, frames, time_info, status):
                if status:
                    logger.debug(f"Status de áudio: {status}")
                # Ignora áudio enquanto o Snoopy está falando (evita eco da própria voz)
                if self.ativo and not self.silenciado:
                    self._fila_audio.put(indata.copy())

            with sd.InputStream(
                samplerate=self.taxa_amostragem,
                channels=1,
                dtype="float32",
                blocksize=self.tamanho_chunk,
                callback=callback_audio
            ):
                while self.ativo:
                    import time
                    time.sleep(0.1)

        except ImportError:
            logger.error(
                "sounddevice não instalado. "
                "Execute: pip install sounddevice"
            )
        except Exception as e:
            logger.error(f"Erro na captura de áudio: {e}")

    def _loop_processamento_audio(self):
        """
        Coleta chunks de áudio, detecta segmentos de fala
        e transcreve com Whisper.
        """
        import time

        buffer_audio = []
        ultimo_som = time.time()
        gravando = False

        while self.ativo:
            try:
                chunk = self._fila_audio.get(timeout=0.1)
                nivel = float(np.abs(chunk).mean())

                if nivel > self.limiar_silencio:
                    ultimo_som = time.time()
                    if not gravando:
                        gravando = True
                        buffer_audio = []
                        logger.debug("🔴 Início de fala detectado")

                if gravando:
                    buffer_audio.append(chunk)
                    duracao_gravada = (
                        len(buffer_audio) * self.tamanho_chunk / self.taxa_amostragem
                    )

                    silencio_detectado = (
                        time.time() - ultimo_som > self.duracao_silencio
                    )
                    duracao_maxima = duracao_gravada > self.duracao_max_frase

                    if silencio_detectado or duracao_maxima:
                        gravando = False
                        logger.debug("⏹️  Fim de fala detectado")
                        if len(buffer_audio) > 5:  # Ignora segmentos muito curtos
                            self._transcrever_e_processar(buffer_audio)
                        buffer_audio = []

            except queue.Empty:
                continue
            except Exception as e:
                logger.error(f"Erro no processamento de áudio: {e}")

    def _transcrever_e_processar(self, buffer_audio: list):
        """Transcreve o áudio capturado e verifica a palavra de ativação."""
        try:
            audio_np = np.concatenate(buffer_audio, axis=0).flatten()
            texto = self._transcrever(audio_np)

            if not texto:
                return

            texto_limpo = texto.strip()
            logger.info(f"Transcrito: '{texto_limpo}'")

            texto_lower = texto_limpo.lower()

            # Verifica se a palavra de ativação está presente
            if self.palavra_ativacao not in texto_lower:
                return

            # Extrai o comando preservando caixa original para melhor compreensão
            # Encontra a posição da palavra de ativação (insensível a maiúsculas)
            import re
            padrao = re.compile(re.escape(self.palavra_ativacao), re.IGNORECASE)
            match = padrao.search(texto_limpo)

            if match:
                # Tudo após a palavra de ativação é o comando
                comando = texto_limpo[match.end():].strip()
                # Remove vírgulas e pontuação inicial
                comando = re.sub(r'^[\s,\.!?:;]+', '', comando).strip()
            else:
                comando = ""

            # Remove o nome caso tenha aparecido no meio ou no final também
            comando = padrao.sub("", comando).strip()

            if len(comando) > 2:
                logger.info(f"✅ Comando final: '{comando}'")
                asyncio.run_coroutine_threadsafe(
                    self.callback(comando),
                    self._loop
                )
            else:
                # Só o nome foi dito sem comando — cumprimenta
                logger.info("Palavra de ativação detectada sem comando — cumprimentando")
                asyncio.run_coroutine_threadsafe(
                    self.callback("olá"),
                    self._loop
                )

        except Exception as e:
            logger.error(f"Erro na transcrição: {e}")

    def _transcrever(self, audio_np: np.ndarray) -> str:
        """Usa o Whisper para transcrever o áudio."""
        if self._modelo is None:
            return ""

        try:
            # faster-whisper
            if hasattr(self._modelo, "transcribe") and not getattr(
                self, "_usar_whisper_padrao", False
            ):
                segmentos, _ = self._modelo.transcribe(
                    audio_np,
                    language=self.modelo_whisper_idioma,
                    beam_size=5,
                    vad_filter=True,
                    vad_parameters={"min_silence_duration_ms": 500}
                )
                return " ".join(seg.text for seg in segmentos).strip()
            else:
                # Whisper padrão
                import whisper
                resultado = self._modelo.transcribe(
                    audio_np,
                    language=self.modelo_whisper_idioma,
                    fp16=False
                )
                return resultado["text"].strip()
        except Exception as e:
            logger.error(f"Erro na transcrição Whisper: {e}")
            return ""

    async def parar(self):
        """Para o ouvinte."""
        self.ativo = False
        logger.info("Ouvinte de voz parado.")