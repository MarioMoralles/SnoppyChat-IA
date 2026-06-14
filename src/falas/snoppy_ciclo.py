# -*- coding: utf-8 -*-
"""
snoppy_ciclo.py — Integração: cache de pastas + histórico de sites.

Fluxo de pastas:
  1) LÊ do cache (cache_pastas)  →  se achar e existir no disco, retorna na hora
  2) Não tem → VARRE o PC procurando a pasta
  3) Achou → GRAVA no cache pra próxima vez ser instantâneo

Coloque este arquivo na MESMA pasta de:
  cache_pastas.py, cache_site.py, ciclo_ias.py
"""
from __future__ import annotations

import os
import webbrowser
from pathlib import Path

import cache_pastas
import cache_site


# ─────────────────────────────────────────────
# BUSCA NO PC
# ─────────────────────────────────────────────
def varrer_pc(nome: str) -> str | None:
    """Varre as pastas comuns do PC procurando uma pasta/arquivo pelo nome."""
    alvo = nome.lower().strip()
    if not alvo:
        return None

    bases = [
        Path.home() / "Desktop",
        Path.home() / "OneDrive" / "Desktop",
        Path.home() / "Documents",
        Path.home() / "Documentos",
        Path.home() / "Downloads",
        Path.home() / "Pictures",
        Path.home() / "Imagens",
    ]

    for base in bases:
        if not base.exists():
            continue
        for raiz, dirs, arquivos in os.walk(base):
            # procura pastas
            for d in dirs:
                if alvo in d.lower():
                    return str(Path(raiz) / d)
            # procura arquivos também
            for a in arquivos:
                if alvo in a.lower():
                    return str(Path(raiz) / a)
    return None


# ─────────────────────────────────────────────
# API PRINCIPAL — PASTAS
# ─────────────────────────────────────────────
def obter_pasta(nome: str) -> str | None:
    """
    Retorna o caminho de uma pasta/arquivo.
    Usa cache primeiro; se não tiver, varre o PC e salva.
    """
    # 1) LÊ do cache (já valida se ainda existe no disco)
    caminho = cache_pastas.buscar_no_cache(nome)
    if caminho:
        print(f"⚡ '{nome}' veio do cache: {caminho}")
        return caminho

    # 2) Não tem → varre o PC
    print(f"🔎 Procurando '{nome}' no PC...")
    caminho = varrer_pc(nome)

    # 3) Achou → grava pra próxima vez
    if caminho:
        cache_pastas.salvar_no_cache(nome, caminho)
        print(f"💾 Encontrei e salvei no cache: {caminho}")
    else:
        print(f"❌ Não encontrei '{nome}' nas pastas vasculhadas.")
    return caminho


def abrir_pasta(nome: str) -> bool:
    """Abre a pasta/arquivo no Explorer do Windows."""
    caminho = obter_pasta(nome)
    if not caminho:
        return False
    try:
        os.startfile(caminho)  # Windows
        print(f"📂 Abri: {caminho}")
        return True
    except Exception as e:
        print(f"⚠️ Não consegui abrir: {e}")
        return False


# ─────────────────────────────────────────────
# API PRINCIPAL — SITES
# ─────────────────────────────────────────────
def abrir_site(termo: str, url: str) -> bool:
    """Abre um site no navegador e registra no histórico."""
    try:
        webbrowser.open(url)
        cache_site.registrar_site(termo, url)
        print(f"🌐 Abri e registrei: {termo} → {url}")
        return True
    except Exception as e:
        print(f"⚠️ Não consegui abrir o site: {e}")
        return False


def pesquisar(termo: str) -> bool:
    """Faz uma pesquisa no Google e registra no histórico."""
    url = f"https://www.google.com/search?q={termo.replace(' ', '+')}"
    try:
        webbrowser.open(url)
        cache_site.registrar_pesquisa(termo, url)
        print(f"🔍 Pesquisei e registrei: {termo}")
        return True
    except Exception as e:
        print(f"⚠️ Não consegui pesquisar: {e}")
        return False


# ─────────────────────────────────────────────
# TESTE RÁPIDO
# ─────────────────────────────────────────────
if __name__ == "__main__":
    print("🐶 Testando o Snoppy...\n")

    # Teste de pasta
    obter_pasta("Downloads")

    # Teste de site
    # abrir_site("YouTube", "https://youtube.com")

    # Teste de pesquisa
    # pesquisar("clima em São Paulo")

    # Ver o que está salvo
    print("\n" + cache_pastas.listar_cache())
    print("\n" + cache_site.listar_cache())
