# -*- coding: utf-8 -*-
"""
programas.py — MOTOR do Snoppy.
Abre QUALQUER site, app ou pasta. Fecha aplicativos, sites e apps.
Salva tudo nos caches .md do Obsidian (cache_pastas.py / cache_site.py).
Este arquivo NÃO decide IA — quem decide é o snoppy.py.
"""
from __future__ import annotations

import os
import re
import glob
import time
import string
import platform
import subprocess
import unicodedata
import webbrowser
from urllib.parse import quote_plus

IS_WINDOWS = platform.system() == "Windows"

# ─────────────────────────────────────────────
# CACHES DO OBSIDIAN
# ─────────────────────────────────────────────
try:
    import cache_pastas
    CACHE_OK = True
except Exception:
    CACHE_OK = False

try:
    import cache_site
    CACHE_SITE_OK = True
except Exception:
    CACHE_SITE_OK = False


# ─────────────────────────────────────────────
# UTILIDADES DE TEXTO
# ─────────────────────────────────────────────
def normalizar(texto: str) -> str:
    if not texto:
        return ""
    texto = unicodedata.normalize("NFKD", texto)
    return "".join(c for c in texto if not unicodedata.combining(c)).lower().strip()


_RUIDO = (
    "abra", "abrir", "abre", "inicia", "iniciar", "executa", "executar",
    "roda", "rodar", "lanca", "lancar", "por favor", "pf", "pfv", "pra mim",
    "para mim", "ai", "aí", "o", "a", "os", "as", "um", "uma", "meu", "minha",
    "programa", "app", "aplicativo", "site", "pagina", "página", "pasta",
    "diretorio", "diretório", "software", "acesse", "acessar", "entra no",
    "entrar no", "vai pro", "folder",
)


def _limpar_nome(texto: str) -> str:
    t = texto.strip()
    low = normalizar(t)
    for r in sorted(_RUIDO, key=len, reverse=True):
        low = re.sub(rf"\b{re.escape(r)}\b", " ", low)
    low = re.sub(r"\s+", " ", low).strip()
    return low or t


def detectar_programa(texto: str) -> str:
    """Extrai o nome do programa/alvo do pedido (alias público)."""
    return _limpar_nome(texto)


# ─────────────────────────────────────────────
# GATILHOS
# ─────────────────────────────────────────────
GATILHOS_ABRIR = ("abra", "abrir", "abre", "inicia", "iniciar", "executa",
                  "executar", "roda", "rodar", "lanca", "lançar")
GATILHOS_FECHAR = ("feche", "fechar", "fecha", "encerra", "encerrar",
                   "mata", "matar", "termina", "terminar")
GATILHOS_PESQUISA = ("pesquise", "pesquisar", "pesquisa", "procure", "procurar",
                     "busque", "buscar", "google")
GATILHOS_SITE = ("site", "página", "pagina", "acesse", "acessar",
                 "entra no", "entrar no", "vai pro")
GATILHOS_PASTA = ("pasta", "diretorio", "diretório", "folder")


# ─────────────────────────────────────────────
# PROGRAMAS E PROCESSOS
# ─────────────────────────────────────────────
PROGRAMAS: dict[str, str] = {
    "calculadora": "calc.exe",
    "bloco de notas": "notepad.exe",
    "notepad": "notepad.exe",
    "explorador": "explorer.exe",
    "gerenciador de tarefas": "taskmgr.exe",
    "cmd": "cmd.exe",
    "terminal": "wt.exe",
    "powershell": "powershell.exe",
    "paint": "mspaint.exe",
}

PROCESSOS: dict[str, str] = {
    "chrome": "chrome.exe",
    "google": "chrome.exe",
    "google chrome": "chrome.exe",
    "firefox": "firefox.exe",
    "edge": "msedge.exe",
    "microsoft edge": "msedge.exe",
    "spotify": "spotify.exe",
    "discord": "discord.exe",
    "steam": "steam.exe",
    "telegram": "telegram.exe",
    "whatsapp": "whatsapp.exe",
    "word": "winword.exe",
    "excel": "excel.exe",
    "powerpoint": "powerpnt.exe",
    "bloco de notas": "notepad.exe",
    "notepad": "notepad.exe",
    "paint": "mspaint.exe",
    "vscode": "Code.exe",          # ← BUGFIX: VSCode é "Code.exe"
    "vs code": "Code.exe",
    "code": "Code.exe",
    "explorador": "explorer.exe",
    "calculadora": "CalculatorApp.exe",   # ← Win10/11 usa esse nome
    "calc": "CalculatorApp.exe",
}


