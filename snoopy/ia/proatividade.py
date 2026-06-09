"""
Módulo de Proatividade (estilo Jarvis)
Decide quando o Snoopy deve oferecer uma sugestão útil além de só responder.
Ex: você pergunta as horas → ele responde E pergunta se quer agendar algo.

A chave é NÃO ser irritante: só sugere quando há um gancho real.
"""

import re
from datetime import datetime
from typing import Optional, Dict, List

from ..utils.logger import obter_logger

logger = obter_logger("ia.proatividade")


# Ganchos que disparam sugestões proativas
GANCHOS = {
    "horario": {
        "padroes": [r"que horas", r"horário", r"que dia", r"data de hoje"],
        "sugestao": "Quer que eu agende algum lembrete ou compromisso?",
    },
    "trabalho": {
        "padroes": [r"reunião", r"trabalho", r"projeto", r"prazo", r"entrega"],
        "sugestao": "Posso criar um lembrete ou anotar isso na sua memória, se ajudar.",
    },
    "arquivo": {
        "padroes": [r"arquivo", r"pasta", r"documento", r"download"],
        "sugestao": "Se quiser, posso organizar essa pasta ou criar um relatório.",
    },
    "estudo": {
        "padroes": [r"estudar", r"aprender", r"curso", r"livro", r"ler"],
        "sugestao": "Quer que eu salve isso nos seus aprendizados para revisitar depois?",
    },
    "cansaco": {
        "padroes": [r"cansado", r"exausto", r"estressado", r"sem energia"],
        "sugestao": "Que tal uma pausa? Posso te lembrar de voltar daqui a pouco.",
    },
}


class MotorProatividade:
    """
    Avalia o contexto e sugere ações úteis quando faz sentido.
    """

    def __init__(self, config):
        self.config = config
        self.ativo = config.get("proatividade_ativa", True)
        self.frequencia = config.get("proatividade_frequencia", 0.5)  # 0=nunca, 1=sempre
        self._compilados = {
            nome: [re.compile(p, re.IGNORECASE) for p in info["padroes"]]
            for nome, info in GANCHOS.items()
        }
        self._ultima_sugestao_turno = -10
        self._turno_atual = 0

    def avaliar(self, texto_usuario: str, resposta_ia: str) -> Optional[str]:
        """
        Decide se deve adicionar uma sugestão proativa.
        Retorna a sugestão (string) ou None.
        """
        self._turno_atual += 1

        if not self.ativo:
            return None

        # Não sugere em turnos seguidos (evita encher o saco)
        if self._turno_atual - self._ultima_sugestao_turno < 3:
            return None

        # Procura um gancho no texto do usuário
        for nome, padroes in self._compilados.items():
            for padrao in padroes:
                if padrao.search(texto_usuario):
                    self._ultima_sugestao_turno = self._turno_atual
                    sugestao = GANCHOS[nome]["sugestao"]
                    logger.info(f"💡 Sugestão proativa ({nome})")
                    return sugestao

        return None

    def montar_instrucao_prompt(self) -> str:
        """Instrução adicionada ao prompt do sistema para tom proativo."""
        if not self.ativo:
            return ""
        return (
            "\n\nSeja levemente proativo, no estilo de um assistente atencioso: "
            "depois de responder à pergunta principal, quando fizer sentido, "
            "ofereça UMA ação ou sugestão útil e relacionada (curta). "
            "Não force — se não houver nada útil a sugerir, apenas responda normalmente. "
            "Nunca faça mais de uma sugestão por vez."
        )
