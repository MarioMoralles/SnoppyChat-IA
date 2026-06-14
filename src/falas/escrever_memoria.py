from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
CAMINHO_MEMORIA = RAIZ / "snoppy-cerebro" / "memoria" / "Sobre Mario.md"


def ler_memoria_completa():
    """Lê todo o conteúdo da memória. Retorna string vazia se não existir."""
    if not CAMINHO_MEMORIA.exists():
        return ""
    return CAMINHO_MEMORIA.read_text(encoding="utf-8")


def ja_existe(texto):
    """Verifica se a informação já está salva (evita repetição)."""
    conteudo = ler_memoria_completa().lower()
    return texto.strip().lower() in conteudo


def salvar_na_memoria(texto_novo, categoria="Geral"):
    """Salva no .md sob a categoria certa, sem repetir."""
    texto_novo = texto_novo.strip()

    if not texto_novo:
        return "vazio"

    if ja_existe(texto_novo):
        return "repetido"

    conteudo = ler_memoria_completa()
    cabecalho = f"## {categoria}"

    if cabecalho in conteudo:
        # Categoria já existe -> insere logo abaixo do cabeçalho
        linhas = conteudo.splitlines()
        novas_linhas = []
        for linha in linhas:
            novas_linhas.append(linha)
            if linha.strip() == cabecalho:
                novas_linhas.append(f"- {texto_novo}")
        CAMINHO_MEMORIA.write_text("\n".join(novas_linhas) + "\n", encoding="utf-8")
    else:
        # Categoria nova -> cria no final
        with open(CAMINHO_MEMORIA, "a", encoding="utf-8") as f:
            f.write(f"\n## {categoria}\n- {texto_novo}\n")

    return "salvo"
