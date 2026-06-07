"""
Módulo de Processamento de IA
Conecta ao Ollama ou LM Studio para rodar LLMs localmente.
Suporta: Llama 3, Mistral, Phi-3, Gemma, entre outros.
"""

import asyncio
import json
import httpx
from typing import Optional, List, Dict, Any

from ..utils.logger import obter_logger
from ..utils.config import Configuracao
from ..memoria.gerenciador_memoria import GerenciadorMemoria

logger = obter_logger("ia.processador")


PROMPT_SISTEMA = """Você é Snoopy, um assistente pessoal inteligente que roda 100% offline no computador do usuário.

Características do seu comportamento:
- Responda SEMPRE em português brasileiro
- Seja direto, amigável e útil
- Adapte o tom ao contexto: técnico para código, encorajador para bem-estar, prático para tarefas
- Você tem memória das conversas anteriores e aprende as preferências do usuário
- Quando receber contexto de memória relevante, use-o naturalmente na resposta
- Seja conciso em respostas de voz (2-3 frases no máximo para respostas faladas)
- Para tarefas complexas executadas em segundo plano, confirme e atualize o progresso

Você NÃO tem acesso à internet (a menos que uma ferramenta de busca seja disponibilizada).
Todos os dados ficam no computador do usuário — privacidade total.

Data e hora atual: {data_hora}
"""