# ─────────────────────────────────────────────
# SITES CONHECIDOS
# ─────────────────────────────────────────────
SITES_CONHECIDOS: dict[str, str] = {
    "youtube": "https://www.youtube.com",
    "you tube": "https://www.youtube.com",
    "google": "https://www.google.com",
    "gmail": "https://mail.google.com",
    "github": "https://github.com",
    "chatgpt": "https://chat.openai.com",
    "chat gpt": "https://chat.openai.com",
    "whatsapp": "https://web.whatsapp.com",
    "whats app": "https://web.whatsapp.com",
    "instagram": "https://www.instagram.com",
    "facebook": "https://www.facebook.com",
    "twitter": "https://twitter.com",
    "x": "https://x.com",
    "netflix": "https://www.netflix.com",
    "linkedin": "https://www.linkedin.com",
    "maps": "https://maps.google.com",
    "drive": "https://drive.google.com",
    "canva": "https://www.canva.com",
}


def _buscar_site(alvo: str) -> str | None:
    n = normalizar(alvo)
    if n in SITES_CONHECIDOS:
        return SITES_CONHECIDOS[n]
    sem_espaco = n.replace(" ", "")
    for chave, url in SITES_CONHECIDOS.items():
        if chave.replace(" ", "") == sem_espaco:
            return url
    return None


def _parece_url(texto: str) -> bool:
    t = normalizar(texto).replace(" ", "")
    return bool(re.match(r"^(https?://)?[\w\-]+\.[a-z]{2,}", t))


# ─────────────────────────────────────────────
# DETECTORES DE INTENÇÃO (usados pelo snoppy.py)
# ─────────────────────────────────────────────
def quer_pesquisar(texto: str) -> bool:
    low = normalizar(texto)
    primeira = low.split()[0] if low.split() else ""
    return primeira in GATILHOS_PESQUISA or any(
        low.startswith(g + " ") for g in GATILHOS_PESQUISA
    )


def quer_site(texto: str) -> bool:
    low = normalizar(texto)
    alvo = _limpar_nome(texto)
    if any(re.search(rf"\b{normalizar(g)}\b", low) for g in GATILHOS_SITE):
        return True
    if _parece_url(texto):
        return True
    if _buscar_site(alvo) and not quer_pasta(texto):
        return True
    return False


def quer_pasta(texto: str) -> bool:
    low = normalizar(texto)
    if any(re.search(rf"\b{normalizar(g)}\b", low) for g in GATILHOS_PASTA):
        return True
    alvo = _limpar_nome(texto).replace(" ", "")
    for chave in PASTAS_ESPECIAIS:
        if normalizar(chave).replace(" ", "") == alvo:
            return True
    return False


def quer_fechar(texto: str) -> bool:
    low = normalizar(texto)
    primeira = low.split()[0] if low.split() else ""
    return primeira in GATILHOS_FECHAR or any(
        low.startswith(g + " ") for g in GATILHOS_FECHAR
    )


def quer_abrir(texto: str) -> bool:
    low = normalizar(texto)
    primeira = low.split()[0] if low.split() else ""
    return primeira in GATILHOS_ABRIR or any(
        low.startswith(g + " ") for g in GATILHOS_ABRIR
    )


def extrair_termo_pesquisa(texto: str) -> str:
    """Remove APENAS o gatilho de pesquisa do início, preservando o termo."""
    termo = texto.strip()
    for g in sorted(GATILHOS_PESQUISA, key=len, reverse=True):
        novo = re.sub(rf"(?i)^{re.escape(g)}\b\s*(por\s+|sobre\s+)?", "", termo).strip()
        if novo != termo:
            termo = novo
            break
    # remove só sufixos de "onde buscar" — NÃO mexe em "o que é"
    termo = re.sub(r"(?i)\s*\b(no google|na internet|na web)\b\s*$", "", termo).strip()
    return termo or texto.strip()


