"""
Módulo de Processamento de IA — com Tool Calling, Streaming e Memória Semântica
Conecta ao Ollama/LM Studio para rodar LLMs localmente.
"""

import asyncio
import json
import re
import httpx
from typing import Optional, List, Dict, Any, Callable

from ..utils.logger import obter_logger
from ..utils.config import Configuracao

logger = obter_logger("ia.processador")


PROMPT_SISTEMA = """Você é Snoopy, um assistente pessoal inteligente que roda 100% offline no computador do usuário.

Comportamento:
- Responda SEMPRE em português brasileiro
- Seja amigável, natural e útil — como um bom assistente pessoal
- Adapte o tom: técnico para código, prático para tarefas, leve para conversa
- Use a memória e o contexto que receber para personalizar respostas
- Em respostas de voz, seja conciso (2-3 frases)

Data e hora atual: {data_hora}
{bloco_ferramentas}
{bloco_proatividade}
"""


class ProcessadorIA:
    """Processador de IA com suporte a ferramentas, streaming e memória semântica."""

    def __init__(self, config: Configuracao, memoria, caixa_ferramentas=None,
                 embeddings=None, proatividade=None):
        self.config = config
        self.memoria = memoria
        self.caixa_ferramentas = caixa_ferramentas
        self.embeddings = embeddings
        self.proatividade = proatividade

        self.backend = config.get("ia_backend", "ollama")
        self.modelo = config.get("ia_modelo", "llama3.2:3b")
        self.temperatura = config.get("ia_temperatura", 0.7)
        self.max_tokens = config.get("ia_max_tokens", 512)
        self._cliente_http: Optional[httpx.AsyncClient] = None
        self._url_base = config.get("ia_url_base", "http://localhost:11434")

    async def inicializar(self):
        self._cliente_http = httpx.AsyncClient(timeout=120.0)
        if self.backend == "ollama":
            self._endpoint_chat = "/api/chat"
            endpoint_modelos = "/api/tags"
        else:
            self._endpoint_chat = "/v1/chat/completions"
            endpoint_modelos = "/v1/models"

        logger.info(f"Conectando ao backend IA: {self.backend} ({self._url_base}) — modelo: {self.modelo}")
        try:
            resp = await self._cliente_http.get(f"{self._url_base}{endpoint_modelos}", timeout=5.0)
            if resp.status_code != 200:
                raise RuntimeError("backend não respondeu 200")
        except Exception:
            raise RuntimeError(
                f"Backend de IA '{self.backend}' indisponível em {self._url_base}.\n"
                f"Ollama: rode 'ollama serve'. LM Studio: ative o servidor local."
            )
        logger.info(f"✅ Backend de IA conectado: {self.backend} / {self.modelo}")

    async def processar(self, mensagem: str, contexto: List[Dict],
                        intencao: Optional[Dict] = None) -> str:
        """Processa uma mensagem com memória semântica, ferramentas e proatividade."""
        from datetime import datetime

        # 1. Recupera memórias relevantes (semântica + palavra-chave)
        memorias = await self._recuperar_memorias(mensagem)

        # 2. Monta o prompt do sistema
        agora = datetime.now().strftime("%d/%m/%Y %H:%M")
        bloco_ferr = ""
        if self.caixa_ferramentas:
            bloco_ferr = (
                "\n\nVocê pode USAR FERRAMENTAS. Se a tarefa exigir uma ação no "
                "computador, responda APENAS com um JSON neste formato:\n"
                '{"ferramenta": "nome", "argumentos": {...}}\n'
                "Se for só conversa, responda normalmente em texto.\n\n"
                + self.caixa_ferramentas.descrever_para_llm()
            )
        bloco_proa = self.proatividade.montar_instrucao_prompt() if self.proatividade else ""

        sistema = PROMPT_SISTEMA.format(
            data_hora=agora, bloco_ferramentas=bloco_ferr, bloco_proatividade=bloco_proa
        )
        if memorias:
            sistema += "\n\nMemórias relevantes sobre o usuário:\n" + "\n".join(
                f"- {m}" for m in memorias
            )

        mensagens = self._montar_mensagens(sistema, contexto, mensagem)

        # 3. Chama o LLM
        resposta = await self._chamar_llm(mensagens)

        # 4. Verifica se o LLM quer usar uma ferramenta
        resposta = await self._tratar_ferramenta(resposta, mensagem)

        # 5. Adiciona sugestão proativa (se aplicável e não foi ferramenta)
        if self.proatividade:
            sugestao = self.proatividade.avaliar(mensagem, resposta)
            if sugestao and "ferramenta" not in resposta.lower():
                resposta = f"{resposta}\n\n{sugestao}"

        # 6. Salva na memória
        await self._salvar_memoria(mensagem, resposta)

        return resposta

    async def _recuperar_memorias(self, consulta: str) -> List[str]:
        """Combina busca semântica (embeddings) com busca por palavra-chave."""
        memorias = []
        if self.embeddings and self.embeddings.disponivel:
            resultados = await self.embeddings.buscar(consulta, limite=3)
            memorias.extend(r["texto"] for r in resultados)
        # Complementa com a memória SQLite tradicional
        try:
            tradicionais = await self.memoria.buscar_relevantes(consulta, limite=2)
            memorias.extend(m["conteudo"] for m in tradicionais)
        except Exception:
            pass
        # Remove duplicatas preservando ordem
        vistos = set()
        unicas = []
        for m in memorias:
            if m not in vistos:
                vistos.add(m)
                unicas.append(m)
        return unicas[:5]

    async def _tratar_ferramenta(self, resposta: str, mensagem_original: str) -> str:
        """Se a resposta for um JSON de ferramenta, executa e gera resposta final."""
        if not self.caixa_ferramentas:
            return resposta

        # Tenta extrair JSON da resposta
        match = re.search(r'\{.*"ferramenta".*\}', resposta, re.DOTALL)
        if not match:
            return resposta

        try:
            dados = json.loads(match.group(0))
            nome = dados.get("ferramenta")
            args = dados.get("argumentos", {})
            if nome not in self.caixa_ferramentas.listar_nomes():
                return resposta

            logger.info(f"🔧 LLM solicitou ferramenta: {nome}")
            resultado = await self.caixa_ferramentas.executar(nome, args)

            # Gera uma resposta natural sobre o resultado da ferramenta
            from datetime import datetime
            mensagens = [
                {"role": "system", "content":
                 "Você é Snoopy. Resuma o resultado da ação de forma natural e breve, em português."},
                {"role": "user", "content":
                 f"O usuário pediu: '{mensagem_original}'. "
                 f"Eu executei a ferramenta '{nome}' e o resultado foi: {resultado}. "
                 f"Responda ao usuário de forma natural confirmando o que foi feito."}
            ]
            return await self._chamar_llm(mensagens)
        except json.JSONDecodeError:
            return resposta
        except Exception as e:
            logger.error(f"Erro ao tratar ferramenta: {e}")
            return resposta

    async def _salvar_memoria(self, pergunta: str, resposta: str):
        """Salva a conversa na memória SQLite, semântica e Obsidian."""
        try:
            await self.memoria.salvar_conversa(pergunta=pergunta, resposta=resposta)
        except Exception as e:
            logger.debug(f"Erro ao salvar memória SQLite: {e}")
        # Indexa semanticamente
        if self.embeddings and self.embeddings.disponivel:
            try:
                await self.embeddings.indexar(
                    f"Pergunta: {pergunta} | Resposta: {resposta}",
                    metadados={"tipo": "conversa"}
                )
            except Exception as e:
                logger.debug(f"Erro ao indexar embedding: {e}")

    def _montar_mensagens(self, sistema: str, contexto: List[Dict],
                          mensagem_atual: str) -> List[Dict]:
        mensagens = [{"role": "system", "content": sistema}]
        for item in contexto[:-1]:
            papel = "user" if item["papel"] == "usuario" else "assistant"
            mensagens.append({"role": papel, "content": item["conteudo"]})
        mensagens.append({"role": "user", "content": mensagem_atual})
        return mensagens

    async def _chamar_llm(self, mensagens: List[Dict]) -> str:
        if self.backend == "ollama":
            payload = {
                "model": self.modelo, "messages": mensagens, "stream": False,
                "options": {"temperature": self.temperatura, "num_predict": self.max_tokens}
            }
            try:
                resp = await self._cliente_http.post(
                    f"{self._url_base}{self._endpoint_chat}", json=payload, timeout=120.0
                )
                resp.raise_for_status()
                return resp.json()["message"]["content"].strip()
            except httpx.TimeoutException:
                return "Desculpe, demorei demais para processar. Pode repetir?"
            except Exception as e:
                logger.error(f"Erro Ollama: {e}")
                return "Tive um erro ao processar. Verifique o backend de IA."
        else:
            payload = {
                "model": self.modelo, "messages": mensagens,
                "temperature": self.temperatura, "max_tokens": self.max_tokens, "stream": False
            }
            try:
                resp = await self._cliente_http.post(
                    f"{self._url_base}{self._endpoint_chat}", json=payload, timeout=120.0
                )
                resp.raise_for_status()
                return resp.json()["choices"][0]["message"]["content"].strip()
            except Exception as e:
                logger.error(f"Erro backend: {e}")
                return "Erro ao processar. Verifique o servidor de IA."

    async def chamar_llm_streaming(self, mensagens: List[Dict],
                                    callback_token: Callable):
        """
        Chama o LLM em modo streaming, invocando callback_token(texto) a cada
        pedaço. Permite começar a falar antes da resposta completa.
        """
        if self.backend != "ollama":
            resposta = await self._chamar_llm(mensagens)
            await callback_token(resposta)
            return resposta

        payload = {
            "model": self.modelo, "messages": mensagens, "stream": True,
            "options": {"temperature": self.temperatura, "num_predict": self.max_tokens}
        }
        completo = ""
        try:
            async with self._cliente_http.stream(
                "POST", f"{self._url_base}{self._endpoint_chat}", json=payload, timeout=120.0
            ) as resp:
                async for linha in resp.aiter_lines():
                    if not linha.strip():
                        continue
                    try:
                        dado = json.loads(linha)
                        token = dado.get("message", {}).get("content", "")
                        if token:
                            completo += token
                            await callback_token(token)
                    except json.JSONDecodeError:
                        continue
        except Exception as e:
            logger.error(f"Erro no streaming: {e}")
        return completo

    async def processar_tarefa_background(self, descricao: str, contexto: List[Dict]) -> str:
        from datetime import datetime
        agora = datetime.now().strftime("%d/%m/%Y %H:%M")
        sistema = (
            PROMPT_SISTEMA.format(data_hora=agora, bloco_ferramentas="", bloco_proatividade="")
            + "\n\nVocê está executando uma tarefa em segundo plano. "
            "Forneça um resultado completo, detalhado e bem estruturado."
        )
        mensagens = [
            {"role": "system", "content": sistema},
            {"role": "user", "content": f"Execute esta tarefa: {descricao}"}
        ]
        return await self._chamar_llm(mensagens)

    async def fechar(self):
        if self._cliente_http:
            await self._cliente_http.aclose()
