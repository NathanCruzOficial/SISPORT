"""
run.py — Ponto de entrada unificado (Webview / Browser)
=========================================================
Comportamento:
  • Padrão .............. abre em janela Webview (GUI nativo)
  • Segurar SHIFT ao abrir .. abre no navegador + console visível
  • --browser (CLI flag) ... idem, força modo browser

Build (PyInstaller):
  pyinstaller --noconsole --onefile run.py ...
  (O console é SEMPRE oculto; quando necessário, alocamos via Win32)
"""

import ctypes
import logging
import platform
import sys
import threading
import time
import webbrowser

from app.paths import APP_DIR, ensure_app_dirs, log_path

# ── Inicialização de pastas ────────────────────────────────────────────────

ensure_app_dirs()

# ── Logging (arquivo + handler de console adicionado depois se necessário) ──

LOG_FILE = log_path()

_fmt = logging.Formatter(
    "[%(asctime)s] %(levelname)-8s %(name)s — %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

_file_handler = logging.FileHandler(LOG_FILE, encoding="utf-8")
_file_handler.setFormatter(_fmt)
_file_handler.setLevel(logging.DEBUG)

_root = logging.getLogger()
_root.setLevel(logging.DEBUG)
_root.addHandler(_file_handler)

log = logging.getLogger("sisport.launcher")


# ── Detecção de tecla (SHIFT) ───────────────────────────────────────────────

def _is_shift_held() -> bool:
    """Retorna True se SHIFT está pressionado (Windows only)."""
    if platform.system() != "Windows":
        return False
    try:
        state = ctypes.windll.user32.GetAsyncKeyState(0x10)  # VK_SHIFT
        return bool(state & 0x8000)
    except Exception:
        return False


def _should_use_browser() -> bool:
    """Decide o modo: browser se --browser flag OU SHIFT pressionado."""
    if "--browser" in sys.argv:
        return True
    return _is_shift_held()


# ── Console Win32 (alocar/mostrar quando necessário) ────────────────────────

def _alloc_console():
    """
    Aloca um console mesmo quando o exe foi buildado com --noconsole.
    Redireciona stdout/stderr para o novo console.
    """
    if platform.system() != "Windows":
        return

    try:
        kernel32 = ctypes.windll.kernel32

        if not kernel32.AllocConsole():
            log.debug("Console já existia, reutilizando.")

        sys.stdout = open("CONOUT$", "w", encoding="utf-8", buffering=1)
        sys.stderr = open("CONOUT$", "w", encoding="utf-8", buffering=1)

        kernel32.SetConsoleTitleW("Sisport — Modo Browser")

        log.info("Console alocado com sucesso.")
    except Exception as e:
        log.warning(f"Falha ao alocar console: {e}")


def _add_console_log_handler():
    """Adiciona handler de console ao logging (só faz sentido se console existir)."""
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(_fmt)
    console_handler.setLevel(logging.INFO)
    _root.addHandler(console_handler)


# ── Servidor Flask ──────────────────────────────────────────────────────────

HOST = "127.0.0.1"
PORT = 5000


def _wait_for_server(host: str, port: int, timeout: float = 15.0) -> bool:
    """
    Espera o servidor responder (polling TCP) em vez de sleep fixo.
    Retorna True se ficou pronto, False se deu timeout.
    """
    import socket

    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with socket.create_connection((host, port), timeout=0.5):
                return True
        except OSError:
            time.sleep(0.15)
    return False


def _run_flask():
    """Sobe o Flask em thread daemon."""
    from app import create_app

    app = create_app()
    log.info(f"Flask iniciando em http://{HOST}:{PORT}")
    app.run(host=HOST, port=PORT, debug=False, use_reloader=False)


def _start_server_thread() -> threading.Thread:
    t = threading.Thread(target=_run_flask, daemon=True, name="flask-server")
    t.start()
    return t


# ── Modos de execução ──────────────────────────────────────────────────────

def _run_webview_mode():
    """Modo padrão: janela nativa via pywebview."""
    import webview
    from app.version import APP_NAME

    log.info("Modo: Webview (janela nativa)")

    _start_server_thread()

    if not _wait_for_server(HOST, PORT):
        log.error("Servidor não respondeu a tempo. Abortando.")
        sys.exit(1)

    log.info("Servidor pronto. Abrindo janela Webview.")

    webview.create_window(
        APP_NAME,
        f"http://{HOST}:{PORT}",
        width=1100,
        height=750,
        resizable=True,
        fullscreen=True,
    )
    webview.start()

    log.info("Janela Webview fechada. Encerrando.")


def _run_browser_mode():
    """Modo browser: console visível + abre navegador padrão."""
    from app.version import APP_NAME, __version__

    _alloc_console()
    _add_console_log_handler()

    log.info("=" * 50)
    log.info(f"  {APP_NAME} v{__version__}")
    log.info(f"  Modo: Browser (console ativo)")
    log.info(f"  URL:  http://{HOST}:{PORT}")
    log.info(f"  Dados: {APP_DIR}")
    log.info("=" * 50)

    _start_server_thread()

    if not _wait_for_server(HOST, PORT):
        log.error("Servidor não respondeu a tempo. Abortando.")
        input("Pressione ENTER para fechar...")
        sys.exit(1)

    log.info("Servidor pronto. Abrindo navegador...")
    webbrowser.open(f"http://{HOST}:{PORT}/")

    log.info("Pressione Ctrl+C ou feche esta janela para encerrar.")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        log.info("Encerrando por Ctrl+C.")


# ── Updater ─────────────────────────────────────────────────────────────────

def _check_update():
    """Verifica atualizações (silencia erros para não travar a inicialização)."""
    try:
        from app.updater import check_and_offer_update
        from app.version import __version__, APP_NAME, GITHUB_REPO

        log.info("Verificando atualizações...")
        check_and_offer_update(__version__, GITHUB_REPO, APP_NAME)
    except Exception as e:
        log.warning(f"Falha ao verificar atualização: {e}")


# ── Main ────────────────────────────────────────────────────────────────────

def main():
    log.info("Iniciando Sisport...")
    log.info(f"Dados em: {APP_DIR}")
    log.info(f"Log em:   {LOG_FILE}")

    browser_mode = _should_use_browser()

    if browser_mode:
        log.info("SHIFT detectado ou --browser passado → Modo Browser.")
    else:
        log.info("Modo padrão → Webview.")

    _check_update()

    if browser_mode:
        _run_browser_mode()
    else:
        _run_webview_mode()


if __name__ == "__main__":
    main()
