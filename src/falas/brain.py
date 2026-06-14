from escrever_memoria import salvar_na_memoria, ler_memoria_completa, ja_existe

# ---------------------------------------------------------------
# 🔍 DETECÇÃO AUTOMÁTICA: o que vale a pena memorizar sozinho?
# ---------------------------------------------------------------

# Gatilhos: se a frase tiver essas palavras, é importante!
GATILHOS = {
    "Projetos": ["projeto", "estou criando", "estou fazendo", "desenvolvendo", "snoppy"],
    "Gostos":   ["eu gosto", "eu amo", "meu favorito", "prefiro", "adoro", "odeio", "não gosto"],
    "Tarefas":  ["preciso", "tenho que", "lembre-se", "lembra de", "não esqueça", "anota"],
    "Pessoal":  ["meu nome é", "eu moro", "eu trabalho", "minha idade", "eu sou"],
}

# Comando explícito: quando VOCÊ manda salvar
COMANDOS_SALVAR = ["lembre-se", "lembra disso", "anota", "guarda isso", "memoriza", "não esqueça"]


def classificar(texto):
    """Decide se deve salvar e em qual categoria. Retorna (deve_salvar, categoria)."""
    texto_low = texto.lower()

    for categoria, palavras in GATILHOS.items():
        for palavra in palavras:
            if palavra in texto_low:
                return True, categoria

    return False, None


def processar_mensagem(texto):
    """Cérebro: analisa a fala do Mario e salva automaticamente o que for relevante."""

    # 🛡️ Filtros de segurança: ignora "lixo"
    texto_limpo = texto.strip()

    # Ignora frases muito curtas
    if len(texto_limpo) < 5:
        return

    # Ignora comandos/respostas curtas sem valor de memória
    if texto_limpo.lower() in ["sair", "oi", "olá", "ola", "ok", "sim", "não", "nao", "valeu", "obrigado"]:
        return

    # 🔍 Classifica e decide se salva
    deve_salvar, categoria = classificar(texto_limpo)

    if deve_salvar:
        status = salvar_na_memoria(texto_limpo, categoria)
        if status == "salvo":
            print(f"   🧠 (memorizei em '{categoria}')")
        elif status == "repetido":
            print(f"   💭 (já sabia disso, não repeti)")

# ---------------------------------------------------------------
# 💬 CONVERSA PRINCIPAL
# ---------------------------------------------------------------

def iniciar():
    # 1. Snoppy LÊ a memória ao acordar
    memoria = ler_memoria_completa()
    print("=" * 50)
    print("🤖 Snoppy acordou e leu sua memória! 🧠")
    print("=" * 50)
    if memoria.strip():
        print("\n📂 O que eu lembro de você:\n")
        print(memoria)
    else:
        print("\n(memória vazia por enquanto)")
    print("=" * 50)

    print("\n💬 Pode conversar! (digite 'sair' pra encerrar)\n")

    # 2. Loop de conversa
    while True:
        entrada = input("Você: ")

        if entrada.lower() == "sair":
            print("🤖 Snoppy: Tudo guardado! Até logo, Mario! 👋")
            break

        # 3. Cérebro processa e decide se salva sozinho
        processar_mensagem(entrada)

        # (Aqui depois entra a resposta da IA de verdade)
        print("🤖 Snoppy: Entendi! 😊\n")


if __name__ == "__main__":
    iniciar()
