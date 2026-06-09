"""
Gerador de Imagens Offline
Usa Stable Diffusion local via biblioteca diffusers — 100% no seu PC.
Funciona com GPU (rápido) ou CPU (lento, mas funciona).

Modelo padrão: SD 1.5 (leve). Para qualidade: SDXL.
"""

import asyncio
from pathlib import Path
from datetime import datetime
from typing import Optional

from ..utils.logger import obter_logger
from ..utils.config import Configuracao

logger = obter_logger("automacao.imagens")


class GeradorImagens:
    """
    Gera imagens localmente com Stable Diffusion.
    A geração é pesada, então roda em executor (thread) para não travar o asyncio.
    """

    def __init__(self, config: Configuracao):
        self.config = config
        self.modelo_id = config.get(
            "imagem_modelo", "runwayml/stable-diffusion-v1-5"
        )
        self.passos = config.get("imagem_passos", 25)
        self._pipe = None
        self._device = "cpu"
        self._disponivel = False
        self._dir_saida = Path.home() / "Pictures" / "Snoopy_Imagens"
        self._dir_saida.mkdir(parents=True, exist_ok=True)
        self._carregando = False

    async def inicializar(self) -> bool:
        """Verifica se o diffusers está instalado (não carrega o modelo ainda)."""
        try:
            import diffusers  # noqa: F401
            import torch
            self._device = "cuda" if torch.cuda.is_available() else "cpu"
            self._disponivel = True
            logger.info(
                f"✅ Gerador de imagens disponível (device: {self._device}). "
                f"Modelo carregado sob demanda no primeiro uso."
            )
            if self._device == "cpu":
                logger.warning(
                    "Sem GPU detectada — geração de imagens será lenta (minutos)."
                )
            return True
        except ImportError:
            logger.warning(
                "Geração de imagens indisponível. "
                "Para ativar: pip install diffusers torch transformers accelerate"
            )
            return False

    def _carregar_modelo(self):
        """Carrega o pipeline do Stable Diffusion (pesado, só na 1ª geração)."""
        if self._pipe is not None:
            return
        logger.info(f"Carregando modelo de imagem '{self.modelo_id}'... (demora na 1ª vez)")
        from diffusers import StableDiffusionPipeline
        import torch

        dtype = torch.float16 if self._device == "cuda" else torch.float32
        cache = Path.home() / ".cache" / "snoopy" / "diffusers"
        cache.mkdir(parents=True, exist_ok=True)

        self._pipe = StableDiffusionPipeline.from_pretrained(
            self.modelo_id,
            torch_dtype=dtype,
            cache_dir=str(cache),
            safety_checker=None,
        )
        self._pipe = self._pipe.to(self._device)
        if self._device == "cuda":
            self._pipe.enable_attention_slicing()
        logger.info("✅ Modelo de imagem carregado.")

    async def gerar(self, prompt: str, prompt_negativo: str = "") -> str:
        """
        Gera uma imagem a partir de um prompt em texto.
        Retorna o caminho do arquivo salvo.
        """
        if not self._disponivel:
            return "Geração de imagens não está instalada neste sistema."

        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            None, self._gerar_sync, prompt, prompt_negativo
        )

    def _gerar_sync(self, prompt: str, prompt_negativo: str) -> str:
        try:
            self._carregar_modelo()
            logger.info(f"🎨 Gerando imagem: '{prompt[:60]}'")

            resultado = self._pipe(
                prompt=prompt,
                negative_prompt=prompt_negativo or None,
                num_inference_steps=self.passos,
            )
            imagem = resultado.images[0]

            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            caminho = self._dir_saida / f"snoopy_{ts}.png"
            imagem.save(caminho)
            logger.info(f"✅ Imagem salva: {caminho}")
            return str(caminho)
        except Exception as e:
            logger.error(f"Erro ao gerar imagem: {e}")
            return f"Erro ao gerar imagem: {e}"

    @property
    def disponivel(self) -> bool:
        return self._disponivel