class ProcessadorIA:
    """
    Processador de IA que se comunica com backends LLM locais.
    
    Backends suportados:
    - Ollama (http://localhost:11434) — recomendado
    - LM Studio (http://localhost:1234) — compatível com OpenAI API
    - llama.cpp server (http://localhost:8080)
    """

    BACKENDS = {
        "ollama": {
            "url_base": "http://localhost:11434",
            "endpoint_chat": "/api/chat",
            "endpoint_modelos": "/api/tags",
        },
        "lm_studio": {
            "url_base": "http://localhost:1234",
            "endpoint_chat": "/v1/chat/completions",
            "endpoint_modelos": "/v1/models",
        },
        "openai_compativel": {
            "url_base": "http://localhost:8080",
            "endpoint_chat": "/v1/chat/completions",
            "endpoint_modelos": "/v1/models",
        }
    }

    def __init__(self, config: Configuracao, memoria: GerenciadorMemoria):
        self.config = config
        self.memoria = memoria
        self.backend = config.get("ia_backend", "ollama")
        self.modelo = config.get("ia_modelo", "llama3.2:3b")
        self.temperatura = config.get("ia_temperatura", 0.7)
        self.max_tokens = config.get("ia_max_tokens", 512)
        self._cliente_http: Optional[httpx.AsyncClient] = None

    async def inicializar(self):
        """Verifica a conexão com o backend e carrega o modelo."""
        self._cliente_http = httpx.AsyncClient(timeout=120.0)
        info = self.BACKENDS.get(self.backend, self.BACKENDS["ollama"])
        self._url_base = self.config.get("ia_url_base", info["url_base"])
        self._endpoint_chat = info["endpoint_chat"]

        logger.info(
            f"Conectando ao backend IA: {self.backend} "
            f"({self._url_base}) — modelo: {self.modelo}"
        )

        disponivel = await self._verificar_backend()
        if not disponivel:
            raise RuntimeError(
                f"Backend de IA '{self.backend}' não está disponível em {self._url_base}.\n"
                f"Para Ollama: certifique-se que está rodando ('ollama serve')\n"
                f"Para LM Studio: ative o servidor local nas configurações"
            )

        logger.info(f"✅ Backend de IA conectado: {self.backend} / {self.modelo}")

    async def _verificar_backend(self) -> bool:
        """Verifica se o backend está rodando."""
        info = self.BACKENDS.get(self.backend, self.BACKENDS["ollama"])
        try:
            resp = await self._cliente_http.get(
                f"{self._url_base}{info['endpoint_modelos']}",
                timeout=5.0
            )
            return resp.status_code == 200
        except Exception:
            return False

    async def processar(
        self,
        mensagem: str,
        contexto: List[Dict[str, str]],
        intencao: Optional[Dict] = None
    ) -> str:
        """
        Processa uma mensagem e retorna a resposta do LLM.
        
        1. Busca memórias relevantes
        2. Monta o prompt com contexto e memórias
        3. Envia ao LLM local
        4. Salva a interação na memória
        """
        from datetime import datetime

        # Busca memórias relevantes para enriquecer o contexto
        memorias_relevantes = await self.memoria.buscar_relevantes(
            mensagem, limite=3
        )

        # Monta o prompt de sistema
        agora = datetime.now().strftime("%d/%m/%Y %H:%M")
        sistema = PROMPT_SISTEMA.format(data_hora=agora)

        if memorias_relevantes:
            bloco_memoria = "\n".join(
                f"- {m['conteudo']}" for m in memorias_relevantes
            )
            sistema += f"\n\nMemórias relevantes sobre o usuário:\n{bloco_memoria}"

        # Converte o contexto para o formato de mensagens
        mensagens = self._montar_mensagens(sistema, contexto, mensagem)

        # Chama o LLM
        resposta = await self._chamar_llm(mensagens)

        # Salva na memória de longo prazo
        await self.memoria.salvar_conversa(pergunta=mensagem, resposta=resposta)

        return resposta

    def _montar_mensagens(
        self,
        sistema: str,
        contexto: List[Dict],
        mensagem_atual: str
    ) -> List[Dict]:
        """Monta a lista de mensagens no formato esperado pelo LLM."""
        mensagens = [{"role": "system", "content": sistema}]

        # Adiciona o histórico recente
        for item in contexto[:-1]:  # Exclui a mensagem atual (já está em contexto)
            papel = "user" if item["papel"] == "usuario" else "assistant"
            mensagens.append({
                "role": papel,
                "content": item["conteudo"]
            })

        # Mensagem atual
        mensagens.append({"role": "user", "content": mensagem_atual})
        return mensagens

    async def _chamar_llm(self, mensagens: List[Dict]) -> str:
        """Faz a chamada HTTP ao LLM local."""
        if self.backend == "ollama":
            return await self._chamar_ollama(mensagens)
        else:
            return await self._chamar_openai_compativel(mensagens)

    async def _chamar_ollama(self, mensagens: List[Dict]) -> str:
        """Chama a API do Ollama."""
        payload = {
            "model": self.modelo,
            "messages": mensagens,
            "stream": False,
            "options": {
                "temperature": self.temperatura,
                "num_predict": self.max_tokens,
            }
        }
        try:
            resp = await self._cliente_http.post(
                f"{self._url_base}{self._endpoint_chat}",
                json=payload,
                timeout=120.0
            )
            resp.raise_for_status()
            dados = resp.json()
            return dados["message"]["content"].strip()
        except httpx.TimeoutException:
            logger.error("Timeout ao chamar o Ollama. O modelo pode estar lento.")
            return "Desculpe, o processamento demorou mais que o esperado. Pode repetir?"
        except Exception as e:
            logger.error(f"Erro ao chamar Ollama: {e}")
            return "Ocorreu um erro ao processar sua mensagem. Verifique o backend de IA."

    async def _chamar_openai_compativel(self, mensagens: List[Dict]) -> str:
        """Chama um backend compatível com a API OpenAI (LM Studio, llama.cpp)."""
        payload = {
            "model": self.modelo,
            "messages": mensagens,
            "temperature": self.temperatura,
            "max_tokens": self.max_tokens,
            "stream": False
        }
        try:
            resp = await self._cliente_http.post(
                f"{self._url_base}{self._endpoint_chat}",
                json=payload,
                timeout=120.0
            )
            resp.raise_for_status()
            dados = resp.json()
            return dados["choices"][0]["message"]["content"].strip()
        except Exception as e:
            logger.error(f"Erro ao chamar backend OpenAI-compatível: {e}")
            return "Erro ao processar. Verifique se o servidor de IA está ativo."

    async def processar_tarefa_background(
        self,
        descricao: str,
        contexto: List[Dict]
    ) -> str:
        """
        Processa uma tarefa complexa para execução em segundo plano.
        Usa um prompt específico para geração de planos e resultados detalhados.
        """
        from datetime import datetime

        agora = datetime.now().strftime("%d/%m/%Y %H:%M")
        sistema_tarefa = (
            f"{PROMPT_SISTEMA.format(data_hora=agora)}\n\n"
            "Você está executando uma tarefa em segundo plano. "
            "Forneça um resultado detalhado e estruturado. "
            "Seja completo e útil, pois o usuário não está esperando imediatamente."
        )

        mensagens = [
            {"role": "system", "content": sistema_tarefa},
            {"role": "user", "content": f"Execute esta tarefa: {descricao}"}
        ]

        return await self._chamar_llm(mensagens)

    async def fechar(self):
        """Encerra o cliente HTTP."""
        if self._cliente_http:
            await self._cliente_http.aclose()
