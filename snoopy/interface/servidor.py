"""
Servidor da Interface Gráfica do Snoopy
FastAPI + WebSocket para comunicação em tempo real com a interface web.
Permite: botão de falar (push-to-talk), digitar texto, e ouvir as respostas.
"""

import asyncio
import json
import base64
from pathlib import Path
from typing import Optional

from ..utils.logger import obter_logger

logger = obter_logger("interface.servidor")


class ServidorInterface:
    """
    Servidor web local que serve a interface e conecta ao núcleo do Snoopy.
    Acesse em http://localhost:8000
    """

    def __init__(self, nucleo, porta: int = 8000):
        self.nucleo = nucleo
        self.porta = porta
        self.app = None
        self._conexoes = []
        self._dir_web = Path(__file__).parent / "web"

    def criar_app(self):
        try:
            from fastapi import FastAPI, WebSocket, WebSocketDisconnect
            from fastapi.responses import HTMLResponse, FileResponse
            from fastapi.staticfiles import StaticFiles
        except ImportError:
            raise RuntimeError(
                "FastAPI não instalado. Execute:\n"
                "pip install fastapi uvicorn[standard] python-multipart"
            )

        app = FastAPI(title="Snoopy")

        @app.get("/")
        async def index():
            html = (self._dir_web / "index.html").read_text(encoding="utf-8")
            return HTMLResponse(html)

        @app.websocket("/ws")
        async def websocket_endpoint(websocket: WebSocket):
            await websocket.accept()
            self._conexoes.append(websocket)
            logger.info("Cliente da interface conectado")
            try:
                while True:
                    dados = await websocket.receive_json()
                    await self._processar_mensagem_ws(websocket, dados)
            except WebSocketDisconnect:
                self._conexoes.remove(websocket)
                logger.info("Cliente da interface desconectado")

        @app.post("/api/texto")
        async def api_texto(payload: dict):
            """Recebe texto digitado e retorna a resposta do Snoopy."""
            texto = payload.get("texto", "")
            resposta = await self.nucleo.processar_para_interface(texto)
            return {"resposta": resposta}

        self.app = app
        return app

    async def _processar_mensagem_ws(self, websocket, dados: dict):
        """Processa mensagens recebidas via WebSocket."""
        tipo = dados.get("tipo")

        if tipo == "texto":
            texto = dados.get("conteudo", "")
            await self._enviar(websocket, {"tipo": "status", "conteudo": "pensando"})
            resposta = await self.nucleo.processar_para_interface(texto)
            await self._enviar(websocket, {"tipo": "resposta", "conteudo": resposta})

        elif tipo == "audio":
            # Áudio gravado no navegador (base64) → transcreve → processa
            audio_b64 = dados.get("conteudo", "")
            await self._enviar(websocket, {"tipo": "status", "conteudo": "ouvindo"})
            texto = await self.nucleo.transcrever_audio_interface(audio_b64)
            if texto:
                await self._enviar(websocket, {"tipo": "transcricao", "conteudo": texto})
                await self._enviar(websocket, {"tipo": "status", "conteudo": "pensando"})
                resposta = await self.nucleo.processar_para_interface(texto)
                await self._enviar(websocket, {"tipo": "resposta", "conteudo": resposta})
            else:
                await self._enviar(websocket, {
                    "tipo": "erro", "conteudo": "Não entendi o áudio."
                })

    async def _enviar(self, websocket, dados: dict):
        try:
            await websocket.send_json(dados)
        except Exception as e:
            logger.error(f"Erro ao enviar via WS: {e}")

    async def transmitir(self, dados: dict):
        """Envia uma mensagem para todas as interfaces conectadas."""
        for ws in self._conexoes[:]:
            await self._enviar(ws, dados)

    async def iniciar(self):
        """Inicia o servidor web."""
        import uvicorn
        self.criar_app()
        config = uvicorn.Config(
            self.app, host="127.0.0.1", port=self.porta, log_level="warning"
        )
        servidor = uvicorn.Server(config)
        logger.info(f"🌐 Interface disponível em http://localhost:{self.porta}")
        print(f"\n🌐 Abra a interface em: http://localhost:{self.porta}\n")
        await servidor.serve()
