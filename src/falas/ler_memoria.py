# Caminho completo até a sua nota
caminho_nota = r"C:\Users\mario\snoppy\snoppy-cerebro\Sobre Mario.md"

# Abre o arquivo e lê todo o conteúdo
with open(caminho_nota, "r", encoding="utf-8") as arquivo:
    memoria = arquivo.read()

# Mostra na tela o que o Snoppy "lembrou"
print("🧠 Snoppy lembrou disto sobre você:\n")
print(memoria)
