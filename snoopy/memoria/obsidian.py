"""
Integração com Obsidian
O Snoopy usa um cofre (vault) do Obsidian como memória de longo prazo.
Vantagens: arquivos Markdown puros, 100% locais, você vê o grafo de conhecimento
crescer no próprio Obsidian. O Snoopy lê e escreve notas, criando links entre temas.
"""

import re
import asyncio
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional

from ..utils.logger import obter_logger
from ..utils.config import Configuracao

logger = obter_logger("memoria.obsidian")


class CofreObsidian:
    """
    Gerencia um vault Obsidian como base de conhecimento do Snoopy.

    Estrutura criada dentro do vault:
      Snoopy/
        Conversas/      — notas diárias das conversas
        Fatos/          — fatos aprendidos sobre o usuário
        Tarefas/        — resultados de tarefas
        Aprendizados/   — insights e padrões
    """

    def __init__(self, config: Configuracao):
        self.config = config
        caminho = config.get("obsidian_vault", "")
        self.vault = Path(caminho).expanduser() if caminho else None
        self.ativo = bool(self.vault)
        self._subpastas = ["Conversas", "Fatos", "Tarefas", "Aprendizados"]

    async def inicializar(self) -> bool:
        if not self.ativo:
            logger.info(
                "Obsidian não configurado. "
                "Defina 'obsidian_vault' no config para ativar a memória estendida."
            )
            return False

        if not self.vault.exists():
            logger.warning(f"Vault Obsidian não existe: {self.vault}. Criando...")
            self.vault.mkdir(parents=True, exist_ok=True)

        # Cria a estrutura de pastas do Snoopy dentro do vault
        base = self.vault / "Snoopy"
        for sub in self._subpastas:
            (base / sub).mkdir(parents=True, exist_ok=True)

        logger.info(f"✅ Memória Obsidian ativa: {self.vault}")
        return True

    # ------------------------------------------------------------------ #
    #  Escrita                                                            #
    # ------------------------------------------------------------------ #
    async def registrar_conversa(self, pergunta: str, resposta: str):
        """Adiciona a troca à nota diária de conversas."""
        if not self.ativo:
            return
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, self._registrar_conversa_sync, pergunta, resposta)

    def _registrar_conversa_sync(self, pergunta: str, resposta: str):
        hoje = datetime.now().strftime("%Y-%m-%d")
        hora = datetime.now().strftime("%H:%M")
        nota = self.vault / "Snoopy" / "Conversas" / f"{hoje}.md"

        if not nota.exists():
            cabecalho = (
                f"# Conversas de {hoje}\n\n"
                f"#snoopy #conversa\n\n"
            )
            nota.write_text(cabecalho, encoding="utf-8")

        bloco = (
            f"\n## {hora}\n\n"
            f"**Você:** {pergunta}\n\n"
            f"**Snoopy:** {resposta}\n\n"
            f"---\n"
        )
        with open(nota, "a", encoding="utf-8") as f:
            f.write(bloco)

    async def salvar_fato(self, fato: str, categoria: str = "geral", tags: List[str] = None):
        """Salva um fato aprendido como nota, com links e tags."""
        if not self.ativo:
            return
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, self._salvar_fato_sync, fato, categoria, tags or [])

    def _salvar_fato_sync(self, fato: str, categoria: str, tags: List[str]):
        pasta = self.vault / "Snoopy" / "Fatos"
        # Nome do arquivo baseado no início do fato
        nome_base = re.sub(r'[^\w\s-]', '', fato[:40]).strip().replace(' ', '_')
        nota = pasta / f"{nome_base}.md"

        tags_str = " ".join(f"#{t}" for t in (tags + [categoria, "snoopy"]))
        conteudo = (
            f"# {fato[:60]}\n\n"
            f"{tags_str}\n\n"
            f"{fato}\n\n"
            f"*Registrado em {datetime.now().strftime('%d/%m/%Y %H:%M')}*\n"
        )
        nota.write_text(conteudo, encoding="utf-8")

    async def salvar_aprendizado(self, titulo: str, conteudo: str):
        """Salva um insight/padrão na pasta Aprendizados."""
        if not self.ativo:
            return
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, self._salvar_aprendizado_sync, titulo, conteudo)

    def _salvar_aprendizado_sync(self, titulo: str, conteudo: str):
        pasta = self.vault / "Snoopy" / "Aprendizados"
        nome = re.sub(r'[^\w\s-]', '', titulo[:40]).strip().replace(' ', '_')
        nota = pasta / f"{nome}.md"
        texto = (
            f"# {titulo}\n\n#aprendizado #snoopy\n\n{conteudo}\n\n"
            f"*{datetime.now().strftime('%d/%m/%Y %H:%M')}*\n"
        )
        nota.write_text(texto, encoding="utf-8")

    # ------------------------------------------------------------------ #
    #  Leitura                                                            #
    # ------------------------------------------------------------------ #
    async def ler_todas_notas(self) -> List[Dict]:
        """Lê todas as notas do Snoopy no vault (para indexação semântica)."""
        if not self.ativo:
            return []
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self._ler_todas_sync)

    def _ler_todas_sync(self) -> List[Dict]:
        notas = []
        base = self.vault / "Snoopy"
        if not base.exists():
            return notas
        for arquivo in base.rglob("*.md"):
            try:
                texto = arquivo.read_text(encoding="utf-8")
                notas.append({
                    "arquivo": str(arquivo),
                    "nome": arquivo.stem,
                    "categoria": arquivo.parent.name,
                    "texto": texto,
                })
            except Exception:
                pass
        return notas

    async def buscar_texto(self, termo: str) -> List[Dict]:
        """Busca simples por palavra-chave nas notas (fallback sem embeddings)."""
        notas = await self.ler_todas_notas()
        termo_lower = termo.lower()
        return [n for n in notas if termo_lower in n["texto"].lower()]
