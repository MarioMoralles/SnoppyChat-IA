"""
Utilitário de logging centralizado para o Snoopy.
"""

import logging
import sys
from pathlib import Path

LOG_DIR = Path.home() / ".local" / "share" / "snoopy" / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)

_configurado = False


def _configurar_logging():
    global _configurado
    if _configurado:
        return
    _configurado = True

    formato = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    formato_data = "%H:%M:%S"

    logging.basicConfig(
        level=logging.INFO,
        format=formato,
        datefmt=formato_data,
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler(
                LOG_DIR / "snoopy.log",
                encoding="utf-8",
                mode="a"
            )
        ]
    )


def obter_logger(nome: str) -> logging.Logger:
    """Retorna um logger configurado para o módulo especificado."""
    _configurar_logging()
    return logging.getLogger(f"snoopy.{nome}")
