"""
Módulo de Síntese de Voz (Text-to-Speech)
Usa Piper TTS (offline, qualidade neural) como principal.
Fallback: pyttsx3 (offline, mais simples).
"""

import asyncio
import subprocess
import tempfile
from pathlib import Path
from typing import Optional

from ..utils.logger import obter_logger
from ..utils.config import Configuracao

logger = obter_logger("voz.sintetizador")


class Sintetizador:
    """
    Sintetizador de voz offline.
    
    Prioridade:
    1. Piper TTS — qualidade neural, completamente offline
    2. pyttsx3 — fallback multiplataforma simples
    """

    VOZ_PIPER_PT_BR = "pt_BR-faber-medium"
    URL_BASE_VOZES = "https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0"

    def __init__(self, config: Configuracao):
        self.config = config
        self.motor = config.get("tts_motor", "piper")  # "piper" ou "pyttsx3"
        self.voz_piper = config.get("tts_voz_piper", self.VOZ_PIPER_PT_BR)
        self.velocidade = config.get("tts_velocidade", 1.0)

        self._piper_disponivel = False
        self._pyttsx3_motor = None
        self._fala_em_andamento = asyncio.Lock()

        # Referência opcional ao ouvinte — se definida, silencia o mic durante a fala
        self.ouvinte = None

        # Diretório de modelos Piper
        self._dir_vozes = Path.home() / ".cache" / "snoopy" / "piper"
        self._dir_vozes.mkdir(parents=True, exist_ok=True)

    async def inicializar(self):
        """Verifica e configura o motor de TTS."""
        if self.motor == "piper":
            self._piper_disponivel = await self._verificar_piper()

        if not self._piper_disponivel:
            logger.warning(
                "Piper TTS não disponível. Usando pyttsx3 como fallback."
            )
            await self._inicializar_pyttsx3()

    async def _verificar_piper(self) -> bool:
        """Verifica se o executável piper está disponível."""
        try:
            resultado = await asyncio.create_subprocess_exec(
                "piper", "--version",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            await resultado.communicate()
            if resultado.returncode == 0:
                logger.info("✅ Piper TTS encontrado")
                await self._garantir_modelo_piper()
                return True
        except FileNotFoundError:
            pass

        logger.warning(
            "Piper TTS não encontrado. "
            "Instale seguindo: https://github.com/rhasspy/piper"
        )
        return False

    async def _garantir_modelo_piper(self):
        """Baixa o modelo de voz Piper se não existir localmente."""
        arquivo_modelo = self._dir_vozes / f"{self.voz_piper}.onnx"
        arquivo_config = self._dir_vozes / f"{self.voz_piper}.onnx.json"

        if arquivo_modelo.exists() and arquivo_config.exists():
            logger.info(f"Modelo Piper '{self.voz_piper}' já disponível.")
            return

        logger.info(
            f"Baixando modelo de voz Piper '{self.voz_piper}'... "
            "(apenas na primeira execução)"
        )
        # Nota: o download real usa a URL do HuggingFace
        # Esta função indica ao usuário que precisa baixar
        print(
            f"\n⚠️  Modelo de voz Piper não encontrado.\n"
            f"   Para baixar, execute:\n"
            f"   python scripts/baixar_voz_piper.py --voz {self.voz_piper}\n"
        )

    async def _inicializar_pyttsx3(self):
        """Inicializa o motor pyttsx3."""
        try:
            import pyttsx3
            loop = asyncio.get_event_loop()
            self._pyttsx3_motor = await loop.run_in_executor(
                None, self._criar_pyttsx3
            )
            logger.info("✅ pyttsx3 inicializado como TTS de fallback")
        except ImportError:
            logger.error(
                "pyttsx3 não encontrado. "
                "Execute: pip install pyttsx3\n"
                "O assistente funcionará SEM voz até que um TTS seja instalado."
            )

    def _criar_pyttsx3(self):
        """Cria e configura o motor pyttsx3 (chamado em thread separada)."""
        import pyttsx3
        motor = pyttsx3.init()
        motor.setProperty("rate", int(150 * self.velocidade))
        motor.setProperty("volume", 0.9)

        # Tenta selecionar voz em português
        vozes = motor.getProperty("voices")
        for voz in vozes:
            if "pt" in voz.id.lower() or "brazil" in voz.name.lower():
                motor.setProperty("voice", voz.id)
                logger.info(f"Voz pyttsx3 selecionada: {voz.name}")
                break
        return motor

    async def falar(self, texto: str):
        """Sintetiza e reproduz o texto."""
        if not texto.strip():
            return

        async with self._fala_em_andamento:
            # Silencia o microfone para não captar a própria voz
            if self.ouvinte:
                self.ouvinte.silenciado = True
            try:
                if self._piper_disponivel:
                    await self._falar_piper(texto)
                elif self._pyttsx3_motor:
                    await self._falar_pyttsx3(texto)
                else:
                    logger.info(f"[TTS indisponível] Resposta: {texto}")
            finally:
                # Garante que o microfone é reativado mesmo em caso de erro
                if self.ouvinte:
                    self.ouvinte.silenciado = False

    async def _falar_piper(self, texto: str):
        """Usa Piper TTS para sintetizar e reproduzir."""
        arquivo_modelo = self._dir_vozes / f"{self.voz_piper}.onnx"

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            arquivo_wav = f.name

        try:
            # Gera o WAV com Piper
            proc = await asyncio.create_subprocess_exec(
                "piper",
                "--model", str(arquivo_modelo),
                "--output_file", arquivo_wav,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            await proc.communicate(input=texto.encode("utf-8"))

            # Reproduz o WAV
            await self._reproduzir_wav(arquivo_wav)
        finally:
            Path(arquivo_wav).unlink(missing_ok=True)

    async def _reproduzir_wav(self, caminho_wav: str):
        """Reproduz um arquivo WAV usando aplay (Linux) ou afplay (macOS)."""
        import sys
        if sys.platform == "darwin":
            cmd = ["afplay", caminho_wav]
        elif sys.platform == "win32":
            # Windows: usa PowerShell
            cmd = [
                "powershell", "-c",
                f'(New-Object Media.SoundPlayer "{caminho_wav}").PlaySync()'
            ]
        else:
            # Linux
            cmd = ["aplay", "-q", caminho_wav]

        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        await proc.communicate()

    async def _falar_pyttsx3(self, texto: str):
        """Usa pyttsx3 para sintetizar e falar (rodado em thread para não bloquear)."""
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            None,
            self._pyttsx3_falar_sincrono,
            texto
        )

    def _pyttsx3_falar_sincrono(self, texto: str):
        """Fala com pyttsx3 de forma síncrona (chamado em executor)."""
        try:
            self._pyttsx3_motor.say(texto)
            self._pyttsx3_motor.runAndWait()
        except Exception as e:
            logger.error(f"Erro no pyttsx3: {e}")