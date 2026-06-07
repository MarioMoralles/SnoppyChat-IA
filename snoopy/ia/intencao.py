"""
Detector de Intenção
Classifica entradas do usuário para decidir o fluxo de processamento.
Usa heurísticas rápidas para não adicionar latência.
"""

import re
from typing import Dict, List, Any

from ..utils.logger import obter_logger
from ..utils.config import Configuracao

logger = obter_logger("ia.intencao")


# Padrões de intenção por categoria
PADROES_BACKGROUND = [
    # Criação e escrita
    r"cri[ea]|escreve?|redij[ae]|faz[ae]|elabor[ae]|gere?|gera",
    r"pesquisa|analisa?|compil[ae]|organiz[ae]|list[ae]",
    r"report[ae]|relatório|resumo|sumário",
    # Código
    r"programa|código|script|desenvolv[ae]|implement[ae]|cod[iae]",
    # Tempo implícito
    r"quando puder|sem pressa|pode demorar|com calma|depois me",
    # Tarefas longas
    r"plan[ea]|estratégi[ao]|todo[s]? os? |todos (os|as)?",
]

PADROES_IMEDIATO = [
    r"que horas|que dia|como está|qual é|o que é|me diz|me fala",
    r"explica|define|significa|traduz",
    r"conta|me conta|me diga|você sabe",
    r"lembra|lembro|lembrar",
    r"olá|oi|tudo bem|tudo bom|boa tarde|bom dia|boa noite",
]

INTENCOES = {
    "saudacao": {
        "padroes": [r"olá|oi|e aí|tudo bem|tudo bom|bom dia|boa tarde|boa noite|hey|salve"],
        "tipo": "imediato"
    },
    "pergunta_rapida": {
        "padroes": [r"^(o que|qual|quem|quando|onde|como|quanto)[^.?!]{0,60}[?.]?$"],
        "tipo": "imediato"
    },
    "tarefa_codigo": {
        "padroes": [r"codi|program|script|função|classe|método|bug|erro|corri[gj]"],
        "tipo": "tarefa_background"
    },
    "tarefa_escrita": {
        "padroes": [r"escreve?|redij[ae]|cri[ae] (um|uma)|elabor|text[oa]|email|mensagem"],
        "tipo": "tarefa_background"
    },
    "tarefa_pesquisa": {
        "padroes": [r"pesquisa|busca|encontra|analisa|compila|resum[eo]"],
        "tipo": "tarefa_background"
    },
    "lembrete": {
        "padroes": [r"lembra|lembr[ae]-me|não esqueça|me avisa"],
        "tipo": "lembrete"
    },
    "memoria": {
        "padroes": [r"lembra (que|quando|de)|você sabe que|já falei|você lembra"],
        "tipo": "memoria"
    },
}


class DetectorIntencao:
    """
    Detecta a intenção de uma mensagem usando heurísticas rápidas.
    Não usa LLM para manter baixa latência.
    """

    def __init__(self, config: Configuracao):
        self.config = config
        self._padroes_compilados = self._compilar_padroes()

    def _compilar_padroes(self) -> Dict:
        """Pré-compila os padrões regex para performance."""
        compilados = {}
        for nome, info in INTENCOES.items():
            compilados[nome] = {
                "padroes": [
                    re.compile(p, re.IGNORECASE | re.UNICODE)
                    for p in info["padroes"]
                ],
                "tipo": info["tipo"]
            }
        return compilados

    async def detectar(
        self,
        texto: str,
        contexto: List[Dict]
    ) -> Dict[str, Any]:
        """
        Detecta a intenção do texto.
        
        Retorna um dicionário com:
        - tipo: "imediato" | "tarefa_background" | "lembrete" | "memoria"
        - intencao: nome da intenção detectada
        - descricao: descrição resumida para tarefas background
        - confianca: 0.0 a 1.0
        """
        texto_lower = texto.lower().strip()

        # Verifica cada categoria de intenção
        for nome, info in self._padroes_compilados.items():
            for padrao in info["padroes"]:
                if padrao.search(texto_lower):
                    resultado = {
                        "intencao": nome,
                        "tipo": info["tipo"],
                        "confianca": 0.8,
                        "descricao": texto
                    }
                    logger.debug(f"Intenção: {nome} ({info['tipo']})")
                    return resultado

        # Heurística por comprimento — textos longos tendem a ser tarefas
        palavras = texto_lower.split()
        if len(palavras) > 25:
            return {
                "intencao": "tarefa_complexa",
                "tipo": "tarefa_background",
                "confianca": 0.6,
                "descricao": texto
            }

        # Default: resposta imediata
        return {
            "intencao": "conversa",
            "tipo": "imediato",
            "confianca": 0.5,
            "descricao": texto
        }
