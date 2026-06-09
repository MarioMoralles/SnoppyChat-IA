"""
Snoopy - Assistente Pessoal de IA 100% Local
Ponto de entrada principal
"""

import asyncio
import sys
import signal
import argparse
from pathlib import Path

# Adiciona o diretório raiz ao path
sys.path.insert(0, str(Path(__file__).parent))

from snoopy.nucleo import Snoopy
from snoopy.utils.logger import obter_logger

logger = obter_logger("main")


def configurar_argumentos():
    parser = argparse.ArgumentParser(
        description="Snoopy - Assistente Pessoal de IA Local",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemplos de uso:
  python main.py                    # Modo voz (padrão)
  python main.py --modo texto       # Modo texto no terminal
  python main.py --modo ditado      # Modo ditado (tecla de atalho)
  python main.py --configurar       # Abre assistente de configuração
        """
    )
    parser.add_argument(
        "--modo",
        choices=["voz", "texto", "ditado", "interface"],
        default="voz",
        help="Modo de interação (padrão: voz). 'interface' abre a interface gráfica web."
    )
    parser.add_argument(
        "--configurar",
        action="store_true",
        help="Abre o assistente de configuração interativo"
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Ativa logs detalhados para depuração"
    )
    parser.add_argument(
        "--sem-voz",
        action="store_true",
        help="Desativa saída de voz (apenas texto)"
    )
    return parser.parse_args()


async def main():
    args = configurar_argumentos()

    if args.debug:
        import logging
        logging.getLogger("snoopy").setLevel(logging.DEBUG)

    print("""
╔══════════════════════════════════════════════════════╗
║          🐾  SNOOPY - Assistente Pessoal IA          ║
║          100% Local  •  100% Privado                 ║
╚══════════════════════════════════════════════════════╝
    """)

    if args.configurar:
        from snoopy.utils.configurador import AssistenteConfiguracao
        configurador = AssistenteConfiguracao()
        await configurador.executar()
        return

    # Inicializa o assistente principal
    snoopy = Snoopy(
        modo=args.modo,
        sem_voz=args.sem_voz
    )

    # Captura CTRL+C e SIGTERM para encerrar graciosamente
    loop = asyncio.get_event_loop()

    def encerrar(signum, frame):
        logger.info("Sinal de encerramento recebido. Finalizando Snoopy...")
        loop.create_task(snoopy.encerrar())

    signal.signal(signal.SIGINT, encerrar)
    signal.signal(signal.SIGTERM, encerrar)

    await snoopy.iniciar()


if __name__ == "__main__":
    asyncio.run(main())
