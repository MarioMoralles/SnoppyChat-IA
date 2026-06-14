# -*- coding: utf-8 -*-
"""
backup.py — Cria backup (.bak) de um arquivo antes da IA 3 corrigir.
Mantém histórico de versões com timestamp dentro de snoppy-cerebro/backups.
"""
from __future__ import annotations

import os
import shutil
from datetime import datetime

# ─────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────
PASTA_BASE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "snoppy-cerebro",
)
PASTA_BACKUPS = os.path.join(PASTA_BASE, "backups")

# quantas versões guardar por arquivo (evita encher o disco)
MAX_VERSOES = 5


def fazer_backup(caminho_arquivo: str) -> str | None:
    """
    Cria uma cópia .bak com timestamp do arquivo informado.
    Retorna o caminho do backup criado, ou None se falhar.
    """
    try:
        if not caminho_arquivo or not os.path.isfile(caminho_arquivo):
            print(f"   ⚠️ Backup ignorado: arquivo não existe ({caminho_arquivo})")
            return None

        os.makedirs(PASTA_BACKUPS, exist_ok=True)

        nome = os.path.basename(caminho_arquivo)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        nome_bak = f"{nome}.{stamp}.bak"
        destino = os.path.join(PASTA_BACKUPS, nome_bak)

        shutil.copy2(caminho_arquivo, destino)
        _limpar_versoes_antigas(nome)
        print(f"   💾 Backup criado: {nome_bak}")
        return destino
    except Exception as e:
        print(f"   ⚠️ Falha ao criar backup: {e}")
        return None


def _limpar_versoes_antigas(nome_original: str) -> None:
    """Mantém só as MAX_VERSOES mais recentes de cada arquivo."""
    try:
        prefixo = f"{nome_original}."
        versoes = [
            f for f in os.listdir(PASTA_BACKUPS)
            if f.startswith(prefixo) and f.endswith(".bak")
        ]
        versoes.sort(reverse=True)  # mais recentes primeiro (timestamp no nome)
        for antigo in versoes[MAX_VERSOES:]:
            try:
                os.remove(os.path.join(PASTA_BACKUPS, antigo))
            except Exception:
                pass
    except Exception:
        pass


def restaurar_backup(caminho_arquivo: str, versao_bak: str | None = None) -> bool:
    """
    Restaura um arquivo a partir de um backup.
    Se versao_bak for None, usa o backup MAIS RECENTE desse arquivo.
    """
    try:
        nome = os.path.basename(caminho_arquivo)
        if versao_bak:
            origem = os.path.join(PASTA_BACKUPS, versao_bak)
        else:
            prefixo = f"{nome}."
            versoes = sorted(
                [f for f in os.listdir(PASTA_BACKUPS)
                 if f.startswith(prefixo) and f.endswith(".bak")],
                reverse=True,
            )
            if not versoes:
                print(f"   ⚠️ Nenhum backup encontrado para {nome}")
                return False
            origem = os.path.join(PASTA_BACKUPS, versoes[0])

        if not os.path.isfile(origem):
            print(f"   ⚠️ Backup não existe: {origem}")
            return False

        shutil.copy2(origem, caminho_arquivo)
        print(f"   ↩️ Restaurado de: {os.path.basename(origem)}")
        return True
    except Exception as e:
        print(f"   ⚠️ Falha ao restaurar: {e}")
        return False


def listar_backups(nome_arquivo: str | None = None) -> str:
    """Lista backups (todos, ou só de um arquivo)."""
    if not os.path.isdir(PASTA_BACKUPS):
        return "Nenhum backup ainda."
    arquivos = [f for f in os.listdir(PASTA_BACKUPS) if f.endswith(".bak")]
    if nome_arquivo:
        arquivos = [f for f in arquivos if f.startswith(f"{nome_arquivo}.")]
    if not arquivos:
        return "Nenhum backup encontrado."
    arquivos.sort(reverse=True)
    saida = [f"💾 {len(arquivos)} backup(s) em {PASTA_BACKUPS}:\n"]
    for f in arquivos:
        saida.append(f"   • {f}")
    return "\n".join(saida)
