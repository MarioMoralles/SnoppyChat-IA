"""
Gerenciador de Memória
Armazena conversas e fatos importantes usando SQLite (local, offline).
Implementa busca por relevância usando similaridade de texto simples.
"""

import asyncio
import json
import sqlite3
import re
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional, Any

from ..utils.logger import obter_logger
from ..utils.config import Configuracao

logger = obter_logger("memoria")


class GerenciadorMemoria:
    """
    Gerenciador de memória persistente usando SQLite.
    
    Armazena:
    - Histórico de conversas
    - Fatos sobre o usuário (preferências, informações)
    - Resultados de tarefas
    - Memórias marcadas como importantes
    """

    def __init__(self, config: Configuracao):
        self.config = config
        self._dir_dados = Path.home() / ".local" / "share" / "snoopy"
        self._dir_dados.mkdir(parents=True, exist_ok=True)
        self._caminho_db = self._dir_dados / "memoria.db"
        self._conexao: Optional[sqlite3.Connection] = None

    async def inicializar(self):
        """Inicializa o banco de dados SQLite."""
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, self._criar_tabelas)
        logger.info(f"Memória iniciada: {self._caminho_db}")

    def _criar_tabelas(self):
        """Cria as tabelas no SQLite."""
        self._conexao = sqlite3.connect(
            str(self._caminho_db),
            check_same_thread=False
        )
        self._conexao.row_factory = sqlite3.Row
        cursor = self._conexao.cursor()

        cursor.executescript("""
            CREATE TABLE IF NOT EXISTS conversas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                pergunta TEXT NOT NULL,
                resposta TEXT NOT NULL,
                criada_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                tokens_estimados INTEGER DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS memorias (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                conteudo TEXT NOT NULL,
                tipo TEXT DEFAULT 'fato',
                importancia INTEGER DEFAULT 5,
                criada_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                acessada_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                acessos INTEGER DEFAULT 0,
                tags TEXT DEFAULT '[]'
            );

            CREATE TABLE IF NOT EXISTS preferencias (
                chave TEXT PRIMARY KEY,
                valor TEXT NOT NULL,
                atualizado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE INDEX IF NOT EXISTS idx_memorias_tipo ON memorias(tipo);
            CREATE INDEX IF NOT EXISTS idx_conversas_data ON conversas(criada_em);
        """)
        self._conexao.commit()

    async def salvar_conversa(self, pergunta: str, resposta: str):
        """Salva uma troca de conversa."""
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            None,
            self._salvar_conversa_sync,
            pergunta,
            resposta
        )

        # Extrai fatos importantes da conversa
        await self._extrair_e_salvar_fatos(pergunta, resposta)

    def _salvar_conversa_sync(self, pergunta: str, resposta: str):
        tokens = (len(pergunta) + len(resposta)) // 4
        self._conexao.execute(
            "INSERT INTO conversas (pergunta, resposta, tokens_estimados) VALUES (?, ?, ?)",
            (pergunta, resposta, tokens)
        )
        self._conexao.commit()

    async def salvar(self, conteudo: str, tipo: str = "fato", importancia: int = 5):
        """Salva um fato ou memória diretamente."""
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            None, self._salvar_memoria_sync,
            conteudo, tipo, importancia
        )

    def _salvar_memoria_sync(self, conteudo: str, tipo: str, importancia: int):
        # Evita duplicatas exatas
        existente = self._conexao.execute(
            "SELECT id FROM memorias WHERE conteudo = ?",
            (conteudo,)
        ).fetchone()
        if existente:
            return

        self._conexao.execute(
            "INSERT INTO memorias (conteudo, tipo, importancia) VALUES (?, ?, ?)",
            (conteudo, tipo, importancia)
        )
        self._conexao.commit()

    async def buscar_relevantes(
        self,
        consulta: str,
        limite: int = 5
    ) -> List[Dict]:
        """
        Busca memórias relevantes para a consulta.
        Usa busca por palavras-chave com scoring simples.
        """
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None, self._buscar_relevantes_sync,
            consulta, limite
        )

    def _buscar_relevantes_sync(
        self, consulta: str, limite: int
    ) -> List[Dict]:
        # Extrai palavras-chave da consulta (>3 chars, sem stop words)
        stop_words = {
            "que", "para", "com", "uma", "por", "mais", "como",
            "mas", "tem", "não", "isso", "este", "essa", "seu",
            "sua", "você", "pode", "vou", "me", "de", "do", "da",
            "em", "no", "na", "os", "as", "um", "uns"
        }
        palavras = [
            p.lower() for p in re.findall(r'\b\w{3,}\b', consulta)
            if p.lower() not in stop_words
        ]

        if not palavras:
            # Retorna memórias mais recentes e importantes
            rows = self._conexao.execute(
                "SELECT conteudo, tipo, importancia FROM memorias "
                "ORDER BY importancia DESC, acessada_em DESC LIMIT ?",
                (limite,)
            ).fetchall()
            return [dict(r) for r in rows]

        # Busca memórias que contenham as palavras-chave
        resultados_scored = []
        rows = self._conexao.execute(
            "SELECT id, conteudo, tipo, importancia FROM memorias "
            "ORDER BY importancia DESC, acessada_em DESC LIMIT 100"
        ).fetchall()

        for row in rows:
            conteudo_lower = row["conteudo"].lower()
            score = sum(1 for p in palavras if p in conteudo_lower)
            if score > 0:
                resultados_scored.append((score, dict(row)))

        # Ordena por relevância
        resultados_scored.sort(key=lambda x: x[0], reverse=True)

        # Atualiza data de acesso das memórias retornadas
        ids_retornados = [r["id"] for _, r in resultados_scored[:limite]]
        if ids_retornados:
            placeholders = ",".join("?" * len(ids_retornados))
            self._conexao.execute(
                f"UPDATE memorias SET acessos = acessos + 1, "
                f"acessada_em = CURRENT_TIMESTAMP "
                f"WHERE id IN ({placeholders})",
                ids_retornados
            )
            self._conexao.commit()

        return [r for _, r in resultados_scored[:limite]]

    async def _extrair_e_salvar_fatos(self, pergunta: str, resposta: str):
        """
        Heurística simples para extrair fatos relevantes da conversa
        e salvá-los como memórias de longo prazo.
        """
        padroes_fatos = [
            # Preferências do usuário
            (r"(eu|me)\s+(gosto|prefiro|curto|odeio|detesto)\s+(.+?)[\.\!]",
             "preferencia", 7),
            # Nome
            (r"(meu nome é|me chamo|pode me chamar de)\s+([A-Z][a-z]+)",
             "identidade", 9),
            # Profissão
            (r"(sou|trabalho como|trabalho com)\s+(.+?)[\.,]",
             "profissao", 7),
            # Localização
            (r"(moro|vivo|estou)\s+(em|no|na)\s+(.+?)[\.,]",
             "localizacao", 6),
        ]

        for padrao, tipo, importancia in padroes_fatos:
            matches = re.findall(padrao, pergunta, re.IGNORECASE)
            for match in matches:
                fato = " ".join(str(m) for m in match if m).strip()
                if len(fato) > 5:
                    await self.salvar(
                        conteudo=fato,
                        tipo=tipo,
                        importancia=importancia
                    )

    async def listar_conversas(self, limite: int = 20) -> List[Dict]:
        """Lista o histórico de conversas mais recentes."""
        loop = asyncio.get_event_loop()
        rows = await loop.run_in_executor(
            None,
            lambda: self._conexao.execute(
                "SELECT pergunta, resposta, criada_em FROM conversas "
                "ORDER BY criada_em DESC LIMIT ?",
                (limite,)
            ).fetchall()
        )
        return [dict(r) for r in rows]

    async def definir_preferencia(self, chave: str, valor: Any):
        """Salva uma preferência do usuário."""
        valor_json = json.dumps(valor, ensure_ascii=False)
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            None,
            lambda: (
                self._conexao.execute(
                    "INSERT OR REPLACE INTO preferencias (chave, valor) VALUES (?, ?)",
                    (chave, valor_json)
                ),
                self._conexao.commit()
            )
        )

    async def obter_preferencia(self, chave: str, padrao: Any = None) -> Any:
        """Obtém uma preferência do usuário."""
        loop = asyncio.get_event_loop()
        row = await loop.run_in_executor(
            None,
            lambda: self._conexao.execute(
                "SELECT valor FROM preferencias WHERE chave = ?",
                (chave,)
            ).fetchone()
        )
        if row:
            return json.loads(row["valor"])
        return padrao

    async def limpar_antigas(self, dias: int = 90):
        """Remove conversas mais antigas que X dias."""
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            None,
            lambda: (
                self._conexao.execute(
                    "DELETE FROM conversas WHERE "
                    "criada_em < datetime('now', ? || ' days')",
                    (f"-{dias}",)
                ),
                self._conexao.commit()
            )
        )
        logger.info(f"Conversas com mais de {dias} dias removidas")

    async def fechar(self):
        """Fecha a conexão com o banco de dados."""
        if self._conexao:
            self._conexao.close()
            logger.info("Memória salva e fechada")
