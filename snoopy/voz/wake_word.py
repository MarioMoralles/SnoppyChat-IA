"""
Detector de Palavra de Ativação dedicado.
Usa openWakeWord (leve, tempo real) para detectar 'Snoopy' SEM precisar
transcrever todo o áudio com o Whisper. Isso deixa tudo mais rápido e preciso.

Fluxo: microfone → wake word (leve, contínuo) → SÓ ENTÃO → Whisper transcreve o comando.

Fallback: se openWakeWord não estiver instalado, usa detecção por energia + Whisper.
"""

import asyncio
import queue
import threading
import time
import numpy as np
from typing import Callable, Optional
from pathlib import Path

from ..utils.logger import obter_logger
from ..utils.config import Configuracao

logger = obter_logger("voz.wake_word")


class DetectorWakeWord:
    """
    Detector de palavra de ativação em tempo real.

    Vantagens sobre transcrever tudo:
    - ~100x mais leve que rodar Whisper continuamente
    - Detecção quase instantânea
    - Não erra o nome (não depende da transcrição)
    """

    def __init__(self, config: Configuracao):
        self.config = config
        self.taxa_amostragem = 16000
        self.limiar = config.get("wake_word_limiar", 0.5)
        self._modelo = None
        self._disponivel = False

    async def inicializar(self) -> bool:
        """Carrega o modelo de wake word. Retorna True se disponível."""
        loop = asyncio.get_running_loop()
        self._disponivel = await loop.run_in_executor(None, self._carregar)
        return self._disponivel

    def _carregar(self) -> bool:
        try:
            from openwakeword.model import Model
            import openwakeword

            # Baixa modelos base na primeira vez
            try:
                openwakeword.utils.download_models()
            except Exception:
                pass

            # Modelo pré-treinado "hey jarvis" funciona razoavelmente como base.
            # Para um modelo "snoopy" customizado, treine em:
            # https://github.com/dscripka/openWakeWord
            modelo_custom = self.config.get("wake_word_modelo_caminho", "")
            if modelo_custom and Path(modelo_custom).exists():
                self._modelo = Model(wakeword_models=[modelo_custom])
                logger.info(f"✅ Wake word customizado: {modelo_custom}")
            else:
                self._modelo = Model(wakeword_models=["hey_jarvis"])
                logger.info(
                    "✅ openWakeWord carregado (modelo base 'hey jarvis'). "
                    "Para usar 'Snoopy' como gatilho, treine um modelo customizado."
                )
            return True
        except ImportError:
            logger.warning(
                "openWakeWord não instalado — usando detecção por transcrição. "
                "Para máxima velocidade: pip install openwakeword"
            )
            return False

    def detectar(self, audio_chunk: np.ndarray) -> bool:
        """
        Processa um chunk de áudio e retorna True se a palavra foi detectada.
        audio_chunk deve ser int16 a 16kHz.
        """
        if not self._modelo:
            return False
        try:
            predicoes = self._modelo.predict(audio_chunk)
            for nome, score in predicoes.items():
                if score >= self.limiar:
                    logger.info(f"🐾 Wake word detectado! ({nome}: {score:.2f})")
                    return True
        except Exception as e:
            logger.debug(f"Erro no wake word: {e}")
        return False

    @property
    def disponivel(self) -> bool:
        return self._disponivel
