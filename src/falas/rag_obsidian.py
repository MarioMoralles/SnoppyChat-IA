# -*- coding: utf-8 -*-
"""
rag_obsidian.py — Cérebro RAG + Cache do Snoppy (leve, offline, sem embeddings).

DUAS CAMADAS DE MEMÓRIA:
  🧠 MEMÓRIA PESSOAL  -> fatos do Mario (Sobre Mario.md, amigos.md...)
                         usada pra RESPONDER perguntas.
  ⚡ CACHE OPERACIONAL -> pastas/sites/ciclos já salvos (cache_*.md)
                         usado pra NÃO refazer trabalho do zero.

FUNÇÕES PRINCIPAIS:
  1. 🔍 buscar_relevante / montar_contexto  -> RAG nos fatos pessoais
  2. 📝 resumir_conversa                     -> resume e salva .md limpo
  3. 🏷️  gerar_tags / 🔗 gerar_links          -> organização estilo Obsidian
  4. ⚡ consultar/salvar pasta e site         -> leitura e escrita no cache
"""
from __future__ import annotations

import re
import unicodedata
from datetime import datetime
from pathlib import Path

# ─────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────
RAIZ = Path(__file__).resolve().parent.parent
VAULT = RAIZ / "snoppy-cerebro"
PASTA_MEMORIA = VAULT / "memoria"
PASTA_RESUMOS = VAULT / "resumos"

# Arquivos de cache (memória operacional)
CACHE_PASTAS = VAULT / "cache_LocalPastas.md"
CACHE_SITES = VAULT / "cache_LocalSite.md"
CACHE_CICLOS = VAULT / "cache_LocalCiclos.md"

TOP_K = 3                       # quantos trechos relevantes trazer
MAX_CHARS_CONTEXTO = 1200       # limite p/ não estourar o num_ctx

# Stopwords PT-BR (palavras que não ajudam na busca)
STOPWORDS = {
    "a", "o", "as", "os", "um", "uma", "de", "da", "do", "das", "dos",
    "e", "ou", "que", "com", "sem", "em", "no", "na", "nos", "nas",
    "para", "por", "pra", "pro", "se", "ao", "aos", "à", "às", "the",
    "meu", "minha", "seu", "sua", "eu", "voce", "você", "ele", "ela",
    "isso", "isto", "aquilo", "qual", "quais", "como", "quando", "onde",
    "é", "ser", "estar", "tem", "ter", "foi", "são", "mais", "menos",
}

# Sinônimos pra busca não falhar por palavra diferente
SINONIMOS = {
    "favorita": {"favorito", "preferida", "preferido", "predileta", "gosto", "curto"},
    "favorito": {"favorita", "preferida", "preferido", "predileta", "gosto", "curto"},
    "bebida":   {"beber", "tomar", "drink", "drinque", "bebo"},
    "comida":   {"comer", "como", "prato", "alimento"},
    "musica":   {"musical", "som", "banda", "cantor", "escuto", "ouco"},
    "trabalho": {"emprego", "profissao", "carreira"},
    "hobby":    {"hobbies", "passatempo", "lazer"},
    "linguagem": {"language", "linguagens", "lang"},
}


# ─────────────────────────────────────────────
# UTILIDADES INTERNAS
# ─────────────────────────────────────────────
def _normalizar(texto: str) -> str:
    """Tira acentos, baixa caixa, limpa espaços."""
    if not texto:
        return ""
    texto = unicodedata.normalize("NFKD", texto)
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    return texto.lower().strip()


def _tokenizar(texto: str) -> list[str]:
    """Quebra em palavras úteis (sem stopwords, sem lixo)."""
    texto = _normalizar(texto)
    palavras = re.findall(r"[a-z0-9]+", texto)
    return [p for p in palavras if len(p) > 2 and p not in STOPWORDS]


def _garantir_pastas() -> None:
    PASTA_MEMORIA.mkdir(parents=True, exist_ok=True)
    PASTA_RESUMOS.mkdir(parents=True, exist_ok=True)


def _quebrar_em_trechos(texto: str) -> list[str]:
    """Quebra o conteúdo de um .md em blocos (por parágrafo/bullet)."""
    blocos = re.split(r"\n\s*\n", texto)
    return [b.strip() for b in blocos if len(b.strip()) >= 10]


def _expandir_termos(termos: set[str]) -> set[str]:
    """Adiciona sinônimos aos termos da busca."""
    expandidos = set(termos)
    for t in termos:
        if t in SINONIMOS:
            expandidos |= SINONIMOS[t]
    return expandidos


# ─────────────────────────────────────────────
# LISTAGEM: separa memória pessoal de cache
# ─────────────────────────────────────────────
def _listar_arquivos_memoria() -> list[Path]:
    """Memória PESSOAL/fatos — usada pelo RAG (ignora .obsidian e cache_*)."""
    _garantir_pastas()
    if not VAULT.exists():
        return []
    arquivos: list[Path] = []
    for md in VAULT.rglob("*.md"):
        if ".obsidian" in md.parts:
            continue
        if md.stem.startswith("cache_"):   # cache NÃO é fato pessoal
            continue
        arquivos.append(md)
    return arquivos


