# -*- coding: utf-8 -*-
"""
snoppy.py — ORQUESTRADOR estilo Jarvis.
Decide entre AÇÃO no PC (programas.py) e CONVERSA com IA.
Pipeline das 3 IAs do Ollama (todas usando hermes3:3b — leve e rápido):
  IA-1 (Criadora)  -> gera a resposta inicial
  IA-2 (Revisora)  -> revisa e aponta falhas/melhorias
  IA-3 (Corretora) -> aplica as correções e entrega a versão final

🆕 RAG (rag_obsidian.py) — busca esperta + resumo + tags + links
🆕 Perguntas factuais curtas com contexto = resposta DIRETA (sem ciclo)
🆕 Prompt rígido: usa fatos do Mario, não inventa, não fala "minhas preferências"
"""
from __future__ import annotations

import requests
import programas as pg
import log_ciclo
import rag_obsidian as rag

# ─────────────────────────────────────────────
# CONFIG OLLAMA
# ─────────────────────────────────────────────
OLLAMA_URL = "http://localhost:11434/api/generate"
TIMEOUT_IA = 180

MODELO_CRIADOR  = "hermes3:3b"
MODELO_REVISOR  = "hermes3:3b"
MODELO_CORRETOR = "hermes3:3b"

MAX_TENTATIVAS = 2
KEEP_ALIVE = "30m"

OPCOES_IA = {
    "temperature": 0.2,   # ← menos invenção, mais fiel aos fatos
    "top_p": 0.9,
    "num_ctx": 2048,
    "num_predict": 512,
    "num_thread": 4,
}

BANNER = """
===========================================================
   🐶  S N O P P Y   O N L I N E   —  estilo Jarvis
-----------------------------------------------------------
   Ações no PC : 'abra o spotify' | 'abra o youtube'
                 'abra a pasta downloads' | 'feche o chrome'
                 'pesquise gatos fofos'
   Conversa IA : 'me explique recursão' | 'o que é python'
   Cérebro/RAG : 'resuma isso: <texto longo>'
   Caches      : 'ver cache' | 'ver historico' | 'reindexar'
   Aprendizado : 'ver ciclos' | 'estatisticas' | 'limpar ciclos'
   Sair        : 'sair'
===========================================================
"""

GATILHOS_IA = (
    "me explique", "explique", "explica", "me explica", "o que e", "o que é",
    "como funciona", "como faço", "como fazer", "por que", "porque", "pq",
    "qual", "quais", "quando", "onde fica", "quem", "me ajude", "me ajuda",
    "escreva", "escreve", "crie um", "crie uma", "criar", "gere", "gera",
    "resuma", "resumir", "traduza", "traduz", "me fale", "fale sobre",
    "diga", "conte", "me conte", "exemplo de", "diferença entre",
)


# ─────────────────────────────────────────────
# DECISÃO: AÇÃO NO PC OU CONVERSA?
# ─────────────────────────────────────────────
def eh_acao_pc(texto: str) -> bool:
    low = pg.normalizar(texto)

    for g in GATILHOS_IA:
        if low.startswith(pg.normalizar(g)):
            return False

    if low in ("recarregar indice", "reindexar", "atualizar programas",
               "ver cache", "listar cache", "mostrar cache",
               "limpar cache", "apagar cache",
               "ver historico", "ver histórico", "ver sites", "ver pesquisas",
               "limpar historico", "limpar histórico",
               "ver ciclos", "estatisticas", "estatísticas",
               "limpar ciclos"):
        return True
    if low.startswith(("buscar no historico", "buscar no histórico")):
        return True

    if (pg.quer_pesquisar(texto) or pg.quer_fechar(texto)
            or pg.quer_abrir(texto) or pg.quer_pasta(texto) or pg.quer_site(texto)):
        return True

    if pg._buscar_site(low) or pg._parece_url(low):
        return True

    return False


# ─────────────────────────────────────────────
# CHAMADA BÁSICA AO OLLAMA
# ─────────────────────────────────────────────
def _chamar_ollama(modelo: str, prompt: str) -> str:
    payload = {
        "model": modelo,
        "prompt": prompt,
        "stream": False,
        "keep_alive": KEEP_ALIVE,
        "options": OPCOES_IA,
    }
    try:
        r = requests.post(OLLAMA_URL, json=payload, timeout=TIMEOUT_IA)
        r.raise_for_status()
        return r.json().get("response", "").strip()
    except requests.exceptions.ConnectionError:
        return "__ERRO_CONEXAO__"
    except requests.exceptions.Timeout:
        return "__ERRO_TIMEOUT__"
    except Exception as e:
        return f"__ERRO__: {e}"


