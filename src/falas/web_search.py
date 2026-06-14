# src/web_search.py
"""
Módulo de busca na web via DuckDuckGo (sem necessidade de chave de API).
"""
from __future__ import annotations

import re
from urllib.parse import unquote

import requests
from bs4 import BeautifulSoup


def _limpar_link(url: str) -> str:
    """Extrai a URL real dos links de redirecionamento do DuckDuckGo."""
    m = re.search(r"uddg=([^&]+)", url)
    return unquote(m.group(1)) if m else url


def buscar_web(query: str, max_resultados: int = 5, timeout: int = 10) -> list[dict]:
    """
    Busca no DuckDuckGo e retorna lista de {title, url, snippet}.
    """
    try:
        resp = requests.post(
            "https://duckduckgo.com/html/",
            data={"q": query},
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=timeout,
        )
        resp.raise_for_status()
    except Exception as e:
        return [{"title": "Erro na busca", "url": "", "snippet": str(e)}]

    soup = BeautifulSoup(resp.text, "html.parser")
    resultados = []

    for bloco in soup.select(".result")[:max_resultados]:
        link_tag = bloco.select_one("a.result__a")
        snippet_tag = bloco.select_one(".result__snippet")
        if not link_tag:
            continue
        resultados.append({
            "title": link_tag.get_text(" ", strip=True),
            "url": _limpar_link(link_tag.get("href", "")),
            "snippet": snippet_tag.get_text(" ", strip=True) if snippet_tag else "",
        })

    return resultados


def precisa_buscar(texto: str) -> bool:
    """Heurística: decide se a resposta da IA está fraca e precisa de busca web."""
    if not texto or len(texto.strip()) < 80:
        return True
    t = texto.lower()
    sinais = ("não sei", "nao sei", "não tenho certeza", "nao tenho certeza",
              "não tenho acesso", "não posso confirmar", "talvez", "não encontrei")
    return any(s in t for s in sinais)