def _listar_caches() -> list[Path]:
    """Cache OPERACIONAL — pastas, sites e ciclos já salvos."""
    if not VAULT.exists():
        return []
    return [md for md in VAULT.rglob("cache_*.md") if ".obsidian" not in md.parts]


# ─────────────────────────────────────────────
# 1) 🔍 BUSCA ESPERTA (RAG nos fatos pessoais)
# ─────────────────────────────────────────────
def _pontuar(trecho: str, termos_busca: set[str]) -> int:
    """Match exato (peso 2) + match por raiz (peso 1)."""
    palavras_trecho = set(_tokenizar(trecho))
    score = 0
    for termo in termos_busca:
        if termo in palavras_trecho:          # match exato
            score += 2
            continue
        for pt in palavras_trecho:            # match por raiz
            if len(termo) >= 4 and (pt.startswith(termo[:4]) or termo.startswith(pt[:4])):
                score += 1
                break
    return score


def buscar_relevante(pergunta: str, top_k: int = TOP_K) -> list[dict]:
    """Acha os trechos mais relevantes na MEMÓRIA PESSOAL."""
    termos = set(_tokenizar(pergunta))
    if not termos:
        return []
    termos = _expandir_termos(termos)

    candidatos: list[dict] = []
    for arq in _listar_arquivos_memoria():
        try:
            conteudo = arq.read_text(encoding="utf-8")
        except Exception:
            continue
        for trecho in _quebrar_em_trechos(conteudo):
            score = _pontuar(trecho, termos)
            if score > 0:
                candidatos.append({"arquivo": arq.stem, "trecho": trecho, "score": score})

    candidatos.sort(key=lambda x: x["score"], reverse=True)
    return candidatos[:top_k]


def montar_contexto(pergunta: str) -> str:
    """Monta o bloco de contexto pronto pra injetar no prompt da IA."""
    achados = buscar_relevante(pergunta)
    if not achados:
        return ""
    partes: list[str] = []
    total = 0
    for a in achados:
        bloco = f"[de: {a['arquivo']}]\n{a['trecho']}"
        if total + len(bloco) > MAX_CHARS_CONTEXTO:
            break
        partes.append(bloco)
        total += len(bloco)
    if not partes:
        return ""
    return "### Anotações relevantes do meu cérebro:\n" + "\n\n".join(partes)


# ─────────────────────────────────────────────
# 2) 🏷️ TAGS  /  3) 🔗 LINKS
# ─────────────────────────────────────────────
def gerar_tags(texto: str, maximo: int = 5) -> list[str]:
    """Gera #tags com as palavras mais frequentes do texto."""
    tokens = _tokenizar(texto)
    if not tokens:
        return []
    freq: dict[str, int] = {}
    for t in tokens:
        freq[t] = freq.get(t, 0) + 1
    ordenadas = sorted(freq.items(), key=lambda x: x[1], reverse=True)
    return [f"#{p}" for p, _ in ordenadas[:maximo]]


def gerar_links(texto: str, maximo: int = 5) -> list[str]:
    """Cria links [[Nota]] pra notas pessoais cujo nome aparece no texto."""
    texto_norm = _normalizar(texto)
    links: list[str] = []
    for arq in _listar_arquivos_memoria():
        nome = arq.stem
        if _normalizar(nome) in texto_norm and f"[[{nome}]]" not in links:
            links.append(f"[[{nome}]]")
            if len(links) >= maximo:
                break
    return links


# ─────────────────────────────────────────────
# 4) 📝 RESUMO AUTOMÁTICO + SALVAR .md LIMPO
# ─────────────────────────────────────────────
def _resumir_simples(texto: str, max_frases: int = 4) -> str:
    """Resumo extrativo leve: pega as frases mais densas em palavras-chave."""
    frases = [f.strip() for f in re.split(r"(?<=[.!?])\s+", texto.strip()) if len(f.strip()) > 15]
    if len(frases) <= max_frases:
        return " ".join(frases)

    freq: dict[str, int] = {}
    for t in _tokenizar(texto):
        freq[t] = freq.get(t, 0) + 1

    pontuadas = [(sum(freq.get(t, 0) for t in _tokenizar(f)), i, f) for i, f in enumerate(frases)]
    melhores = sorted(pontuadas, key=lambda x: x[0], reverse=True)[:max_frases]
    melhores.sort(key=lambda x: x[1])  # mantém ordem original
    return " ".join(f for _, _, f in melhores)