def _erro(txt: str) -> bool:
    return txt.startswith(("__ERRO_CONEXAO__", "__ERRO_TIMEOUT__", "__ERRO__"))


def _esta_ok(revisao: str) -> bool:
    r = revisao.strip().upper()
    return r.startswith("OK") and len(revisao.strip()) < 8


# ─────────────────────────────────────────────
# PRÉ-AQUECIMENTO
# ─────────────────────────────────────────────
def preaquecer() -> None:
    print("   🔥 Pré-aquecendo o hermes3:3b na memória...")
    resp = _chamar_ollama(MODELO_CRIADOR, "oi")
    if _erro(resp):
        print("   ⚠️ Não consegui pré-aquecer (Ollama está rodando?).")
    else:
        print("   ✅ Modelo pronto e quente na RAM!")


# ─────────────────────────────────────────────
# PIPELINE DAS 3 IAs (com RAG + prompt rígido + pular ciclo)
# ─────────────────────────────────────────────
def pipeline_3_ias(pergunta: str, verboso: bool = True) -> str:
    # ---------- 🆕 RAG: busca no cérebro ----------
    contexto = rag.montar_contexto(pergunta)
    if contexto and verboso:
        print("   📂 Encontrei anotações relevantes no cérebro!")

    # 🆕 Pergunta CURTA + tem contexto = resposta DIRETA (sem ciclo bagunçar)
    pergunta_curta = len(pergunta.split()) <= 8
    pular_ciclo = bool(contexto) and pergunta_curta

    # ---------- IA-1: CRIA (prompt rígido) ----------
    if verboso:
        print("   🧠 IA-1 (Criadora) pensando...")

    bloco_contexto = f"{contexto}\n\n" if contexto else ""
    p1 = (
        "Você é o Snoppy, o assistente pessoal do Mario. "
        "Responda SEMPRE em português do Brasil, falando COM o Mario (2ª pessoa).\n\n"
        f"{bloco_contexto}"
        "═══════════════════════════════════════\n"
        "REGRAS OBRIGATÓRIAS:\n"
        "1. As anotações acima são FATOS sobre o MARIO (o usuário), não sobre você.\n"
        "2. Se a pergunta for respondida pelas anotações, responda DIRETO e CURTO "
        "usando essa informação. Ex: bebida favorita → 'Sua bebida favorita é café ☕'.\n"
        "3. NUNCA fale das SUAS preferências. Você é uma IA, não tem gostos pessoais.\n"
        "4. NÃO invente nada que não esteja nas anotações. "
        "Se não souber, diga que não há essa informação registrada.\n"
        "═══════════════════════════════════════\n\n"
        f"Pergunta do Mario: {pergunta}\n\nResposta:"
    )
    rascunho = _chamar_ollama(MODELO_CRIADOR, p1)
    if rascunho == "__ERRO_CONEXAO__":
        return ("⚠️ Não consegui falar com o Ollama. Ele está rodando?\n"
                "   Abra outro terminal e rode: `ollama serve`")
    if _erro(rascunho):
        return f"⚠️ Erro na IA-1: {rascunho}"

    resposta = rascunho

    # 🆕 Resposta direta: factual curta com contexto → não roda o ciclo
    if pular_ciclo:
        if verboso:
            print("   ⚡ Resposta direta (fato do cérebro, sem revisão).")
        try:
            log_ciclo.registrar_ciclo(
                arquivo=f"pergunta: {pergunta[:60]}",
                ia2_achou="pulado (resposta factual direta)",
                ia3_corrigiu="nada",
                tentativas=0,
                sucesso=True,
            )
        except Exception:
            pass
        return resposta

    ultima_revisao = "nada"
    ultima_correcao = "nada"
    sucesso = False
    tentativa = 0

    # ── CICLO revisar → corrigir ──
    while tentativa < MAX_TENTATIVAS:
        tentativa += 1

        if verboso:
            print(f"   🔍 IA-2 (Revisora) procurando falhas... "
                  f"(tentativa {tentativa}/{MAX_TENTATIVAS})")
        p2 = (
            "Você é um revisor técnico rigoroso. Analise a resposta abaixo e liste "
            "de forma curta os ERROS, imprecisões ou pontos que faltam. "
            "Se estiver perfeita, escreva apenas 'OK'. Não reescreva a resposta.\n\n"
            f"Pergunta original: {pergunta}\n\n"
            f"Resposta a revisar:\n{resposta}\n\nProblemas encontrados:"
        )
        revisao = _chamar_ollama(MODELO_REVISOR, p2)
        if _erro(revisao):
            revisao = "OK"

        if _esta_ok(revisao):
            if verboso:
                print("   ✅ IA-2: nada a corrigir.")
            sucesso = True
            break

        ultima_revisao = revisao.replace("\n", " ")[:200]

        if verboso:
            print("   ✨ IA-3 (Corretora) aplicando melhorias...")
        p3 = (
            "Você é o Snoppy. Reescreva a resposta abaixo aplicando as correções "
            "apontadas pela revisão. Entregue a versão FINAL, completa e clara, "
            "em português do Brasil. Não comente o processo, só dê a resposta final.\n\n"
            f"Pergunta original: {pergunta}\n\n"
            f"Resposta original:\n{resposta}\n\n"
            f"Correções a aplicar:\n{revisao}\n\nResposta final:"
        )
        corrigida = _chamar_ollama(MODELO_CORRETOR, p3)

        if _erro(corrigida) or not corrigida.strip():
            if verboso:
                print("   ⚠️ IA-3 falhou; mantendo a versão anterior.")
            break

        resposta = corrigida
        ultima_correcao = f"correção aplicada (tentativa {tentativa})"

    try:
        log_ciclo.registrar_ciclo(
            arquivo=f"pergunta: {pergunta[:60]}",
            ia2_achou=ultima_revisao,
            ia3_corrigiu=ultima_correcao,
            tentativas=tentativa,
            sucesso=sucesso,
        )
    except Exception:
        pass

    return resposta


