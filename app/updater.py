# =====================================================================
# updater.py
# Módulo de Atualização Automática — Verifica novas versões no GitHub,
# oferece ao usuário via diálogo e exibe progresso visual durante o
# download e instalação.
# =====================================================================

# ─────────────────────────────────────────────────────────────────────
# Imports
# ─────────────────────────────────────────────────────────────────────
import sys
import time
import logging
import subprocess

import requests
from packaging import version

from app.dialogs import ask_yes_no, show_error, ProgressWindow
from app.paths import UPDATE_DIR

log = logging.getLogger("sisport.updater")


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
    Procura por arquivos cujo nome termine com '_setup.exe'.

    :param release_json: (dict) JSON da release retornado pela API do GitHub.
    :return: (dict) Dicionário do asset encontrado.
    :raises RuntimeError: Se nenhum asset com sufixo '_setup.exe' for encontrado.
    """
    for a in release_json.get("assets", []):
        name = (a.get("name") or "").lower()
        if name.endswith("_setup.exe"):
            return a
    raise RuntimeError(
        "Release encontrada, mas nenhum asset terminando em '_setup.exe'."
    )


# =====================================================================
# Funções — Download com Progresso Visual
# =====================================================================

def _download_with_progress(url: str, filename: str, progress: ProgressWindow) -> str:
    """
    Baixa o instalador exibindo progresso visual em tempo real.

    :param url:       (str) URL de download do asset.
    :param filename:  (str) Nome do arquivo de destino.
    :param progress:  (ProgressWindow) Janela de progresso ativa.
    :return: (str) Caminho absoluto do arquivo baixado.
    """
    UPDATE_DIR.mkdir(parents=True, exist_ok=True)
    file_path = UPDATE_DIR / filename

    if file_path.exists():
        file_path.unlink()

    with requests.get(url, stream=True, timeout=120) as r:
        r.raise_for_status()

        total = int(r.headers.get("content-length", 0))
        downloaded = 0
        chunk_size = 1024 * 256  # 256 KB

        for chunk in r.iter_content(chunk_size=chunk_size):
            if not chunk:
                continue

            file_path.open("ab").write(chunk)
            downloaded += len(chunk)

            if total > 0:
                percent = (downloaded / total) * 100
                downloaded_mb = downloaded / (1024 * 1024)
                total_mb = total / (1024 * 1024)
                progress.update_progress(
                    percent,
                    f"Baixando atualização... {downloaded_mb:.1f} MB / {total_mb:.1f} MB",
                )
            else:
                downloaded_mb = downloaded / (1024 * 1024)
                progress.update_status(
                    f"Baixando atualização... {downloaded_mb:.1f} MB"
                )

    log.info(f"Download concluído: {file_path}")
    return str(file_path)


# =====================================================================
# Função Principal — Verificação e Oferta de Atualização
# =====================================================================

def check_and_offer_update(
    current_version: str, repo: str, app_name: str
) -> None:
    """
    Verifica se há uma versão mais recente no GitHub e oferece
    atualização ao usuário com feedback visual completo.

    Fluxo:
        1. Consulta a release mais recente via API do GitHub.
        2. Compara versões (semantic versioning).
        3. Exibe diálogo Sim/Não ao usuário.
        4. Abre janela de progresso visual.
        5. Baixa o instalador com barra de progresso.
        6. Executa o instalador e encerra a aplicação.

    :param current_version: (str) Versão atualmente instalada (ex: '1.2.0').
    :param repo:            (str) Repositório GitHub no formato 'owner/repo'.
    :param app_name:        (str) Nome da aplicação para exibir nos diálogos.
    :return: None.
    """
    progress = None

    try:
        # ── Ignora versão de desenvolvimento ──
        if current_version == "dev":
            log.info("Versão de desenvolvimento detectada — update ignorado.")
            return

        # ── Consulta GitHub ──
        log.info("Verificando atualizações no GitHub...")
        rel = _get_latest_release(repo)

        latest = (rel.get("tag_name") or "").lstrip("v").strip()
        if not latest:
            log.warning("Tag de versão não encontrada na release.")
            return

        log.info(f"Versão atual: {current_version} | Disponível: {latest}")

        # ── Compara versões ──
        if version.parse(latest) <= version.parse(current_version):
            log.info("Aplicação já está na versão mais recente.")
            return

        # ── Pergunta ao usuário ──
        msg = (
            f"Uma nova versão do {app_name} está disponível!\n\n"
            f"  Versão instalada:   {current_version}\n"
            f"  Versão disponível:  {latest}\n\n"
            "Deseja atualizar agora?"
        )

        if not ask_yes_no(f"{app_name} — Atualização Disponível", msg):
            log.info("Usuário recusou a atualização.")
            return

        # ── Localiza o instalador na release ──
        asset = _pick_installer_asset(rel)
        installer_url = asset["browser_download_url"]
        file_name = asset["name"]

        # ── Abre janela de progresso ──
        progress = ProgressWindow(f"{app_name} — Atualizando")
        progress.show()
        progress.update_progress(0, "Preparando download...")

        time.sleep(0.5)  # Pequena pausa para a janela renderizar

        # ── Download com progresso ──
        installer_path = _download_with_progress(
            installer_url, file_name, progress
        )

        # ── Instalação ──
        progress.update_progress(100, "Download concluído!")
        time.sleep(0.5)

        progress.set_indeterminate("Iniciando instalação...")
        time.sleep(1)

        log.info(f"Executando instalador: {installer_path}")
        subprocess.Popen([installer_path], shell=False)

        progress.update_status("Instalador iniciado! Fechando o aplicativo...")
        time.sleep(1.5)

        progress.close()
        sys.exit(0)

    except Exception as e:
        log.error(f"Erro durante atualização: {e}", exc_info=True)

        if progress:
            progress.close()

        show_error(
            f"{app_name} — Erro",
            f"Não foi possível concluir a atualização.\n\n"
            f"Erro: {e}\n\n"
            "O aplicativo continuará normalmente.",
        )
