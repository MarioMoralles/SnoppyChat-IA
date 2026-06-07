"""
Assistente de Configuração Interativo do Snoopy
Guia o usuário pela configuração inicial via terminal.
"""

import asyncio
import httpx
from pathlib import Path

from .config import Configuracao
from .logger import obter_logger

logger = obter_logger("configurador")


class AssistenteConfiguracao:
    """Assistente de configuração passo a passo via terminal."""

    def __init__(self):
        self.config = Configuracao.carregar()

    async def executar(self):
        """Executa o fluxo completo de configuração."""
        self._cabecalho()
        await self._configurar_backend_ia()
        await self._configurar_voz_stt()
        await self._configurar_tts()
        self._configurar_geral()
        self.config.salvar()
        self._resumo()

    def _cabecalho(self):
        print("""
╔══════════════════════════════════════════════════════╗
║     🐾  SNOOPY - Assistente de Configuração          ║
╚══════════════════════════════════════════════════════╝
Vamos configurar o Snoopy passo a passo.
Pressione Enter para aceitar o valor padrão (em colchetes).
        """)

    async def _configurar_backend_ia(self):
        print("\n📦  CONFIGURAÇÃO DO MODELO DE IA")
        print("-" * 40)
        print("Backends disponíveis:")
        print("  1. Ollama (recomendado) — instale em https://ollama.com")
        print("  2. LM Studio            — instale em https://lmstudio.ai")
        print("  3. Outro (compatível com OpenAI API)")

        escolha = input("\nEscolha o backend [1]: ").strip() or "1"
        backends = {"1": "ollama", "2": "lm_studio", "3": "openai_compativel"}
        backend = backends.get(escolha, "ollama")
        self.config.set("ia_backend", backend)

        if backend == "ollama":
            url_padrao = "http://localhost:11434"
        elif backend == "lm_studio":
            url_padrao = "http://localhost:1234"
        else:
            url_padrao = "http://localhost:8080"

        url = input(f"URL do servidor [{url_padrao}]: ").strip() or url_padrao
        self.config.set("ia_url_base", url)

        # Verifica conectividade e lista modelos
        print(f"\nVerificando conexão com {url}...")
        modelos = await self._listar_modelos_ollama(url, backend)

        if modelos:
            print("✅ Conectado! Modelos disponíveis:")
            for i, m in enumerate(modelos[:8], 1):
                print(f"  {i}. {m}")

            modelo_padrao = self.config.get("ia_modelo", "llama3.2:3b")
            modelo = input(f"\nNome do modelo [{modelo_padrao}]: ").strip() or modelo_padrao
        else:
            print("⚠️  Não foi possível conectar. Configure o servidor e reinicie.")
            modelo_padrao = self.config.get("ia_modelo", "llama3.2:3b")
            modelo = input(f"Nome do modelo [{modelo_padrao}]: ").strip() or modelo_padrao

        self.config.set("ia_modelo", modelo)
        print(f"✅ IA configurada: {backend} / {modelo}")

    async def _listar_modelos_ollama(self, url: str, backend: str) -> list:
        """Tenta listar modelos disponíveis no backend."""
        try:
            async with httpx.AsyncClient(timeout=5.0) as cliente:
                if backend == "ollama":
                    resp = await cliente.get(f"{url}/api/tags")
                    if resp.status_code == 200:
                        dados = resp.json()
                        return [m["name"] for m in dados.get("models", [])]
                else:
                    resp = await cliente.get(f"{url}/v1/models")
                    if resp.status_code == 200:
                        dados = resp.json()
                        return [m["id"] for m in dados.get("data", [])]
        except Exception:
            pass
        return []

    async def _configurar_voz_stt(self):
        print("\n🎙️  CONFIGURAÇÃO DE RECONHECIMENTO DE VOZ (STT)")
        print("-" * 40)
        print("Modelos Whisper disponíveis (mais pesado = mais preciso):")
        print("  tiny   — muito rápido, menos preciso (~75MB)")
        print("  base   — equilíbrio ideal para a maioria  (~150MB)  ← recomendado")
        print("  small  — mais preciso, mais lento (~490MB)")
        print("  medium — alta precisão (~1.5GB)")

        modelo = input("\nModelo Whisper [base]: ").strip() or "base"
        self.config.set("whisper_modelo", modelo)
        print(f"✅ Whisper configurado: {modelo}")

    async def _configurar_tts(self):
        print("\n🔊  CONFIGURAÇÃO DE SÍNTESE DE VOZ (TTS)")
        print("-" * 40)
        print("Motores disponíveis:")
        print("  1. Piper TTS (recomendado) — voz neural de alta qualidade")
        print("     Instale: https://github.com/rhasspy/piper")
        print("  2. pyttsx3 — mais simples, funciona sem instalar nada extra")

        escolha = input("\nEscolha o motor [1]: ").strip() or "1"
        motor = "piper" if escolha == "1" else "pyttsx3"
        self.config.set("tts_motor", motor)

        if motor == "piper":
            voz_padrao = "pt_BR-faber-medium"
            print(f"\nVozes disponíveis para pt-BR:")
            print("  pt_BR-faber-medium (recomendada)")
            print("  pt_BR-edresson-low")
            voz = input(f"Voz Piper [{voz_padrao}]: ").strip() or voz_padrao
            self.config.set("tts_voz_piper", voz)

        print(f"✅ TTS configurado: {motor}")

    def _configurar_geral(self):
        print("\n⚙️  CONFIGURAÇÕES GERAIS")
        print("-" * 40)

        limiar_atual = self.config.get("audio_limiar_silencio", 0.01)
        print(f"Sensibilidade do microfone (limiar de silêncio)")
        print(f"  Valores menores = mais sensível (pode captar ruído)")
        print(f"  Valores maiores = menos sensível")
        limiar = input(f"Limiar [{limiar_atual}]: ").strip()
        if limiar:
            try:
                self.config.set("audio_limiar_silencio", float(limiar))
            except ValueError:
                pass

        print("✅ Configurações gerais salvas")

    def _resumo(self):
        dados = self.config.todos()
        print(f"""
╔══════════════════════════════════════════════════════╗
║               ✅  Configuração Concluída!            ║
╚══════════════════════════════════════════════════════╝

Resumo:
  • Backend IA:    {dados['ia_backend']} / {dados['ia_modelo']}
  • Whisper:       {dados['whisper_modelo']}
  • TTS:           {dados['tts_motor']}
  • Config salva:  ~/.config/snoopy/config.json

Para iniciar o Snoopy:
  python main.py

Para modo texto (sem microfone):
  python main.py --modo texto
        """)