# ─────────────────────────────────────────────
# CHECAGEM DO OLLAMA
# ─────────────────────────────────────────────
def checar_ollama() -> None:
    try:
        r = requests.get("http://localhost:11434/api/tags", timeout=3)
        modelos = [m["name"] for m in r.json().get("models", [])]
        print("[OK] Ollama conectado.")
        for nome, papel in [(MODELO_CRIADOR, "Criadora"),
                            (MODELO_REVISOR, "Revisora"),
                            (MODELO_CORRETOR, "Corretora")]:
            status = "✅" if any(nome in m for m in modelos) else "❌ (faltando)"
            print(f"     {status} IA-{papel}: {nome}")
    except Exception:
        print("[AVISO] Ollama não respondeu. Rode 'ollama serve' "
              "em outro terminal para a conversa com IA funcionar.")


# ─────────────────────────────────────────────
# ROTEADOR PRINCIPAL
# ─────────────────────────────────────────────
def responder(texto: str) -> str:
    low = pg.normalizar(texto)

    if low in ("ver ciclos",):
        return log_ciclo.listar_ciclos(15)
    if low in ("estatisticas", "estatísticas"):
        return log_ciclo.estatisticas()
    if low in ("limpar ciclos",):
        return log_ciclo.limpar_log()

    if low.startswith(("resuma isso", "resumir isso", "salvar resumo")):
        conteudo = texto.split(":", 1)[1].strip() if ":" in texto else ""
        if not conteudo:
            return "Me manda assim: 'resuma isso: <seu texto>' 🐶"
        caminho = rag.resumir_conversa(conteudo)
        return (f"✅ Resumo salvo no Obsidian com tags e links!\n"
                f"   📄 {caminho}")

    if eh_acao_pc(texto):
        return pg.interpretar_comando(texto)
    return pipeline_3_ias(texto)


# ─────────────────────────────────────────────
# LOOP
# ─────────────────────────────────────────────
def iniciar() -> None:
    print(BANNER)
    print(pg.recarregar_indice())
    checar_ollama()
    preaquecer()

    while True:
        try:
            cmd = input("\n> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nAté logo! 🐶")
            break

        if not cmd:
            continue
        if cmd.lower() in ("sair", "exit", "quit"):
            print("Até logo! 🐶")
            break

        print(responder(cmd))


if __name__ == "__main__":
    iniciar()
