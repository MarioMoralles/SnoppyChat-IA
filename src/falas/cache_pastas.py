# -*- coding: utf-8 -*-
"""
cache_pastas.py — Cache persistente de caminhos em cache_LocalPastas.md do Obsidian.
"""
from __future__ import annotations

import os
import re
import unicodedata
from datetime import datetime

# ─────────────────────────────────────────────
# CONFIGURAÇÃO
# ─────────────────────────────────────────────
# Caminho FIXO do vault (pasta snoppy-cerebro, um nível acima de src/)
VAULT_OBSIDIAN: str | None = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "snoppy-cerebro",
)

# Nome REAL do arquivo (igual ao do Explorer)
ARQUIVO_CACHE = "cache_LocalPastas.md"

_CABECALHO = "# Cache de Pastas — Snoppy\n\n"
_HEADER_TABELA = (
    "| Nome | Caminho | Tipo | Último acesso |\n"
    "|------|---------|------|---------------|\n"
)


def _normalizar(texto: str) -> str:
    if not texto:
        return ""
    texto = unicodedata.normalize("NFKD", texto)
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    return texto.lower().strip()


def _achar_vault() -> str | None:
    """Localiza o vault. Se não existir, cria a pasta snoppy-cerebro."""
    if VAULT_OBSIDIAN:
        try:
            os.makedirs(VAULT_OBSIDIAN, exist_ok=True)
        except Exception:
            pass
        if os.path.isdir(VAULT_OBSIDIAN):
            return VAULT_OBSIDIAN
    return None


def _caminho_cache() -> str | None:
    """Retorna o caminho completo do cache_LocalPastas.md."""
    vault = _achar_vault()
    if not vault:
        vault = os.path.expandvars(r"%USERPROFILE%\Documents\Snoppy")
        try:
            os.makedirs(vault, exist_ok=True)
        except Exception:
            return None
    return os.path.join(vault, ARQUIVO_CACHE)


def _ler_cache() -> dict[str, dict]:
    """Lê o cache e devolve {nome_normalizado: {nome, caminho, tipo, data}}."""
    caminho = _caminho_cache()
    entradas: dict[str, dict] = {}
    if not caminho or not os.path.isfile(caminho):
        return entradas
    try:
        with open(caminho, "r", encoding="utf-8") as f:
            for linha in f:
                linha = linha.strip()
                if not linha.startswith("|") or "---" in linha:
                    continue
                if linha.lower().startswith("| nome"):
                    continue
                partes = [p.strip() for p in linha.strip("|").split("|")]
                if len(partes) < 3:
                    continue
                nome, cam, tipo = partes[0], partes[1], partes[2]
                data = partes[3] if len(partes) > 3 else ""
                if nome and cam:
                    entradas[_normalizar(nome)] = {
                        "nome": nome, "caminho": cam,
                        "tipo": tipo or "pasta", "data": data,
                    }
    except Exception:
        pass
    return entradas


def _escrever_cache(entradas: dict[str, dict]) -> bool:
    caminho = _caminho_cache()
    if not caminho:
        return False
    try:
        with open(caminho, "w", encoding="utf-8") as f:
            f.write(_CABECALHO)
            f.write(_HEADER_TABELA)
            for e in sorted(entradas.values(), key=lambda x: _normalizar(x["nome"])):
                f.write(f"| {e['nome']} | {e['caminho']} | "
                        f"{e['tipo']} | {e['data']} |\n")
        return True
    except Exception:
        return False


# ─────────────────────────────────────────────
# API PÚBLICA
# ─────────────────────────────────────────────
def buscar_no_cache(nome: str) -> str | None:
    """Retorna o caminho salvo se existir E ainda for válido no disco."""
    chave = _normalizar(nome)
    if not chave:
        return None
    entradas = _ler_cache()
    e = entradas.get(chave)
    if e and os.path.exists(e["caminho"]):
        return e["caminho"]
    if e:  # caminho sumiu → remove a entrada órfã
        entradas.pop(chave, None)
        _escrever_cache(entradas)
    return None


def salvar_no_cache(nome: str, caminho: str) -> bool:
    """Salva/atualiza um caminho no cache."""
    chave = _normalizar(nome)
    if not chave or not caminho:
        return False
    entradas = _ler_cache()
    tipo = "arquivo" if os.path.isfile(caminho) else "pasta"
    entradas[chave] = {
        "nome": nome.strip(),
        "caminho": caminho,
        "tipo": tipo,
        "data": datetime.now().strftime("%Y-%m-%d %H:%M"),
    }
    return _escrever_cache(entradas)


# aliases curtos (caso o programa.py chame "salvar"/"buscar")
def salvar(nome: str, caminho: str) -> bool:
    return salvar_no_cache(nome, caminho)


def buscar(nome: str) -> str | None:
    return buscar_no_cache(nome)


def listar_cache() -> str:
    """Mostra tudo que está salvo (debug/visualização)."""
    entradas = _ler_cache()
    if not entradas:
        return f"O cache está vazio.\n(arquivo: {_caminho_cache()})"
    linhas = [f"Cache em: {_caminho_cache()}", ""]
    for e in entradas.values():
        linhas.append(f"• {e['nome']} → {e['caminho']} ({e['tipo']})")
    return "\n".join(linhas)


def limpar_cache() -> str:
    if _escrever_cache({}):
        return "Cache limpo com sucesso."
    return "Não consegui limpar o cache."
