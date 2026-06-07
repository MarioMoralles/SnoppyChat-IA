"""
Testes básicos do Snoopy
Execute com: python -m pytest tests/ -v
"""

import asyncio
import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from snoopy.utils.config import Configuracao
from snoopy.ia.intencao import DetectorIntencao
from snoopy.memoria.gerenciador_memoria import GerenciadorMemoria


# --- Testes de Configuração ---

def test_configuracao_carrega_padroes():
    config = Configuracao({"ia_modelo": "llama3.2:3b"})
    assert config.get("ia_modelo") == "llama3.2:3b"
    assert config.get("chave_inexistente", "padrao") == "padrao"


def test_configuracao_set():
    config = Configuracao({})
    config._dados["teste"] = "valor"
    assert config.get("teste") == "valor"


# --- Testes de Detecção de Intenção ---

@pytest.mark.asyncio
async def test_detecta_saudacao():
    config = Configuracao({})
    detector = DetectorIntencao(config)
    resultado = await detector.detectar("olá, tudo bem?", [])
    assert resultado["tipo"] == "imediato"
    assert resultado["intencao"] == "saudacao"


@pytest.mark.asyncio
async def test_detecta_tarefa_background_codigo():
    config = Configuracao({})
    detector = DetectorIntencao(config)
    resultado = await detector.detectar(
        "pode programar um script Python para organizar meus arquivos?", []
    )
    assert resultado["tipo"] == "tarefa_background"


@pytest.mark.asyncio
async def test_detecta_tarefa_escrita():
    config = Configuracao({})
    detector = DetectorIntencao(config)
    resultado = await detector.detectar(
        "escreve um email profissional para o cliente", []
    )
    assert resultado["tipo"] == "tarefa_background"


@pytest.mark.asyncio
async def test_detecta_pergunta_rapida():
    config = Configuracao({})
    detector = DetectorIntencao(config)
    resultado = await detector.detectar("que horas são?", [])
    assert resultado["tipo"] == "imediato"


# --- Testes de Memória ---

@pytest.mark.asyncio
async def test_memoria_salvar_e_buscar(tmp_path):
    """Testa o ciclo completo de salvar e buscar memórias."""
    config = Configuracao({})
    # Redireciona o diretório de dados para tmp
    memoria = GerenciadorMemoria(config)
    memoria._dir_dados = tmp_path
    memoria._caminho_db = tmp_path / "test_memoria.db"
    await memoria.inicializar()

    # Salva uma memória
    await memoria.salvar(
        conteudo="Usuário prefere Python a JavaScript",
        tipo="preferencia",
        importancia=7
    )

    # Busca por relevância
    resultados = await memoria.buscar_relevantes("Python", limite=5)
    assert len(resultados) > 0
    assert any("Python" in r["conteudo"] for r in resultados)

    await memoria.fechar()


@pytest.mark.asyncio
async def test_memoria_preferencias(tmp_path):
    """Testa salvar e recuperar preferências."""
    config = Configuracao({})
    memoria = GerenciadorMemoria(config)
    memoria._dir_dados = tmp_path
    memoria._caminho_db = tmp_path / "test_prefs.db"
    await memoria.inicializar()

    await memoria.definir_preferencia("idioma", "pt-BR")
    valor = await memoria.obter_preferencia("idioma")
    assert valor == "pt-BR"

    valor_padrao = await memoria.obter_preferencia("chave_inexistente", "fallback")
    assert valor_padrao == "fallback"

    await memoria.fechar()


@pytest.mark.asyncio
async def test_memoria_historico_conversas(tmp_path):
    """Testa salvar e listar conversas."""
    config = Configuracao({})
    memoria = GerenciadorMemoria(config)
    memoria._dir_dados = tmp_path
    memoria._caminho_db = tmp_path / "test_conv.db"
    await memoria.inicializar()

    await memoria.salvar_conversa(
        pergunta="Qual é a capital do Brasil?",
        resposta="A capital do Brasil é Brasília."
    )

    conversas = await memoria.listar_conversas(limite=10)
    assert len(conversas) >= 1
    assert "Brasil" in conversas[0]["pergunta"]

    await memoria.fechar()


if __name__ == "__main__":
    asyncio.run(pytest.main([__file__, "-v"]))