# ─────────────────────────────────────────────
# PASTAS ESPECIAIS
# ─────────────────────────────────────────────
PASTAS_ESPECIAIS: dict[str, str] = {
    "downloads": os.path.expandvars("%USERPROFILE%\\Downloads"),
    "documentos": os.path.expandvars("%USERPROFILE%\\Documents"),
    "documents": os.path.expandvars("%USERPROFILE%\\Documents"),
    "imagens": os.path.expandvars("%USERPROFILE%\\Pictures"),
    "fotos": os.path.expandvars("%USERPROFILE%\\Pictures"),
    "videos": os.path.expandvars("%USERPROFILE%\\Videos"),
    "vídeos": os.path.expandvars("%USERPROFILE%\\Videos"),
    "musicas": os.path.expandvars("%USERPROFILE%\\Music"),
    "músicas": os.path.expandvars("%USERPROFILE%\\Music"),
    "area de trabalho": os.path.expandvars("%USERPROFILE%\\Desktop"),
    "área de trabalho": os.path.expandvars("%USERPROFILE%\\Desktop"),
    "desktop": os.path.expandvars("%USERPROFILE%\\Desktop"),
}

_IGNORAR_PASTAS = {
    "windows", "$recycle.bin", "system volume information", "node_modules",
    "appdata", "programdata", "$windows.~bs", "$windows.~ws",
    "perflogs", "recovery", "msocache", "config.msi",
    ".git", ".cache", "temp", "tmp", "winsxs", "drivers", "driverstore",
}

_CACHE_PASTAS: dict[str, str] | None = None


# ─────────────────────────────────────────────
# ÍNDICE DE PROGRAMAS INSTALADOS
# ─────────────────────────────────────────────
_CACHE_PROGRAMAS: dict[str, str] | None = None
_CACHE_UWP: dict[str, str] | None = None

_PASTAS_MENU = [
    os.path.expandvars("%ProgramData%\\Microsoft\\Windows\\Start Menu\\Programs"),
    os.path.expandvars("%AppData%\\Microsoft\\Windows\\Start Menu\\Programs"),
]

_PASTAS_EXE = [
    os.path.expandvars("%ProgramFiles%"),
    os.path.expandvars("%ProgramFiles(x86)%"),
    os.path.expandvars("%LocalAppData%"),
    os.path.expandvars("%LocalAppData%\\Programs"),
    os.path.expandvars("%AppData%"),
]

_CHAVES_REGISTRO = [
    (r"SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\App Paths", "app_paths"),
    (r"SOFTWARE\\WOW6432Node\\Microsoft\\Windows\\CurrentVersion\\App Paths", "app_paths"),
    (r"SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Uninstall", "uninstall"),
    (r"SOFTWARE\\WOW6432Node\\Microsoft\\Windows\\CurrentVersion\\Uninstall", "uninstall"),
]


def _listar_drives() -> list[str]:
    if not IS_WINDOWS:
        return ["/"]
    drives = []
    for letra in string.ascii_uppercase:
        raiz = f"{letra}:/"
        if os.path.isdir(raiz):
            drives.append(raiz)
    return drives or ["C:/"]


def _indexar_menu_iniciar() -> dict[str, str]:
    mapa: dict[str, str] = {}
    for pasta in _PASTAS_MENU:
        if not os.path.isdir(pasta):
            continue
        for raiz, _, arquivos in os.walk(pasta):
            for arq in arquivos:
                if arq.lower().endswith(('.lnk', '.url')):
                    nome = normalizar(os.path.splitext(arq)[0])
                    if nome and nome not in mapa:
                        mapa[nome] = os.path.join(raiz, arq)
    return mapa


