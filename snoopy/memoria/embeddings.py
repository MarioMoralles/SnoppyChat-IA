"""
Busca Semântica com Embeddings Locais
Usa sentence-transformers (roda local) para transformar texto em vetores
e encontrar memórias por SIGNIFICADO, não só por palavra-chave.

Isso é o "RAG" que deixa o Snoopy parecer mais inteligente: ele recupera
o que é relevante mesmo que você use palavras diferentes.
"""

import asyncio
import json
import numpy as np
from pathlib import Path
from typing import List, Dict, Optional, Tuple

from ..utils.logger import obter_logger
from ..utils.config import Configuracao

logger = obter_logger("memoria.embeddings")


class MotorEmbeddings:
    """
    Gera e compara embeddings de texto localmente.
    Modelo padrão: all-MiniLM-L6-v2 (leve, ~80MB, multilíngue razoável).
    Para português melhor: paraphrase-multilingual-MiniLM-L12-v2.
    """

    def __init__(self, config: Configuracao):
        self.config = config
        self.modelo_nome = config.get(
            "embeddings_modelo",
            "paraphrase-multilingual-MiniLM-L12-v2"
        )
        self._modelo = None
        self._disponivel = False
        # Índice em memória: lista de (texto, vetor, metadados)
        self._indice: List[Dict] = []
        self._caminho_indice = (
            Path.home() / ".local" / "share" / "snoopy" / "indice_embeddings.json"
        )

    async def inicializar(self) -> bool:
        loop = asyncio.get_running_loop()
        self._disponivel = await loop.run_in_executor(None, self._carregar)
        if self._disponivel:
            await loop.run_in_executor(None, self._carregar_indice)
        return self._disponivel

    def _carregar(self) -> bool:
        try:
            from sentence_transformers import SentenceTransformer
            cache = Path.home() / ".cache" / "snoopy" / "embeddings"
            cache.mkdir(parents=True, exist_ok=True)
            logger.info(f"Carregando modelo de embeddings '{self.modelo_nome}'...")
            self._modelo = SentenceTransformer(
                self.modelo_nome, cache_folder=str(cache)
            )
            logger.info("✅ Motor de embeddings pronto (busca semântica ativa)")
            return True
        except ImportError:
            logger.warning(
                "sentence-transformers não instalado — busca semântica desativada. "
                "Para ativar: pip install sentence-transformers"
            )
            return False
        except Exception as e:
            logger.error(f"Erro ao carregar embeddings: {e}")
            return False

    def _vetorizar(self, texto: str) -> np.ndarray:
        return self._modelo.encode(texto, convert_to_numpy=True, normalize_embeddings=True)

    async def indexar(self, texto: str, metadados: Optional[Dict] = None):
        """Adiciona um texto ao índice semântico."""
        if not self._disponivel:
            return
        loop = asyncio.get_running_loop()
        vetor = await loop.run_in_executor(None, self._vetorizar, texto)
        self._indice.append({
            "texto": texto,
            "vetor": vetor.tolist(),
            "metadados": metadados or {},
        })
        await loop.run_in_executor(None, self._salvar_indice)

    async def buscar(self, consulta: str, limite: int = 5) -> List[Dict]:
        """
        Busca os textos mais semanticamente parecidos com a consulta.
        Retorna lista de {texto, score, metadados}.
        """
        if not self._disponivel or not self._indice:
            return []

        loop = asyncio.get_running_loop()
        vetor_consulta = await loop.run_in_executor(None, self._vetorizar, consulta)

        resultados = []
        for item in self._indice:
            vetor_item = np.array(item["vetor"])
            # Similaridade de cosseno (vetores já normalizados → produto escalar)
            score = float(np.dot(vetor_consulta, vetor_item))
            resultados.append({
                "texto": item["texto"],
                "score": score,
                "metadados": item["metadados"],
            })

        resultados.sort(key=lambda x: x["score"], reverse=True)
        # Filtra resultados muito fracos
        return [r for r in resultados[:limite] if r["score"] > 0.3]

    def _salvar_indice(self):
        try:
            self._caminho_indice.parent.mkdir(parents=True, exist_ok=True)
            with open(self._caminho_indice, "w", encoding="utf-8") as f:
                json.dump(self._indice, f, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Erro ao salvar índice: {e}")

    def _carregar_indice(self):
        try:
            if self._caminho_indice.exists():
                with open(self._caminho_indice, "r", encoding="utf-8") as f:
                    self._indice = json.load(f)
                logger.info(f"Índice semântico carregado: {len(self._indice)} memórias")
        except Exception as e:
            logger.error(f"Erro ao carregar índice: {e}")
            self._indice = []

    @property
    def disponivel(self) -> bool:
        return self._disponivel
