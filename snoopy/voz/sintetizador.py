"""
Módulo de Síntese de Voz — pyttsx3 corrigido para Windows
Recria o motor a cada fala (bug clássico do pyttsx3: trava ao reutilizar).
Roda em thread separada para não bloquear o asyncio.
"""

import asyncio
import subprocess
import tempfile
import sys
from pathlib import Path
from typing import Optional

from ..utils.logger import obter_logger
from ..utils.config import Configuracao

logger = obter_logger("voz.sintetizador")


class Sintetizador:
    """
    Sintetizador de voz offline que nunca bloqueia o event loop
    e que recria o motor pyttsx3 a cada fala (evita o travamento do Windows).
    """

    VOZ_PIPER_PT_BR = "pt_BR-faber-medium"

    def __init__(self, config: Configuracao):
        self.config = config
        self.motor = config.get("tts_motor", "piper")
        self.voz_piper = config.get("tts_voz_piper", self.VOZ_PIPER_PT_BR)

        # Velocidade da fala (palavras por minuto). 150-175 soa mais natural.
        self.velocidade_wpm = config.get("tts_velocidade_wpm", 175)
        self.volume = config.get("tts_volume", 1.0)

        self._piper_ok = False
        self._id_voz_pt = None   # guarda o ID da voz pt-BR encontrada
        self._lock_fala = asyncio.Lock()
        self._dir_vozes = Path.home() / ".cache" / "snoopy" / "piper"
        self._dir_vozes.mkdir(parents=True, exist_ok=True)

        self.ouvinte = None  # para silenciar o mic durante a fala

    async def inicializar(self):
        if self.motor == "piper":
            self._piper_ok = await self._verificar_piper()

        if not self._piper_ok:
            logger.warning("Piper TTS não disponível. Usando pyttsx3 como fallback.")
            await asyncio.get_running_loop().run_in_executor(
                None, self._descobrir_voz_pt
            )

    # ------------------------------------------------------------------ #
    #  Descoberta da melhor voz em português (uma vez só)                 #
    # ------------------------------------------------------------------ #
    def _descobrir_voz_pt(self):
        """Descobre o ID da melhor voz pt-BR disponível no sistema."""
        try:
            import pyttsx3
            motor = pyttsx3.init()
            melhor = None
            for voz in motor.getProperty("voices"):
                texto = (voz.id + " " + voz.name).lower()
                # Prioriza vozes brasileiras
                if "brazil" in texto or "pt-br" in texto or "maria" in texto \
                   or "daniel" in texto:
                    melhor = voz.id
                    logger.info(f"Voz pt-BR encontrada: {voz.name}")
                    break
                elif "portuguese" in texto or "pt_" in texto or "_pt" in texto:
                    melhor = voz.id  # guarda mas continua procurando br
            self._id_voz_pt = melhor
            try:
                motor.stop()
                del motor
            except Exception:
                pass
            logger.info("✅ pyttsx3 pronto (voz recriada a cada fala)")
        except Exception as e:
            logger.error(f"Erro ao descobrir voz pyttsx3: {e}")

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
        logger.warning("Piper não encontrado.")
        return False

    async def _falar_piper(self, texto: str):
        modelo = self._dir_vozes / f"{self.voz_piper}.onnx"
        if not modelo.exists():
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
    #  pyttsx3 — recria motor a cada fala, roda em thread                 #
    # ------------------------------------------------------------------ #
    async def _falar_pyttsx3(self, texto: str):
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, self._pyttsx3_sync, texto)

    def _pyttsx3_sync(self, texto: str):
        """
        Cria um motor pyttsx3 NOVO a cada chamada e o destrói depois.
        Esta é a forma confiável de usar pyttsx3 no Windows — reutilizar
        a mesma instância faz ele falar só na 1ª vez e travar nas seguintes.
        """
        try:
            import pyttsx3
            motor = pyttsx3.init()
            motor.setProperty("rate", int(self.velocidade_wpm))
            motor.setProperty("volume", float(self.volume))
            if self._id_voz_pt:
                motor.setProperty("voice", self._id_voz_pt)
            motor.say(texto)
            motor.runAndWait()
            try:
                motor.stop()
                del motor
            except Exception:
                pass
        except Exception as e:
            logger.error(f"Erro pyttsx3: {e}")

    # ------------------------------------------------------------------ #
    #  Interface pública                                                   #
    # ------------------------------------------------------------------ #
    async def falar(self, texto: str):
        if not texto.strip():
            return

        async with self._lock_fala:
            if self.ouvinte:
                self.ouvinte.silenciado = True
            try:
                preview = texto[:60] + "..." if len(texto) > 60 else texto
                logger.info(f"🔊 Falando: '{preview}'")
                if self._piper_ok:
                    await self._falar_piper(texto)
                else:
                    await self._falar_pyttsx3(texto)
            except Exception as e:
                logger.error(f"Erro ao falar: {e}")
            finally:
                if self.ouvinte:
                    await asyncio.sleep(0.3)
                    self.ouvinte.silenciado = FalseA