def _indexar_registro() -> dict[str, str]:
    mapa: dict[str, str] = {}
    if not IS_WINDOWS:
        return mapa
    import winreg
    raizes = [winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER]
    for raiz in raizes:
        for caminho, tipo in _CHAVES_REGISTRO:
            try:
                chave = winreg.OpenKey(raiz, caminho)
            except Exception:
                continue
            try:
                i = 0
                while True:
                    try:
                        sub = winreg.EnumKey(chave, i)
                        i += 1
                    except OSError:
                        break
                    try:
                        subchave = winreg.OpenKey(chave, sub)
                    except Exception:
                        continue
                    try:
                        if tipo == "app_paths":
                            try:
                                caminho_valor, _ = winreg.QueryValueEx(subchave, "")
                            except Exception:
                                continue
                            if not caminho_valor:
                                continue
                            nome = normalizar(os.path.splitext(sub)[0])
                            if nome and nome not in mapa:
                                mapa[nome] = caminho_valor.strip('"')
                        else:
                            try:
                                nome_disp, _ = winreg.QueryValueEx(subchave, "DisplayName")
                            except Exception:
                                continue
                            caminho_exe = None
                            for campo in ("DisplayIcon", "InstallLocation"):
                                try:
                                    val, _ = winreg.QueryValueEx(subchave, campo)
                                except Exception:
                                    continue
                                if not val:
                                    continue
                                val = val.split(",")[0].strip('"')
                                if val.lower().endswith(".exe") and os.path.isfile(val):
                                    caminho_exe = val
                                    break
                                if os.path.isdir(val):
                                    exes = glob.glob(os.path.join(val, "*.exe"))
                                    exes = [
                                        e for e in exes
                                        if not any(x in e.lower() for x in ("unins", "setup", "update", "crash"))
                                    ]
                                    if exes:
                                        caminho_exe = max(exes, key=os.path.getsize)
                                        break
                            if caminho_exe:
                                nome = normalizar(nome_disp)
                                if nome and nome not in mapa:
                                    mapa[nome] = caminho_exe
                    finally:
                        try:
                            winreg.CloseKey(subchave)
                        except Exception:
                            pass
            finally:
                try:
                    winreg.CloseKey(chave)
                except Exception:
                    pass
    return mapa


def _indexar_uwp() -> dict[str, str]:
    mapa: dict[str, str] = {}
    if not IS_WINDOWS:
        return mapa
    try:
        ps = ("[Console]::OutputEncoding=[System.Text.Encoding]::UTF8; "
              "Get-StartApps | ForEach-Object { Write-Output \"$($_.Name)`t$($_.AppID)\" }")
        r = subprocess.run(
            ["powershell", "-NoProfile", "-Command", ps],
            capture_output=True, text=True, timeout=25,
            encoding="utf-8", errors="ignore",
        )
        for linha in r.stdout.splitlines():
            if "\t" not in linha:
                continue
            nome, app_id = linha.split("\t", 1)
            nome_n = normalizar(nome.strip())
            app_id = app_id.strip()
            if nome_n and app_id and nome_n not in mapa:
                mapa[nome_n] = app_id
    except Exception:
        pass
    return mapa


def _carregar_cache() -> dict[str, str]:
    global _CACHE_PROGRAMAS, _CACHE_UWP
    if _CACHE_PROGRAMAS is None:
        if IS_WINDOWS:
            mapa: dict[str, str] = {}
            mapa.update(_indexar_registro())
            for k, v in _indexar_menu_iniciar().items():
                mapa.setdefault(k, v)
            _CACHE_UWP = _indexar_uwp()
            for k, v in _CACHE_UWP.items():
                mapa.setdefault(k, f"shell:appsFolder\\{v}")
            _CACHE_PROGRAMAS = mapa
        else:
            _CACHE_PROGRAMAS = {}
            _CACHE_UWP = {}
    return _CACHE_PROGRAMAS


def recarregar_indice() -> str:
    global _CACHE_PROGRAMAS, _CACHE_UWP, _CACHE_PASTAS
    _CACHE_PROGRAMAS = None
    _CACHE_UWP = None
    _CACHE_PASTAS = None
    cache = _carregar_cache()
    n_uwp = len(_CACHE_UWP or {})
    return (f"Índice atualizado: {len(cache)} programas no total "
            f"(incluindo {n_uwp} apps da Microsoft Store).")


# ─────────────────────────────────────────────
# MATCHING
# ─────────────────────────────────────────────
def _pontuar_match(alvo: str, nome: str) -> int:
    if not nome:
        return 0
    if nome == alvo:
        return 100
    if alvo in nome:
        return 80 - abs(len(nome) - len(alvo))
    if nome in alvo and len(nome) >= max(4, len(alvo) - 3):
        return 40 - (len(alvo) - len(nome))
    return 0


