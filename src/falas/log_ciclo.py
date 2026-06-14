# -*- coding: utf-8 -*-
"""
log_ciclo.py — Registra o ciclo das 3 IAs (gerar → auditar → corrigir).
Salva em 'cache_LocalCiclos.md' dentro do vault snoppy-cerebro.
Vira o histórico de aprendizado do Snoppy.
"""
from __future__ import annotations

import os
from datetime import datetime

# ─────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────
PASTA_OBSIDIAN = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "snoppy-cerebro",
)
ARQUIVO_LOG = os.path.join(PASTA_OBSIDIAN, "cache_LocalCiclos.md")

LIMITE_CICLOS = 300


def _escapar(txt: str) -> str:
    return (txt or "").replace("|", "\\|").replace("\n", " ").strip()


def _garantir_arquivo() -> None:
    os.makedirs(PASTA_OBSIDIAN, exist_ok=True)
    if not os.path.isfile(ARQUIVO_LOG):
        with open(ARQUIVO_LOG, "w", encoding="utf-8") as f:
            f.write("# 🧠 Histórico de Ciclos das IAs — Snoppy\n\n")
            f.write("Cada linha = um ciclo (gerar → auditar → corrigir).\n\n")
            f.write("| Data/Hora | Arquivo | IA2 achou | IA3 corrigiu | Tentativas | Resultado |\n")
            f.write("|-----------|---------|-----------|--------------|------------|-----------|\n")


def _ler_linhas() -> list[str]:
    if not os.path.isfile(ARQUIVO_LOG):
        return []
    with open(ARQUIVO_LOG, "r", encoding="utf-8") as f:
        linhas = f.readlines()
    dados = []
    for ln in linhas:
        ln = ln.rstrip("\n")
        if ln.startswith("|") and "---" not in ln and "Data/Hora" not in ln:
            dados.append(ln)
    return dados


def _reescrever(dados: list[str]) -> None:
    os.makedirs(PASTA_OBSIDIAN, exist_ok=True)
    with open(ARQUIVO_LOG, "w", encoding="utf-8") as f:
        f.write("# 🧠 Histórico de Ciclos das IAs — Snoppy\n\n")
        f.write("Cada linha = um ciclo (gerar → auditar → corrigir).\n\n")
        f.write("| Data/Hora | Arquivo | IA2 achou | IA3 corrigiu | Tentativas | Resultado |\n")
        f.write("|-----------|---------|-----------|--------------|------------|-----------|\n")
        for ln in dados:
            f.write(ln + "\n")


# ─────────────────────────────────────────────
# API PÚBLICA
# ─────────────────────────────────────────────
def registrar_ciclo(
    arquivo: str,
    ia2_achou: str,
    ia3_corrigiu: str,
    tentativas: int,
    sucesso: bool,
) -> bool:
    """Registra um ciclo completo das IAs."""
    try:
        _garantir_arquivo()
        agora = datetime.now().strftime("%d/%m/%Y %H:%M")
        resultado = "✅ OK" if sucesso else "❌ Falhou"
        nova = (
            f"| {agora} | {_escapar(arquivo)} | {_escapar(ia2_achou)} | "
            f"{_escapar(ia3_corrigiu)} | {tentativas} | {resultado} |"
        )
        dados = _ler_linhas()
        dados.insert(0, nova)
        if len(dados) > LIMITE_CICLOS:
            dados = dados[:LIMITE_CICLOS]
        _reescrever(dados)
        return True
    except Exception as e:
        print(f"   ⚠️ Não consegui salvar o log do ciclo: {e}")
        return False


def listar_ciclos(quantidade: int = 15) -> str:
    """Mostra os últimos N ciclos."""
    dados = _ler_linhas()
    if not dados:
        return f"Nenhum ciclo registrado ainda.\n(arquivo: {ARQUIVO_LOG})"
    saida = [f"🧠 Últimos {min(quantidade, len(dados))} ciclos (de {len(dados)}):\n"]
    for ln in dados[:quantidade]:
        partes = [p.strip() for p in ln.strip("|").split("|")]
        if len(partes) >= 6:
            data, arq, achou, corr, tent, res = partes[:6]
            saida.append(f"   {res} [{data}] {arq} — IA2: {achou} | IA3: {corr} ({tent}x)")
    return "\n".join(saida)


def estatisticas() -> str:
    """Resumo: total, sucessos, falhas, taxa."""
    dados = _ler_linhas()
    if not dados:
        return "Sem dados para estatísticas."
    total = len(dados)
    sucessos = sum(1 for ln in dados if "✅" in ln)
    falhas = total - sucessos
    taxa = (sucessos / total * 100) if total else 0
    return (
        f"📊 Estatísticas do Snoppy:\n"
        f"   • Total de ciclos: {total}\n"
        f"   • ✅ Sucessos: {sucessos}\n"
        f"   • ❌ Falhas: {falhas}\n"
        f"   • Taxa de acerto: {taxa:.1f}%"
    )


def limpar_log() -> str:
    try:
        _reescrever([])
        return "Histórico de ciclos limpo. 🧹"
    except Exception as e:
        return f"Não consegui limpar: {e}"
