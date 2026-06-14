# -*- coding: utf-8 -*-
"""
snoppy_ciclo.py — Cérebro do Snoppy.

Integra:
  📂 Pastas  → cache_pastas (lê cache → varre PC → salva)
  🌐 Sites   → cache_site   (abre + registra histórico)
  🧠 IAs     → ciclo_ias    (roda o ciclo das 3 IAs)

Salve este arquivo na MESMA pasta de:
  cache_pastas.py, cache_site.py, ciclo_ias.py
"""
from __future__ import annotations

import os
import webbrowser
from pathlib import Path

import cache_pastas
import cache_site
import ciclo_ias


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
            for d in dirs:
                if alvo in d.lower():
                    return str(Path(raiz) / d)
            for a in arquivos:
                if alvo in a.lower():
                    return str(Path(raiz) / a)
    return None


# ─────────────────────────────────────────────
# API — PASTAS
# ─────────────────────────────────────────────
def obter_pasta(nome: str) -> str | None:
    """Retorna caminho: cache primeiro; senão varre PC e salva."""
    caminho = cache_pastas.buscar_no_cache(nome)
    if caminho:
        print(f"⚡ '{nome}' veio do cache: {caminho}")
        return caminho

    print(f"🔎 Procurando '{nome}' no PC...")
    caminho = varrer_pc(nome)

    if caminho:
        cache_pastas.salvar_no_cache(nome, caminho)
        print(f"💾 Encontrei e salvei no cache: {caminho}")
    else:
        print(f"❌ Não encontrei '{nome}'.")
    return caminho


def abrir_pasta(nome: str) -> bool:
    """Abre a pasta/arquivo no Explorer."""
    caminho = obter_pasta(nome)
    if not caminho:
        return False
    try:
        os.startfile(caminho)
        print(f"📂 Abri: {caminho}")
        return True
    except Exception as e:
        print(f"⚠️ Não consegui abrir: {e}")
        return False


# ─────────────────────────────────────────────
# API — SITES
# ─────────────────────────────────────────────
def abrir_site(termo: str, url: str) -> bool:
    try:
        webbrowser.open(url)
        cache_site.registrar_site(termo, url)
        print(f"🌐 Abri e registrei: {termo} → {url}")
        return True
    except Exception as e:
        print(f"⚠️ Não consegui abrir o site: {e}")
        return False


def pesquisar(termo: str) -> bool:
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
# API — CICLO DAS IAs
# ─────────────────────────────────────────────
def rodar_ciclo(pergunta: str):
    """
    Roda o ciclo das 3 IAs com a pergunta dada.

    Tenta, NESTA ORDEM, encontrar a função certa dentro de ciclo_ias:
      ciclo_ias.rodar_ciclo(pergunta)
      ciclo_ias.executar(pergunta)
      ciclo_ias.iniciar(pergunta)
      ciclo_ias.ciclo(pergunta)
      ciclo_ias.main(pergunta)
    """
    print(f"🧠 Iniciando ciclo das IAs com: '{pergunta}'\n")

    candidatos = ["rodar_ciclo", "executar", "iniciar", "ciclo", "main", "run"]

    for nome_func in candidatos:
        func = getattr(ciclo_ias, nome_func, None)
        if callable(func):
            print(f"▶️ Usando ciclo_ias.{nome_func}()")
            try:
                return func(pergunta)
            except TypeError:
                # talvez a função não receba argumento
                return func()

    # Se chegou aqui, nenhuma função bateu
    funcs = [n for n in dir(ciclo_ias) if not n.startswith("_") and callable(getattr(ciclo_ias, n))]
    print("⚠️ Não achei a função do ciclo automaticamente.")
    print(f"   Funções disponíveis em ciclo_ias.py: {funcs}")
    print("   👉 Me diga qual é a principal e eu ajusto o nome aqui.")
    return None


# ─────────────────────────────────────────────
# COMANDO ÚNICO (cérebro do Snoppy)
# ─────────────────────────────────────────────
def snoppy(comando: str, valor: str = "", extra: str = ""):
    """
    Atalho geral. Exemplos:
      snoppy("pasta", "Downloads")
      snoppy("site", "GitHub", "https://github.com")
      snoppy("buscar", "python tutorial")
      snoppy("ia", "Resuma as notícias de hoje")
    """
    comando = comando.lower().strip()

    if comando in ("pasta", "abrir", "folder"):
        return abrir_pasta(valor)
    if comando in ("site", "url", "abrir_site"):
        return abrir_site(valor, extra)
    if comando in ("buscar", "pesquisar", "google"):
        return pesquisar(valor)
    if comando in ("ia", "ias", "ciclo", "pensar"):
        return rodar_ciclo(valor)

    print(f"❓ Comando '{comando}' desconhecido. Use: pasta | site | buscar | ia")
    return None


# ─────────────────────────────────────────────
# TESTE RÁPIDO
# ─────────────────────────────────────────────
if __name__ == "__main__":
    print("🐶 Snoppy online!\n")

    # 📂 Pasta
    snoppy("pasta", "Downloads")

    # 🌐 Site
    # snoppy("site", "YouTube", "https://youtube.com")

    # 🔍 Pesquisa
    # snoppy("buscar", "clima São Paulo")

    # 🧠 Ciclo das IAs
    # snoppy("ia", "Qual a capital do Brasil?")

    print("\n📋 Caches atuais:")
    print(cache_pastas.listar_cache())
    print(cache_site.listar_cache())