def _achar_no_indice(nome: str) -> str | None:
    cache = _carregar_cache()
    alvo = normalizar(nome)
    if not alvo:
        return None
    if alvo in cache:
        return cache[alvo]
    alvo_c = alvo.replace(" ", "")
    melhor: tuple[int, str] | None = None
    for k, v in cache.items():
        pontos = _pontuar_match(alvo_c, k.replace(" ", ""))
        if pontos <= 0:
            continue
        if v.startswith("shell:appsFolder\\"):
            pontos += 1
        if melhor is None or pontos > melhor[0]:
            melhor = (pontos, v)
    return melhor[1] if melhor else None


def _achar_exe_nas_pastas(nome: str) -> str | None:
    alvo = normalizar(nome).replace(" ", "")
    if not alvo:
        return None
    limite = time.time() + 8
    melhor: tuple[int, str] | None = None
    for base in _PASTAS_EXE:
        if not os.path.isdir(base):
            continue
        for padrao in ("*.exe", "*/*.exe", "*/*/*.exe", "*/*/*/*.exe"):
            if time.time() > limite:
                return melhor[1] if melhor else None
            try:
                for caminho in glob.glob(os.path.join(base, padrao)):
                    if time.time() > limite:
                        return melhor[1] if melhor else None
                    nome_exe = normalizar(
                        os.path.splitext(os.path.basename(caminho))[0]
                    ).replace(" ", "")
                    if not nome_exe:
                        continue
                    if any(x in nome_exe for x in ("unins", "setup", "update", "crashpad", "helper", "redist")):
                        continue
                    pontos = _pontuar_match(alvo, nome_exe)
                    if pontos > 0 and (melhor is None or pontos > melhor[0]):
                        melhor = (pontos, caminho)
                        if pontos == 100:
                            return caminho
            except Exception:
                continue
    return melhor[1] if melhor else None


def _achar_pasta_por_nome(nome: str, timeout: float = 30.0) -> str | None:
    alvo = normalizar(nome).replace(" ", "")
    if not alvo:
        return None

    if CACHE_OK:
        try:
            achado = cache_pastas.buscar(nome)
            if achado and os.path.isdir(achado):
                return achado
        except Exception:
            pass

    limite = time.time() + timeout
    melhor: tuple[int, str] | None = None

    bases_prioritarias = [os.path.expandvars("%USERPROFILE%")]
    bases_secundarias = list(_listar_drives())

    def varrer(base: str) -> str | None:
        nonlocal melhor
        if not os.path.isdir(base):
            return None
        for raiz, dirs, _ in os.walk(base, topdown=True):
            if time.time() > limite:
                return melhor[1] if melhor else None
            dirs[:] = [
                d for d in dirs
                if normalizar(d) not in _IGNORAR_PASTAS and not d.startswith(("$", "."))
            ]
            for d in dirs:
                nome_pasta = normalizar(d).replace(" ", "")
                pontos = _pontuar_match(alvo, nome_pasta)
                if pontos > 0 and (melhor is None or pontos > melhor[0]):
                    melhor = (pontos, os.path.join(raiz, d))
                    if pontos == 100:
                        return melhor[1]
        return None

    for base in bases_prioritarias:
        varrer(base)
        if melhor and melhor[0] == 100:
            break

    if not (melhor and melhor[0] == 100):
        for base in bases_secundarias:
            if time.time() > limite:
                break
            varrer(base)
            if melhor and melhor[0] == 100:
                break

    resultado = melhor[1] if melhor else None

    if resultado and CACHE_OK:
        try:
            cache_pastas.salvar(nome, resultado)
        except Exception:
            pass

    return resultado


# ─────────────────────────────────────────────
# AÇÕES — ABRIR
# ─────────────────────────────────────────────
def abrir_site(alvo: str) -> str:
    nome = _limpar_nome(alvo) if any(g in normalizar(alvo) for g in GATILHOS_ABRIR + GATILHOS_SITE) else alvo
    url = _buscar_site(nome)
    if not url:
        n = normalizar(nome).replace(" ", "")
        if _parece_url(nome):
            url = n if n.startswith("http") else f"https://{n}"
        else:
            url = f"https://www.google.com/search?q={quote_plus(nome)}"
    try:
        webbrowser.open(url)
        if CACHE_SITE_OK:
            cache_site.registrar_site(nome, url)
        return f"Pronto, abri o site: {url} 🌐"
    except Exception as e:
        return f"Não consegui abrir o site '{nome}': {e}"


