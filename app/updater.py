# =====================================================================
# updater.py
# Módulo de Atualização Automática — Verifica a existência de novas
# versões no repositório GitHub, oferece ao usuário via diálogo
# Tkinter e, se aceito, baixa e executa o instalador automaticamente.
# =====================================================================

# ─────────────────────────────────────────────────────────────────────
# Imports
# ─────────────────────────────────────────────────────────────────────
import sys
import time
import subprocess

import requests
from packaging import version

import tkinter as tk
from tkinter import messagebox
from app.paths import UPDATE_DIR


# =====================================================================
# Funções — Interface de Diálogo (Tkinter)
# =====================================================================

def _ask_yes_no(title: str, message: str) -> bool:
    """
    Exibe um diálogo Sim/Não nativo do sistema via Tkinter (janela oculta).
    Utilizado para perguntar ao usuário se deseja atualizar.

    :param title:   (str) Título da janela de diálogo.
    :param message: (str) Mensagem exibida no corpo do diálogo.
    :return: (bool) True se o usuário clicou "Sim", False se "Não".
    """
    root = tk.Tk()
    root.withdraw()
    return messagebox.askyesno(title, message)


# =====================================================================
# Funções — Comunicação com GitHub API
# =====================================================================

def _get_latest_release(repo: str) -> dict:
    """
    Consulta a API do GitHub para obter os dados da release mais
    recente de um repositório público.

    :param repo: (str) Identificador do repositório no formato 'owner/repo'.
    :return: (dict) JSON da release mais recente retornado pela API.
    :raises requests.HTTPError: Se a requisição falhar (404, 403, etc.).
    """
    url = f"https://api.github.com/repos/{repo}/releases/latest"
    r = requests.get(url, timeout=10)
    r.raise_for_status()
    return r.json()


def _pick_installer_asset(release_json: dict) -> dict:
    """
    Localiza o asset do instalador dentro dos assets de uma release.
    Procura por arquivos cujo nome termine com '_setup.exe'
    (ex: SISPORTSetup.exe, sisport_setup.exe).

    :param release_json: (dict) JSON da release retornado pela API do GitHub.
    :return: (dict) Dicionário do asset encontrado (contém 'browser_download_url', etc.).
    :raises RuntimeError: Se nenhum asset com sufixo '_setup.exe' for encontrado.
    """
    for a in release_json.get("assets", []):
        name = (a.get("name") or "").lower()
        if name.endswith("_setup.exe"):
            return a
    raise RuntimeError("Release encontrada, mas não achei nenhum asset terminando em 'Setup.exe'.")


# =====================================================================
# Funções — Download do Instalador (Updater)
# =====================================================================

def _download_to_updates(url: str, filename: str) -> str:
    """
    Baixa o instalador para o diretório controlado da aplicação.
    """

    # Garante que a pasta existe
    UPDATE_DIR.mkdir(parents=True, exist_ok=True)

    file_path = UPDATE_DIR / filename

    # Remove versão anterior (evita conflito)
    if file_path.exists():
        file_path.unlink()

    with requests.get(url, stream=True, timeout=60) as r:
        r.raise_for_status()
        with open(file_path, "wb") as f:
            for chunk in r.iter_content(chunk_size=1024 * 256):
                if chunk:
                    f.write(chunk)

    return str(file_path)


# =====================================================================
# Função Principal — Verificação e Oferta de Atualização
# =====================================================================

def check_and_offer_update(current_version: str, repo: str, app_name: str) -> None:
    """
    Verifica se há uma versão mais recente no GitHub e oferece
    atualização ao usuário. Fluxo completo:

    1. Consulta a release mais recente via API do GitHub.
    2. Compara a versão remota com a versão instalada (semantic versioning).
    3. Se houver atualização, exibe diálogo Sim/Não ao usuário.
    4. Se aceito, localiza o asset do instalador na release.
    5. Baixa o instalador para pasta temporária.
    6. Executa o instalador e encerra a aplicação atual (sys.exit).

    Em caso de qualquer erro, retorna silenciosamente sem travar
    a inicialização da aplicação.

    :param current_version: (str) Versão atualmente instalada (ex: '1.2.0').
    :param repo:            (str) Repositório GitHub no formato 'owner/repo'.
    :param app_name:        (str) Nome da aplicação para exibir no diálogo.
    :return: None. Encerra o processo via sys.exit(0) se o usuário aceitar
             a atualização; caso contrário, retorna normalmente.
    """
    try:
        if current_version == "dev":
            print("[Updater]: Você está em versão de desenvolvedor.")
            return  # Ignora atualização em ambiente de desenvolvimento
        
        rel = _get_latest_release(repo)
        latest = (rel.get("tag_name") or "").lstrip("v").strip()
        if not latest:
            print("[Updater]: Versão mais recente não encontrada.")
            return
        print("[Updater]: Nova atualização detectada!")

        if version.parse(latest) <= version.parse(current_version):
            print("[Updater]: Você já está usando a versão mais recente.")
            return

        msg = (
            f"Existe uma nova versão do {app_name}.\n\n"
            f"Instalada: {current_version}\n"
            f"Disponível: {latest}\n\n"
            "Deseja atualizar agora?"
        )

        if not _ask_yes_no("Atualização disponível", msg):
            print("[Updater]: Usuário escolheu não atualizar o sistema.")
            return
        
        print("[Updater]: atualizando o sistema. Por favor, aguarde.")

        asset = _pick_installer_asset(rel)
        installer_url = asset["browser_download_url"]
        file_name = asset["name"]  # <- vem do GitHub
        installer_path = _download_to_updates(installer_url, file_name)

        # Executa o instalador em modo normal (vai perguntar pasta, permissões, etc.)
        subprocess.Popen([installer_path], shell=False)
        time.sleep(1)
        sys.exit(0)

    except Exception:
        # Em produção: logar isso em arquivo. Não travar o app por causa do update.
        return
