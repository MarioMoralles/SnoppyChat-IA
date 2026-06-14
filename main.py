# main.py
from src.brain import pensar

def main():
    print("🐶 Snoppy ligado! (digite 'sair' pra encerrar)\n")

    while True:
        pergunta = input("Você: ")

        if pergunta.lower() in ["sair", "exit", "quit"]:
            print("🐶 Snoppy: Até mais, Mario! 👋")
            break

        resposta = pensar(pergunta)
        print(f"🐶 Snoppy: {resposta}\n")


if __name__ == "__main__":
    main()
