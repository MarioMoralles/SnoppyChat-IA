"""
Script auxiliar para baixar vozes do Piper TTS.
Uso: python scripts/baixar_voz_piper.py --voz pt_BR-faber-medium
"""

import argparse
import urllib.request
from pathlib import Path


VOZES_DISPONIVEIS = {
    "pt_BR-faber-medium": {
        "descricao": "Português BR - Faber (masculino, média qualidade) — recomendado",
        "tamanho": "~63MB"
    },
    "pt_BR-edresson-low": {
        "descricao": "Português BR - Edresson (masculino, baixa qualidade, mais rápido)",
        "tamanho": "~28MB"
    },
}

URL_BASE = (
    "https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/pt/pt_BR"
)

DIR_VOZES = Path.home() / ".cache" / "snoopy" / "piper"


def baixar_voz(nome_voz: str):
    DIR_VOZES.mkdir(parents=True, exist_ok=True)

    # Mapeia nome da voz para o caminho no HuggingFace
    partes = nome_voz.split("-")  # ex: pt_BR-faber-medium -> ["pt_BR", "faber", "medium"]
    if len(partes) < 3:
        print(f"❌ Nome de voz inválido: {nome_voz}")
        return

    locutor = partes[1]
    qualidade = partes[2]
    caminho_hf = f"/{locutor}/{qualidade}/{nome_voz}"

    arquivos = [
        (f"{URL_BASE}{caminho_hf}.onnx", DIR_VOZES / f"{nome_voz}.onnx"),
        (f"{URL_BASE}{caminho_hf}.onnx.json", DIR_VOZES / f"{nome_voz}.onnx.json"),
    ]

    for url, destino in arquivos:
        if destino.exists():
            print(f"✅ Já existe: {destino.name}")
            continue

        print(f"⬇️  Baixando {destino.name}...")
        print(f"   URL: {url}")

        try:
            def mostrar_progresso(contagem, tam_bloco, tam_total):
                if tam_total > 0:
                    pct = min(100, contagem * tam_bloco * 100 // tam_total)
                    print(f"\r   Progresso: {pct}%", end="", flush=True)

            urllib.request.urlretrieve(url, destino, reporthook=mostrar_progresso)
            print(f"\n✅ Salvo em: {destino}")
        except Exception as e:
            print(f"\n❌ Erro ao baixar {destino.name}: {e}")
            print("   Verifique sua conexão com a internet.")
            print(
                "   Lembre-se: este download é apenas na primeira instalação.\n"
                "   Depois, o Piper funciona 100% offline."
            )


def main():
    parser = argparse.ArgumentParser(
        description="Baixa vozes do Piper TTS para uso offline"
    )
    parser.add_argument(
        "--voz",
        default="pt_BR-faber-medium",
        help="Nome da voz a baixar (padrão: pt_BR-faber-medium)"
    )
    parser.add_argument(
        "--listar",
        action="store_true",
        help="Lista vozes disponíveis"
    )
    args = parser.parse_args()

    if args.listar:
        print("\n🔊 Vozes disponíveis para Piper TTS:\n")
        for nome, info in VOZES_DISPONIVEIS.items():
            print(f"  {nome}")
            print(f"    {info['descricao']}")
            print(f"    Tamanho: {info['tamanho']}\n")
        return

    print(f"\n🔊 Baixando voz Piper: {args.voz}")
    info = VOZES_DISPONIVEIS.get(args.voz)
    if info:
        print(f"   {info['descricao']}")
        print(f"   Tamanho: {info['tamanho']}\n")

    baixar_voz(args.voz)

    print(
        f"\n✅ Concluído! A voz '{args.voz}' está pronta para uso offline.\n"
        f"   Localização: {DIR_VOZES}\n"
    )


if __name__ == "__main__":
    main()
