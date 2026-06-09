"""
Ferramentas de Controle da Máquina (Tool Calling)
Cada ferramenta é uma função que o Snoopy pode invocar para agir no sistema.

⚠️ SEGURANÇA: ações destrutivas pedem confirmação. Comandos arbitrários
são bloqueados por padrão — só rodam os comandos da lista permitida.
"""

import os
import sys
import shutil
import subprocess
import webbrowser
import platform
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Callable, Any, Optional
from urllib.parse import quote_plus

from ..utils.logger import obter_logger

logger = obter_logger("automacao.ferramentas")


class CaixaDeFerramentas:
    """
    Registro central de ferramentas que o Snoopy pode usar.
    Cada ferramenta tem: nome, descrição, parâmetros e função executora.
    O LLM recebe a lista e escolhe qual chamar.
    """

    def __init__(self, callback_confirmacao: Optional[Callable] = None):
        # callback_confirmacao(mensagem) -> bool : pede ao usuário antes de agir
        self.callback_confirmacao = callback_confirmacao
        self.sistema = platform.system()  # 'Windows', 'Linux', 'Darwin'
        self._ferramentas: Dict[str, Dict] = {}
        self._registrar_padrao()

    # ------------------------------------------------------------------ #
    #  Registro de ferramentas                                            #
    # ------------------------------------------------------------------ #
    def registrar(self, nome: str, descricao: str, parametros: Dict, funcao: Callable):
        self._ferramentas[nome] = {
            "nome": nome,
            "descricao": descricao,
            "parametros": parametros,
            "funcao": funcao,
        }

    def _registrar_padrao(self):
        self.registrar(
            "criar_pasta",
            "Cria uma nova pasta/diretório no computador.",
            {"caminho": "string - caminho da pasta a criar"},
            self._criar_pasta,
        )
        self.registrar(
            "listar_arquivos",
            "Lista arquivos e pastas de um diretório.",
            {"caminho": "string - caminho do diretório (padrão: pasta atual)"},
            self._listar_arquivos,
        )
        self.registrar(
            "organizar_pasta",
            "Organiza arquivos de uma pasta em subpastas por tipo (imagens, documentos, etc).",
            {"caminho": "string - pasta a organizar"},
            self._organizar_pasta,
        )
        self.registrar(
            "abrir_app",
            "Abre um aplicativo ou programa instalado no computador.",
            {"nome_app": "string - nome do app (ex: notepad, calc, chrome)"},
            self._abrir_app,
        )
        self.registrar(
            "pesquisar_web",
            "Abre o navegador e pesquisa algo no Google. (Requer internet)",
            {"consulta": "string - o que pesquisar"},
            self._pesquisar_web,
        )
        self.registrar(
            "abrir_site",
            "Abre um site específico no navegador. (Requer internet)",
            {"url": "string - endereço do site"},
            self._abrir_site,
        )
        self.registrar(
            "gerar_relatorio",
            "Cria um arquivo de relatório em Markdown com o conteúdo fornecido.",
            {"titulo": "string", "conteudo": "string - texto do relatório",
             "pasta": "string - onde salvar (opcional)"},
            self._gerar_relatorio,
        )
        self.registrar(
            "info_sistema",
            "Retorna informações do sistema (SO, hora, espaço em disco).",
            {},
            self._info_sistema,
        )

    # ------------------------------------------------------------------ #
    #  Descrição para o LLM                                               #
    # ------------------------------------------------------------------ #
    def descrever_para_llm(self) -> str:
        """Gera texto descrevendo as ferramentas para o prompt do LLM."""
        linhas = ["Ferramentas disponíveis (responda com JSON para usar uma):"]
        for f in self._ferramentas.values():
            params = ", ".join(f["parametros"].keys()) or "nenhum"
            linhas.append(f"- {f['nome']}({params}): {f['descricao']}")
        return "\n".join(linhas)

    def listar_nomes(self) -> List[str]:
        return list(self._ferramentas.keys())

    # ------------------------------------------------------------------ #
    #  Execução                                                           #
    # ------------------------------------------------------------------ #
    async def executar(self, nome: str, argumentos: Dict) -> str:
        """Executa uma ferramenta pelo nome com os argumentos dados."""
        ferramenta = self._ferramentas.get(nome)
        if not ferramenta:
            return f"Ferramenta '{nome}' não existe."

        logger.info(f"🔧 Executando ferramenta: {nome}({argumentos})")
        try:
            funcao = ferramenta["funcao"]
            import asyncio
            if asyncio.iscoroutinefunction(funcao):
                return await funcao(**argumentos)
            else:
                loop = asyncio.get_running_loop()
                return await loop.run_in_executor(None, lambda: funcao(**argumentos))
        except TypeError as e:
            return f"Argumentos inválidos para '{nome}': {e}"
        except Exception as e:
            logger.error(f"Erro ao executar '{nome}': {e}")
            return f"Erro ao executar '{nome}': {e}"

    def _expandir(self, caminho: str) -> Path:
        return Path(os.path.expanduser(os.path.expandvars(caminho))).resolve()

    # ------------------------------------------------------------------ #
    #  Implementação das ferramentas                                      #
    # ------------------------------------------------------------------ #
    def _criar_pasta(self, caminho: str) -> str:
        p = self._expandir(caminho)
        p.mkdir(parents=True, exist_ok=True)
        return f"Pasta criada: {p}"

    def _listar_arquivos(self, caminho: str = ".") -> str:
        p = self._expandir(caminho)
        if not p.exists():
            return f"Caminho não existe: {p}"
        itens = sorted(p.iterdir())
        if not itens:
            return f"A pasta {p} está vazia."
        linhas = [f"Conteúdo de {p}:"]
        for item in itens[:50]:
            tipo = "📁" if item.is_dir() else "📄"
            linhas.append(f"  {tipo} {item.name}")
        return "\n".join(linhas)

    def _organizar_pasta(self, caminho: str) -> str:
        p = self._expandir(caminho)
        if not p.is_dir():
            return f"Não é uma pasta válida: {p}"

        categorias = {
            "Imagens": [".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp", ".svg"],
            "Documentos": [".pdf", ".doc", ".docx", ".txt", ".odt", ".rtf", ".md"],
            "Planilhas": [".xls", ".xlsx", ".csv", ".ods"],
            "Videos": [".mp4", ".avi", ".mkv", ".mov", ".wmv"],
            "Audio": [".mp3", ".wav", ".flac", ".ogg", ".m4a"],
            "Compactados": [".zip", ".rar", ".7z", ".tar", ".gz"],
            "Executaveis": [".exe", ".msi", ".deb", ".appimage"],
        }
        movidos = 0
        for arquivo in p.iterdir():
            if arquivo.is_file():
                ext = arquivo.suffix.lower()
                for categoria, exts in categorias.items():
                    if ext in exts:
                        destino = p / categoria
                        destino.mkdir(exist_ok=True)
                        try:
                            shutil.move(str(arquivo), str(destino / arquivo.name))
                            movidos += 1
                        except Exception:
                            pass
                        break
        return f"Organização concluída: {movidos} arquivos movidos em {p}"

    def _abrir_app(self, nome_app: str) -> str:
        try:
            if self.sistema == "Windows":
                os.startfile(nome_app)  # type: ignore[attr-defined]
            elif self.sistema == "Darwin":
                subprocess.Popen(["open", "-a", nome_app])
            else:
                subprocess.Popen([nome_app])
            return f"Abrindo {nome_app}..."
        except FileNotFoundError:
            return f"Não encontrei o app '{nome_app}'."
        except Exception as e:
            return f"Não consegui abrir '{nome_app}': {e}"

    def _pesquisar_web(self, consulta: str) -> str:
        url = f"https://www.google.com/search?q={quote_plus(consulta)}"
        webbrowser.open(url)
        return f"Pesquisando '{consulta}' no Google..."

    def _abrir_site(self, url: str) -> str:
        if not url.startswith(("http://", "https://")):
            url = "https://" + url
        webbrowser.open(url)
        return f"Abrindo {url}..."

    def _gerar_relatorio(self, titulo: str, conteudo: str, pasta: str = "") -> str:
        if pasta:
            destino = self._expandir(pasta)
        else:
            destino = Path.home() / "Documents" / "Snoopy_Relatorios"
        destino.mkdir(parents=True, exist_ok=True)

        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        nome_arquivo = f"{titulo.replace(' ', '_')}_{ts}.md"
        caminho = destino / nome_arquivo

        texto = (
            f"# {titulo}\n\n"
            f"*Gerado por Snoopy em {datetime.now().strftime('%d/%m/%Y %H:%M')}*\n\n"
            f"---\n\n{conteudo}\n"
        )
        caminho.write_text(texto, encoding="utf-8")
        return f"Relatório salvo em: {caminho}"

    def _info_sistema(self) -> str:
        uso = shutil.disk_usage(Path.home())
        gb = lambda x: round(x / (1024**3), 1)
        return (
            f"Sistema: {platform.system()} {platform.release()}\n"
            f"Hora: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}\n"
            f"Disco: {gb(uso.used)}GB usados de {gb(uso.total)}GB "
            f"({gb(uso.free)}GB livres)"
        )