def pesquisar_navegador(termo: str) -> str:
    termo = (termo or "").strip()
    if not termo:
        return "O que você quer pesquisar?"
    try:
        url = f"https://www.google.com/search?q={quote_plus(termo)}"
        webbrowser.open(url)
        if CACHE_SITE_OK:
            cache_site.registrar_pesquisa(termo, url)
        return f"Pronto, pesquisei por '{termo}' no Google. 🔍"
    except Exception as e:
        return f"Não consegui pesquisar '{termo}': {e}"


def abrir_pasta(alvo: str) -> str:
    nome = _limpar_nome(alvo) if any(g in normalizar(alvo) for g in GATILHOS_ABRIR + GATILHOS_PASTA) else alvo
    n = normalizar(nome).replace(" ", "")

    for chave, caminho in PASTAS_ESPECIAIS.items():
        if normalizar(chave).replace(" ", "") == n:
            if os.path.isdir(caminho):
                return _abrir_caminho(caminho, tipo="pasta")

    if os.path.isdir(nome):
        return _abrir_caminho(nome, tipo="pasta")

    caminho = _achar_pasta_por_nome(nome)
    if caminho and os.path.isdir(caminho):
        return _abrir_caminho(caminho, tipo="pasta")
    return f"Não encontrei a pasta '{nome}' no computador. 🤔"


def _abrir_caminho(caminho: str, tipo: str = "programa") -> str:
    try:
        if IS_WINDOWS:
            if caminho.startswith("shell:appsFolder\\"):
                subprocess.Popen(["explorer.exe", caminho])
            else:
                os.startfile(caminho)  # type: ignore[attr-defined]
        else:
            abridor = "open" if platform.system() == "Darwin" else "xdg-open"
            subprocess.Popen([abridor, caminho])
        nome = os.path.basename(caminho.rstrip("\\/")) or caminho
        if tipo == "pasta":
            return f"Pronto, abri a pasta: {caminho} 📁"
        return f"Pronto, abri: {nome} 🚀"
    except Exception as e:
        return f"Não consegui abrir '{caminho}': {e}"


def abrir_programa(alvo: str) -> str | None:
    chave = normalizar(alvo)
    if chave in PROGRAMAS:
        try:
            subprocess.Popen(PROGRAMAS[chave], shell=True)
            return f"Pronto, abri o {alvo}. 🚀"
        except Exception as e:
            return f"Não consegui abrir '{alvo}': {e}"

    caminho = _achar_no_indice(alvo)
    if caminho:
        return _abrir_caminho(caminho, tipo="programa")

    exe = _achar_exe_nas_pastas(alvo)
    if exe:
        return _abrir_caminho(exe, tipo="programa")

    return None


# ─────────────────────────────────────────────
# AÇÕES — FECHAR (robusto: apps, programas e sites)
# ─────────────────────────────────────────────
def fechar_programa(alvo: str) -> str:
    # limpa o gatilho de fechar se vier no texto bruto
    if any(re.search(rf"\b{normalizar(g)}\b", normalizar(alvo)) for g in GATILHOS_FECHAR):
        alvo = _limpar_nome(alvo)

    chave = normalizar(alvo)
    if not chave:
        return "Qual programa você quer fechar?"

    # 1) Se for um SITE conhecido, fecha o NAVEGADOR
    if _buscar_site(chave):
        return _fechar_navegadores(alvo)

    # 2) Descobre o nome do processo (.exe)
    nome_proc = PROCESSOS.get(chave)
    if not nome_proc:
        # tenta achar o .exe real no índice de programas instalados
        caminho = _achar_no_indice(chave) or _achar_exe_nas_pastas(chave)
        if caminho and caminho.lower().endswith(".exe"):
            nome_proc = os.path.basename(caminho)
        else:
            nome_proc = chave.replace(" ", "") + ".exe"

    if not nome_proc or nome_proc == ".exe":
        return "Qual programa você quer fechar?"

    return _matar_processo(nome_proc, alvo)


