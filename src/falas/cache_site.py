# -*- coding: utf-8 -*-
"""
cache_site.py — Histórico de SITES abertos e PESQUISAS feitas.
Salva em 'cache_LocalSite.md' dentro do vault snoppy-cerebro.
"""
from __future__ import annotations

import os
import re
from datetime import datetime

# ─────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────
PASTA_OBSIDIAN = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "snoppy-cerebro",
)
ARQUIVO_CACHE = os.path.join(PASTA_OBSIDIAN, "cache_LocalSite.md")

LIMITE_ENTRADAS = 500


def _garantir_arquivo() -> None:
    """Cria a pasta e o arquivo com cabeçalho, se não existirem."""
    os.makedirs(PASTA_OBSIDIAN, exist_ok=True)
    if not os.path.isfile(ARQUIVO_CACHE):
        with open(ARQUIVO_CACHE, "w", encoding="utf-8") as f:
            f.write("# 🌐 Histórico de Sites e Pesquisas\n\n")
            f.write("Registro automático de sites abertos e buscas feitas.\n\n")
            f.write("| Data/Hora | Tipo | Termo / Site | URL |\n")
            f.write("|-----------|------|--------------|-----|\n")


def _ler_linhas_tabela() -> list[str]:
    """Retorna apenas as linhas de dados da tabela (sem cabeçalho)."""
    if not os.path.isfile(ARQUIVO_CACHE):
        return []
    with open(ARQUIVO_CACHE, "r", encoding="utf-8") as f:
        linhas = f.readlines()
    dados = []
    for ln in linhas:
        ln = ln.rstrip("\n")
        if ln.startswith("|") and "---" not in ln and "Data/Hora" not in ln:
            dados.append(ln)
    return dados


def _reescrever(dados: list[str]) -> None:
    """Reescreve o arquivo inteiro mantendo o cabeçalho + dados."""
    os.makedirs(PASTA_OBSIDIAN, exist_ok=True)
    with open(ARQUIVO_CACHE, "w", encoding="utf-8") as f:
        f.write("# 🌐 Histórico de Sites e Pesquisas\n\n")
        f.write("Registro automático de sites abertos e buscas feitas.\n\n")
        f.write("| Data/Hora | Tipo | Termo / Site | URL |\n")
        f.write("|-----------|------|--------------|-----|\n")
        for ln in dados:
            f.write(ln + "\n")


def _escapar(txt: str) -> str:
    """Evita quebrar a tabela do Markdown (| vira \\|)."""
    return (txt or "").replace("|", "\\|").replace("\n", " ").strip()


# ─────────────────────────────────────────────
# API PÚBLICA
# ─────────────────────────────────────────────
def registrar_site(termo: str, url: str) -> bool:
    """Registra um SITE aberto. Retorna True se salvou."""
    return _registrar("site", termo, url)


def registrar_pesquisa(termo: str, url: str = "") -> bool:
    """Registra uma PESQUISA feita. Retorna True se salvou."""
    return _registrar("pesquisa", termo, url)


def _registrar(tipo: str, termo: str, url: str) -> bool:
    try:
        _garantir_arquivo()
        agora = datetime.now().strftime("%d/%m/%Y %H:%M")
        nova = f"| {agora} | {tipo} | {_escapar(termo)} | {_escapar(url)} |"

        dados = _ler_linhas_tabela()
        dados.insert(0, nova)  # mais recente no topo

        if len(dados) > LIMITE_ENTRADAS:
            dados = dados[:LIMITE_ENTRADAS]

        _reescrever(dados)
        return True
    except Exception as e:
        print(f"   ⚠️ Não consegui salvar no cache_site: {e}")
        return False


def listar_cache(quantidade: int = 15) -> str:
    """Mostra as últimas N entradas do histórico."""
    dados = _ler_linhas_tabela()
    if not dados:
        return f"O histórico de sites/pesquisas está vazio.\n(arquivo: {ARQUIVO_CACHE})"

    saida = [f"🌐 Últimas {min(quantidade, len(dados))} entradas (de {len(dados)}):\n"]
    for ln in dados[:quantidade]:
        partes = [p.strip() for p in ln.strip("|").split("|")]
        if len(partes) >= 3:
            data, tipo, termo = partes[0], partes[1], partes[2]
            url = partes[3] if len(partes) > 3 else ""
            emoji = "🔍" if tipo == "pesquisa" else "🌐"
            extra = f" → {url}" if url else ""
            saida.append(f"   {emoji} [{data}] {termo}{extra}")
    return "\n".join(saida)


def buscar_no_historico(termo: str) -> str:
    """Procura entradas que contenham o termo."""
    alvo = (termo or "").lower().strip()
    if not alvo:
        return "Informe o que buscar no histórico."
    dados = _ler_linhas_tabela()
    achados = [ln for ln in dados if alvo in ln.lower()]
    if not achados:
        return f"Nada encontrado no histórico com '{termo}'."

    saida = [f"🔎 {len(achados)} resultado(s) para '{termo}':\n"]
    for ln in achados[:20]:
        partes = [p.strip() for p in ln.strip("|").split("|")]
        if len(partes) >= 3:
            saida.append(f"   • [{partes[0]}] {partes[2]}")
    return "\n".join(saida)


def limpar_cache() -> str:
    """Apaga todo o histórico."""
    try:
        _reescrever([])
        return "Histórico de sites/pesquisas limpo. 🧹"
    except Exception as e:
        return f"Não consegui limpar o histórico: {e}"
