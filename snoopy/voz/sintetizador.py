"""
Módulo de Síntese de Voz — Reescrito
Usa pyttsx3 em thread separada para NÃO bloquear o asyncio.
Piper TTS como opção superior quando disponível.
"""

import asyncio
import subprocess
import tempfile
import threading
import sys
from pathlib import Path
from typing import Optional

from ..utils.logger import obter_logger
from ..utils.config import Configuracao

logger = obter_logger("voz.sintetizador")


class Sintetizador:
    """
    Sintetizador de voz offline que nunca bloqueia o event loop.

    Prioridade:
    1. Piper TTS  — qualidade neural
    2. pyttsx3    — fallback sempre disponível no Windows/Linux/macOS
    """

    VOZ_PIPER_PT_BR = "pt_BR-faber-medium"

    def __init__(self, config: Configuracao):
        self.config = config
        self.motor = config.get("tts_motor", "piper")
        self.voz_piper = config.get("tts_voz_piper", self.VOZ_PIPER_PT_BR)
        self.velocidade = config.get("tts_velocidade", 1.0)

        self._piper_ok = False
        self._pyttsx3_motor = None
        self._lock_fala = asyncio.Lock()
        self._dir_vozes = Path.home() / ".cache" / "snoopy" / "piper"
        self._dir_vozes.mkdir(parents=True, exist_ok=True)

        # Referência ao ouvinte para silenciar o mic durante a fala
        self.ouvinte = None

    async def inicializar(self):
        if self.motor == "piper":
            self._piper_ok = await self._verificar_piper()

        if not self._piper_ok:
            logger.warning("Piper TTS não disponível. Usando pyttsx3 como fallback.")
            await asyncio.get_running_loop().run_in_executor(
                None, self._init_pyttsx3
            )

    # ------------------------------------------------------------------ #
    #  Piper TTS                                                           #
    # ------------------------------------------------------------------ #
    async def _verificar_piper(self) -> bool:
        try:
            p = await asyncio.create_subprocess_exec(
                "piper", "--version",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            await p.communicate()
            if p.returncode == 0:
                logger.info("✅ Piper TTS encontrado")
                return True
        except FileNotFoundError:
            pass
        logger.warning(
            "Piper não encontrado. Instale em: https://github.com/rhasspy/piper/releases"
        )
        return False

    async def _falar_piper(self, texto: str):
        modelo = self._dir_vozes / f"{self.voz_piper}.onnx"
        if not modelo.exists():
            logger.error(f"Modelo Piper não encontrado: {modelo}")
            await self._falar_pyttsx3(texto)
            return

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            wav = f.name
        try:
            proc = await asyncio.create_subprocess_exec(
                "piper", "--model", str(modelo), "--output_file", wav,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            await proc.communicate(input=texto.encode("utf-8"))
            await self._reproduzir_wav(wav)
        finally:
            Path(wav).unlink(missing_ok=True)

    async def _reproduzir_wav(self, wav: str):
        if sys.platform == "darwin":
            cmd = ["afplay", wav]
        elif sys.platform == "win32":
            cmd = ["powershell", "-c",
                   f'(New-Object Media.SoundPlayer "{wav}").PlaySync()']
        else:
            cmd = ["aplay", "-q", wav]
        p = await asyncio.create_subprocess_exec(*cmd)
        await p.communicate()

    # ------------------------------------------------------------------ #
    #  pyttsx3 — roda em thread para não bloquear o asyncio               #
    # ------------------------------------------------------------------ #
    def _init_pyttsx3(self):
        """Inicializa pyttsx3 (chamado em executor para não bloquear)."""
        try:
            import pyttsx3
            motor = pyttsx3.init()
            motor.setProperty("rate", int(160 * self.velocidade))
            motor.setProperty("volume", 0.95)

            # Seleciona voz em português se disponível
            for voz in motor.getProperty("voices"):
                id_lower = voz.id.lower()
                nome_lower = voz.name.lower()
                if "pt" in id_lower or "brazil" in nome_lower or \
                   "portuguese" in nome_lower or "maria" in nome_lower:
                    motor.setProperty("voice", voz.id)
                    logger.info(f"Voz pyttsx3 selecionada: {voz.name}")
                    break

            self._pyttsx3_motor = motor
            logger.info("✅ pyttsx3 inicializado como TTS de fallback")
        except Exception as e:
            logger.error(f"Falha ao inicializar pyttsx3: {e}")

    async def _falar_pyttsx3(self, texto: str):
        """
        Executa pyttsx3 em um executor de thread para não bloquear o asyncio.
        pyttsx3.runAndWait() é bloqueante — NUNCA chamar direto na corrotina.
        """
        if not self._pyttsx3_motor:
            logger.warning(f"[sem TTS] {texto}")
            return

        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, self._pyttsx3_sync, texto)

    def _pyttsx3_sync(self, texto: str):
        """Fala de forma síncrona — chamado apenas via executor."""
        try:
            self._pyttsx3_motor.say(texto)
            self._pyttsx3_motor.runAndWait()
        except Exception as e:
            logger.error(f"Erro pyttsx3: {e}")
            # Tenta reinicializar o motor (pode travar após erros)
            try:
                self._init_pyttsx3()
            except Exception:
                pass

    # ------------------------------------------------------------------ #
    #  Interface pública                                                   #
    # ------------------------------------------------------------------ #
    async def falar(self, texto: str):
        """Fala o texto sem bloquear o event loop."""
        if not texto.strip():
            return

        async with self._lock_fala:
            # Silencia o microfone para evitar que o Snoopy "ouça" a si mesmo
            if self.ouvinte:
                self.ouvinte.silenciado = True

            try:
                logger.info(f"🔊 Falando: '{texto[:60]}...' " if len(texto) > 60
                            else f"🔊 Falando: '{texto}'")
                if self._piper_ok:
                    await self._falar_piper(texto)
                else:
                    await self._falar_pyttsx3(texto)
            except Exception as e:
                logger.error(f"Erro ao falar: {e}")
            finally:
                # Reativa o microfone após a fala (sempre, mesmo em erro)
                if self.ouvinte:
                    # Pequena pausa extra para o áudio do alto-falante dissipar
                    await asyncio.sleep(0.3)
                    self.ouvinte.silenciado = False