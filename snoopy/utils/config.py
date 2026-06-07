"""
Gerenciador de Configuração
Carrega e salva configurações do arquivo config.json
"""

import json
from pathlib import Path
from typing import Any, Dict

CONFIG_PADRAO = {
    # IA
    "ia_backend": "ollama",          # "ollama" | "lm_studio" | "openai_compativel"
    "ia_modelo": "llama3.2:3b",      # Modelo Ollama a usar
    "ia_url_base": "http://localhost:11434",
    "ia_temperatura": 0.7,
    "ia_max_tokens": 512,

    # Voz / STT
    "whisper_modelo": "base",        # "tiny" | "base" | "small" | "medium"
    "whisper_idioma": "pt",
    "audio_taxa_amostragem": 16000,
    "audio_tamanho_chunk": 1024,
    "audio_limiar_silencio": 0.01,
    "audio_duracao_silencio_seg": 1.5,
    "audio_duracao_max_frase_seg": 15,

    # TTS
    "tts_motor": "piper",            # "piper" | "pyttsx3"
    "tts_voz_piper": "pt_BR-faber-medium",
    "tts_velocidade": 1.0,

    # Memória
    "max_contexto_conversa": 10,

    # Ditado
    "ditado_tecla_atalho": "ctrl+alt",
    "ditado_remover_preenchimento": True,

    # Geral
    "nome_assistente": "Snoopy",
    "palavra_ativacao": "snoopy",
    "idioma": "pt-BR",
}


class Configuracao:
    """Gerenciador de configuração baseado em arquivo JSON."""

    DIR_CONFIG = Path.home() / ".config" / "snoopy"
    ARQUIVO_CONFIG = DIR_CONFIG / "config.json"

    def __init__(self, dados: Dict):
        self._dados = dados

    @classmethod
    def carregar(cls) -> "Configuracao":
        """Carrega as configurações do arquivo, criando se não existir."""
        cls.DIR_CONFIG.mkdir(parents=True, exist_ok=True)

        if cls.ARQUIVO_CONFIG.exists():
            with open(cls.ARQUIVO_CONFIG, "r", encoding="utf-8") as f:
                dados_salvos = json.load(f)
            # Mescla com padrões (novos campos adicionados em updates)
            config = {**CONFIG_PADRAO, **dados_salvos}
        else:
            config = CONFIG_PADRAO.copy()
            # Salva o arquivo padrão
            with open(cls.ARQUIVO_CONFIG, "w", encoding="utf-8") as f:
                json.dump(config, f, ensure_ascii=False, indent=2)

        return cls(config)

    def get(self, chave: str, padrao: Any = None) -> Any:
        """Obtém um valor de configuração."""
        return self._dados.get(chave, padrao)

    def set(self, chave: str, valor: Any):
        """Define um valor de configuração e salva."""
        self._dados[chave] = valor
        self.salvar()

    def salvar(self):
        """Salva as configurações no arquivo."""
        self.DIR_CONFIG.mkdir(parents=True, exist_ok=True)
        with open(self.ARQUIVO_CONFIG, "w", encoding="utf-8") as f:
            json.dump(self._dados, f, ensure_ascii=False, indent=2)

    def todos(self) -> Dict:
        """Retorna todas as configurações."""
        return self._dados.copy()
