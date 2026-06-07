"""
Gerenciador de Tarefas em Segundo Plano
Executa tarefas pesadas de forma assíncrona, notificando o usuário ao concluir.
"""

import asyncio
import uuid
from enum import Enum
from dataclasses import dataclass, field
from datetime import datetime
from typing import Callable, Dict, List, Optional, Any

from ..utils.logger import obter_logger
from ..utils.config import Configuracao

logger = obter_logger("automacao.tarefas")


class StatusTarefa(Enum):
    PENDENTE = "pendente"
    EXECUTANDO = "executando"
    CONCLUIDA = "concluída"
    FALHOU = "falhou"
    CANCELADA = "cancelada"


@dataclass
class Tarefa:
    id: int
    descricao: str
    contexto: List[Dict]
    status: StatusTarefa = StatusTarefa.PENDENTE
    resultado: Optional[str] = None
    erro: Optional[str] = None
    criada_em: datetime = field(default_factory=datetime.now)
    concluida_em: Optional[datetime] = None
    tipo: str = "ia"  # "ia", "sistema", "arquivo", "web"


class GerenciadorTarefas:
    """
    Gerencia tarefas executadas em segundo plano.
    
    - Aceita tarefas via agendar()
    - Executa de forma assíncrona com concorrência controlada
    - Notifica via callback quando uma tarefa é concluída
    - Mantém histórico de tarefas
    """

    MAX_TAREFAS_SIMULTANEAS = 3

    def __init__(
        self,
        processador_ia=None,
        callback_notificacao: Optional[Callable] = None
    ):
        self.processador_ia = processador_ia
        self.callback_notificacao = callback_notificacao
        self._tarefas: Dict[int, Tarefa] = {}
        self._contador_id = 0
        self._semaforo: Optional[asyncio.Semaphore] = None
        self._fila: Optional[asyncio.Queue] = None
        self._workers: List[asyncio.Task] = []
        self._ativo = False

    async def inicializar(self):
        """Inicializa o gerenciador de tarefas."""
        self._semaforo = asyncio.Semaphore(self.MAX_TAREFAS_SIMULTANEAS)
        self._fila = asyncio.Queue()
        self._ativo = True

        # Inicia workers
        for i in range(self.MAX_TAREFAS_SIMULTANEAS):
            worker = asyncio.create_task(
                self._worker(f"worker-{i+1}"),
                name=f"snoopy-tarefa-worker-{i+1}"
            )
            self._workers.append(worker)

        logger.info(
            f"Gerenciador de tarefas iniciado "
            f"({self.MAX_TAREFAS_SIMULTANEAS} workers)"
        )

    async def agendar(
        self,
        descricao: str,
        contexto: Optional[List[Dict]] = None,
        tipo: str = "ia"
    ) -> int:
        """
        Agenda uma nova tarefa para execução em segundo plano.
        
        Retorna o ID da tarefa.
        """
        self._contador_id += 1
        tarefa = Tarefa(
            id=self._contador_id,
            descricao=descricao,
            contexto=contexto or [],
            tipo=tipo
        )
        self._tarefas[tarefa.id] = tarefa
        await self._fila.put(tarefa)

        logger.info(f"Tarefa #{tarefa.id} agendada: '{descricao[:60]}...'")
        return tarefa.id

    async def _worker(self, nome: str):
        """Worker que consome e executa tarefas da fila."""
        logger.debug(f"Worker '{nome}' iniciado")
        while self._ativo:
            try:
                tarefa = await asyncio.wait_for(
                    self._fila.get(), timeout=1.0
                )
            except asyncio.TimeoutError:
                continue

            async with self._semaforo:
                await self._executar_tarefa(tarefa)
                self._fila.task_done()

    async def _executar_tarefa(self, tarefa: Tarefa):
        """Executa uma tarefa e notifica ao concluir."""
        tarefa.status = StatusTarefa.EXECUTANDO
        logger.info(f"⚙️  Executando tarefa #{tarefa.id}: {tarefa.descricao[:50]}")

        try:
            if tarefa.tipo == "ia":
                resultado = await self._executar_tarefa_ia(tarefa)
            elif tarefa.tipo == "sistema":
                resultado = await self._executar_tarefa_sistema(tarefa)
            else:
                resultado = await self._executar_tarefa_ia(tarefa)

            tarefa.resultado = resultado
            tarefa.status = StatusTarefa.CONCLUIDA
            tarefa.concluida_em = datetime.now()

            logger.info(f"✅ Tarefa #{tarefa.id} concluída")

            if self.callback_notificacao:
                await self.callback_notificacao(tarefa.id, resultado)

        except asyncio.CancelledError:
            tarefa.status = StatusTarefa.CANCELADA
            logger.info(f"Tarefa #{tarefa.id} cancelada")
        except Exception as e:
            tarefa.status = StatusTarefa.FALHOU
            tarefa.erro = str(e)
            logger.error(f"Tarefa #{tarefa.id} falhou: {e}")

            if self.callback_notificacao:
                await self.callback_notificacao(
                    tarefa.id,
                    f"Infelizmente a tarefa falhou: {str(e)}"
                )

    async def _executar_tarefa_ia(self, tarefa: Tarefa) -> str:
        """Executa uma tarefa usando o processador de IA."""
        if not self.processador_ia:
            return "Processador de IA não disponível."

        return await self.processador_ia.processar_tarefa_background(
            descricao=tarefa.descricao,
            contexto=tarefa.contexto
        )

    async def _executar_tarefa_sistema(self, tarefa: Tarefa) -> str:
        """Executa um comando de sistema operacional."""
        import shlex
        cmd = shlex.split(tarefa.descricao)
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await proc.communicate()
        if proc.returncode == 0:
            return stdout.decode("utf-8").strip() or "Comando executado com sucesso."
        else:
            raise RuntimeError(stderr.decode("utf-8").strip())

    def obter_tarefa(self, id_tarefa: int) -> Optional[Tarefa]:
        """Retorna uma tarefa pelo ID."""
        return self._tarefas.get(id_tarefa)

    def listar_tarefas(self, status: Optional[StatusTarefa] = None) -> List[Tarefa]:
        """Lista todas as tarefas, opcionalmente filtradas por status."""
        tarefas = list(self._tarefas.values())
        if status:
            tarefas = [t for t in tarefas if t.status == status]
        return sorted(tarefas, key=lambda t: t.criada_em, reverse=True)

    async def cancelar_tarefa(self, id_tarefa: int) -> bool:
        """Tenta cancelar uma tarefa pendente."""
        tarefa = self._tarefas.get(id_tarefa)
        if tarefa and tarefa.status == StatusTarefa.PENDENTE:
            tarefa.status = StatusTarefa.CANCELADA
            logger.info(f"Tarefa #{id_tarefa} cancelada pelo usuário")
            return True
        return False

    async def encerrar(self):
        """Encerra o gerenciador e aguarda as tarefas em andamento."""
        self._ativo = False
        logger.info("Aguardando tarefas em andamento concluírem...")

        for worker in self._workers:
            worker.cancel()

        await asyncio.gather(*self._workers, return_exceptions=True)
        logger.info("Gerenciador de tarefas encerrado")