def _matar_processo(nome_proc: str, label: str) -> str:
    """Mata um processo pelo nome do .exe (robusto: /T fecha filhos)."""
    try:
        if IS_WINDOWS:
            # /T = encerra a árvore inteira (processos filhos junto)
            r = subprocess.run(
                ["taskkill", "/F", "/T", "/IM", nome_proc],
                capture_output=True, text=True,
            )
            if r.returncode == 0:
                return f"Fechei o programa '{label}'. ✅"

            # Fallback p/ apps da Store (UWP) teimosos (ex.: Calculadora)
            base_nome = os.path.splitext(nome_proc)[0]
            ps = (f"Get-Process | Where-Object {{$_.Name -like '*{base_nome}*'}} "
                  f"| Stop-Process -Force")
            r2 = subprocess.run(
                ["powershell", "-NoProfile", "-Command", ps],
                capture_output=True, text=True,
            )
            if r2.returncode == 0 and not r2.stderr.strip():
                return f"Fechei o programa '{label}'. ✅"

            return f"Não encontrei um programa em execução chamado '{label}'. 🤔"
        else:
            base = nome_proc.replace(".exe", "")
            subprocess.run(["pkill", "-f", base])
            return f"Tentei fechar '{label}'."
    except Exception as e:
        return f"Não consegui fechar '{label}': {e}"


def _fechar_navegadores(label: str) -> str:
    """
    Fecha o(s) navegador(es) abertos. Usado quando o usuário pede pra
    'fechar o youtube' / 'fechar o gmail' (sites que vivem no navegador).
    Obs.: fecha o navegador inteiro (Windows não fecha aba isolada via taskkill).
    """
    navegadores = ["chrome.exe", "msedge.exe", "firefox.exe"]
    fechou = []
    for nav in navegadores:
        try:
            r = subprocess.run(
                ["taskkill", "/F", "/T", "/IM", nav],
                capture_output=True, text=True,
            )
            if r.returncode == 0:
                fechou.append(nav.replace(".exe", ""))
        except Exception:
            continue
    if fechou:
        return f"Fechei o navegador ({', '.join(fechou)}) pra encerrar o {label}. 🌐❌"
    return f"Nenhum navegador estava aberto pra fechar o {label}. 🤔"


# ─────────────────────────────────────────────
# CÉREBRO DE AÇÕES (chamado pelo snoppy.py)
# ─────────────────────────────────────────────
def interpretar_comando(texto: str) -> str:
    if not texto or not texto.strip():
        return "Não entendi o comando. Pode repetir?"

    low = normalizar(texto)

    # caches do Obsidian
    if CACHE_OK:
        if low in ("ver cache", "listar cache", "mostrar cache"):
            return cache_pastas.listar_cache()
        if low in ("limpar cache", "apagar cache"):
            return cache_pastas.limpar_cache()

    if CACHE_SITE_OK:
        if low in ("ver historico", "ver histórico", "ver sites", "ver pesquisas"):
            return cache_site.listar_cache()
        if low in ("limpar historico", "limpar histórico"):
            return cache_site.limpar_cache()
        if low.startswith(("buscar no historico", "buscar no histórico")):
            termo = re.sub(r"(?i)^buscar no hist[oó]rico\s*", "", texto).strip()
            return cache_site.buscar_no_historico(termo)

    if low in ("recarregar indice", "reindexar", "atualizar programas"):
        return recarregar_indice()

    # 1) PESQUISAR
    if quer_pesquisar(texto):
        return pesquisar_navegador(extrair_termo_pesquisa(texto))

    # 2) FECHAR
    if quer_fechar(texto):
        return fechar_programa(texto)

    # 3) PASTA
    if quer_pasta(texto):
        return abrir_pasta(texto)

    # 4) SITE
    if quer_site(texto):
        return abrir_site(texto)

    # 5) ABRIR (programa → pasta → site fallback)
    if quer_abrir(texto):
        alvo = detectar_programa(texto)
        if _buscar_site(alvo):
            return abrir_site(alvo)
        res = abrir_programa(alvo)
        if res:
            return res
        caminho_pasta = _achar_pasta_por_nome(alvo)
        if caminho_pasta:
            return _abrir_caminho(caminho_pasta, tipo="pasta")
        return abrir_site(alvo)

    # 6) site solto
    if _buscar_site(low) or _parece_url(low):
        return abrir_site(low)

    return ("Não entendi o que você quer abrir. "
            "Tente 'abra o spotify', 'pesquise gatos' ou 'abra a pasta downloads'. 🐶")


# teste isolado do motor
if __name__ == "__main__":
    print(recarregar_indice())
    while True:
        try:
            cmd = input("\n[motor] > ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if cmd.lower() in ("sair", "exit", "quit"):
            break
        print(interpretar_comando(cmd))