def resumir_conversa(texto: str, titulo: str = "") -> str:
    """Resume, gera tags + links e salva .md LIMPO em resumos/. Retorna o caminho."""
    _garantir_pastas()
    resumo = _resumir_simples(texto)
    tags = gerar_tags(texto)
    links = gerar_links(texto)

    agora = datetime.now()
    if not titulo:
        titulo = f"Resumo {agora.strftime('%Y-%m-%d %H-%M')}"
    nome_arq = re.sub(r'[<>:"/\\|?*]', "-", titulo).strip() + ".md"
    caminho = PASTA_RESUMOS / nome_arq

    linhas = [f"# {titulo}", "", f"> 🗓️ {agora.strftime('%d/%m/%Y %H:%M')}", "",
              "## 📌 Resumo", resumo, ""]
    if links:
        linhas += ["## 🔗 Relacionado", " ".join(links), ""]
    if tags:
        linhas += ["## 🏷️ Tags", " ".join(tags), ""]

    caminho.write_text("\n".join(linhas), encoding="utf-8")
    return str(caminho)


# ─────────────────────────────────────────────
# ⚡ CACHE OPERACIONAL — LER (não refazer do zero)
# ─────────────────────────────────────────────
def _ler_tabela_md(caminho: Path) -> list[list[str]]:
    """Lê uma tabela Markdown e devolve as linhas (sem cabeçalho/separador)."""
    if not caminho.exists():
        return []
    linhas: list[list[str]] = []
    cabecalho_passou = False
    for linha in caminho.read_text(encoding="utf-8").splitlines():
        linha = linha.strip()
        if not linha.startswith("|"):
            continue
        cols = [c.strip() for c in linha.split("|")[1:-1]]
        # pula linha de separador (|---|---|)
        if all(set(c) <= {"-", ":"} for c in cols if c):
            cabecalho_passou = True
            continue
        if not cabecalho_passou:   # ainda no cabeçalho
            continue
        if any(cols):              # ignora linhas totalmente vazias
            linhas.append(cols)
    return linhas


def consultar_pasta(nome: str) -> str | None:
    """Pega caminho de pasta já salvo. Ex: consultar_pasta('apostila')."""
    for cols in _ler_tabela_md(CACHE_PASTAS):
        # [Nome, Caminho, Tipo, Último acesso]
        if len(cols) >= 2 and cols[0] and _normalizar(nome) in _normalizar(cols[0]):
            return cols[1]
    return None


def consultar_site(termo: str) -> str | None:
    """Pega URL de site já visitado. Ex: consultar_site('youtube')."""
    for cols in _ler_tabela_md(CACHE_SITES):
        # [Data/Hora, Tipo, Termo/Site, URL]
        if len(cols) >= 4 and _normalizar(termo) in _normalizar(cols[2]):
            return cols[3]
    return None


# ─────────────────────────────────────────────
# ⚡ CACHE OPERACIONAL — SALVAR (gravar pra próxima)
# ─────────────────────────────────────────────
def salvar_pasta_cache(nome: str, caminho: str, tipo: str = "pasta") -> None:
    """Salva/atualiza uma pasta no cache. Cria o arquivo se não existir."""
    agora = datetime.now().strftime("%Y-%m-%d %H:%M")
    if consultar_pasta(nome):
        return  # já existe, não duplica
    if not CACHE_PASTAS.exists():
        CACHE_PASTAS.write_text(
            "# Cache de Pastas — Snoppy\n\n"
            "| Nome | Caminho | Tipo | Último acesso |\n"
            "| ---- | ------- | ---- | ------------- |\n",
            encoding="utf-8",
        )
    nova = f"| {nome} | {caminho} | {tipo} | {agora} |\n"
    with CACHE_PASTAS.open("a", encoding="utf-8") as f:
        f.write(nova)


def salvar_site_cache(termo: str, url: str, tipo: str = "site") -> None:
    """Salva/atualiza um site no cache. Cria o arquivo se não existir."""
    agora = datetime.now().strftime("%d/%m/%Y %H:%M")
    if consultar_site(termo):
        return  # já existe
    if not CACHE_SITES.exists():
        CACHE_SITES.write_text(
            "# 🌐 Histórico de Sites e Pesquisas\n\n"
            "Registro automático de sites abertos e buscas feitas.\n\n"
            "| Data/Hora | Tipo | Termo / Site | URL |\n"
            "|-----------|------|--------------|-----|\n",
            encoding="utf-8",
        )
    nova = f"| {agora} | {tipo} | {termo} | {url} |\n"
    with CACHE_SITES.open("a", encoding="utf-8") as f:
        f.write(nova)


# ─────────────────────────────────────────────
# TESTE RÁPIDO (rode: python rag_obsidian.py)
# ─────────────────────────────────────────────
if __name__ == "__main__":
    print("🧪 Testando Cérebro do Snoppy...\n")

    print("🧠 Memória pessoal:", [a.name for a in _listar_arquivos_memoria()])
    print("⚡ Caches:", [a.name for a in _listar_caches()])

    print("\n🔍 Busca 'qual a minha bebida favorita':")
    for r in buscar_relevante("qual a minha bebida favorita"):
        print(f"   [{r['score']}] {r['arquivo']}: {r['trecho'][:60]}...")

    print("\n⚡ Cache de pasta 'apostila':", consultar_pasta("apostila"))
    print("⚡ Cache de site 'youtube':", consultar_site("youtube"))
    