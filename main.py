# =====================================================================
# main.py
# Ponto de Entrada Unificado — Responsável por inicializar a aplicação
# Sisport em dois modos: janela nativa (Webview) ou navegador padrão.
# Gerencia logging, detecção de tecla SHIFT, alocação de console
# Win32, servidor Flask em thread e verificação de atualizações.
#
# Comportamento:
#   • Padrão ................. abre em janela Webview (GUI nativo)
#   • Segurar SHIFT ao abrir . abre no navegador + console visível
#   • --browser (CLI flag) ... idem, força modo browser
#
# Build (PyInstaller):
#   pyinstaller --noconsole --onefile main.py... (ou main.spec)
#   (O console é SEMPRE oculto; quando necessário, alocamos via Win32)
# =====================================================================

# ─────────────────────────────────────────────────────────────────────
# Imports
# ─────────────────────────────────────────────────────────────────────
import ctypes
import logging
import platform
import sys
import threading
import time
import webbrowser

from app.paths import APP_DIR, ensure_app_dirs, log_path, icon_path




# ─── AppUserModelID (Desagrupa o sistema do python normal) ───
if platform.system() == "Windows":
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("com.sisport.app")

# =====================================================================
# Inicialização de Pastas
# =====================================================================

# Garante que todos os diretórios necessários da aplicação existam
# antes de qualquer outra operação (uploads, logs, banco, etc.).
ensure_app_dirs()


# =====================================================================
# Variáveis Globais — Logging
# =====================================================================

# Caminho absoluto do arquivo de log da aplicação.
LOG_FILE = log_path()

# Formatter padrão reutilizado por todos os handlers de log.
_fmt = logging.Formatter(
    "[%(asctime)s] %(levelname)-8s %(name)s — %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

# Handler de arquivo: grava todos os logs (DEBUG+) em disco.
_file_handler = logging.FileHandler(LOG_FILE, encoding="utf-8")
_file_handler.setFormatter(_fmt)
_file_handler.setLevel(logging.DEBUG)

# Configuração do logger raiz com handler de arquivo.
_root = logging.getLogger()
_root.setLevel(logging.DEBUG)
_root.addHandler(_file_handler)

# Logger específico do launcher para mensagens de inicialização.
log = logging.getLogger("sisport.launcher")


# =====================================================================
# Variáveis Globais — Servidor Flask
# =====================================================================

# Endereço e porta do servidor Flask local.
HOST = "127.0.0.1"
PORT = 5000


# =====================================================================
# Detecção de Isntância existente do sistema.
# =====================================================================

def _ensure_single_instance():
    """
    Garante que apenas uma instância da aplicação esteja rodando.
    Usa um Named Mutex do Windows. Se já houver uma instância ativa,
    exibe um aviso e encerra o processo.

    :return: O handle do mutex (deve ser mantido em memória enquanto o app rodar).
    """
    if platform.system() != "Windows":
        return None

    mutex_name = "Global\\SISPORT_SINGLE_INSTANCE"
    kernel32 = ctypes.windll.kernel32

    ERROR_ALREADY_EXISTS = 183

    mutex = kernel32.CreateMutexW(None, False, mutex_name)
    last_error = ctypes.GetLastError()

    if last_error == ERROR_ALREADY_EXISTS:
        log.warning("Outra instância do SISPORT já está em execução.")
        ctypes.windll.user32.MessageBoxW(
            0,
            "O SISPORT já está em execução!",
            "SISPORT",
            0x40  # MB_ICONINFORMATION
        )
        sys.exit(0)

    log.info("Mutex adquirido — instância única confirmada.")
    return mutex

# =====================================================================
# Funções — Detecção de Tecla (SHIFT) e Modo de Execução
# =====================================================================

def _is_shift_held() -> bool:
    """
    Verifica se a tecla SHIFT está pressionada no momento da chamada.
    Funciona apenas no Windows via API Win32 (GetAsyncKeyState).

    :return: (bool) True se SHIFT está pressionado, False caso contrário
             ou se não estiver no Windows.
    """
    if platform.system() != "Windows":
        return False
    try:
        state = ctypes.windll.user32.GetAsyncKeyState(0x10)  # VK_SHIFT
        return bool(state & 0x8000)
    except Exception:
        return False


def _should_use_browser() -> bool:
    """
    Decide o modo de execução da aplicação: browser se a flag --browser
    foi passada via CLI ou se SHIFT está pressionado ao iniciar.

    :return: (bool) True para modo browser, False para modo Webview.
    """
    if "--browser" in sys.argv:
        return True
    return _is_shift_held()


# =====================================================================
# Funções — Console Win32 (Alocação e Configuração)
# =====================================================================

def _alloc_console():
    """
    Aloca um console Win32 mesmo quando o executável foi buildado com
    --noconsole (PyInstaller). Redireciona stdout/stderr para o novo
    console e define o título da janela.

    :return: None. Apenas no Windows; em outros SOs é no-op.
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
    """
    Adiciona um handler de console (stdout) ao sistema de logging.
    Deve ser chamado somente após _alloc_console(), quando há um
    console disponível para exibir as mensagens.

    :return: None.
    """
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(_fmt)
    console_handler.setLevel(logging.INFO)
    _root.addHandler(console_handler)


# =====================================================================
# Funções — Servidor Flask (Thread e Polling)
# =====================================================================

def _wait_for_server(host: str, port: int, timeout: float = 15.0) -> bool:
    """
    Aguarda o servidor Flask ficar pronto fazendo polling via conexão
    TCP. Mais confiável que um sleep fixo.

    :param host:    (str)   Endereço do servidor.
    :param port:    (int)   Porta do servidor.
    :param timeout: (float) Tempo máximo de espera em segundos (padrão: 15s).
    :return: (bool) True se o servidor respondeu, False se deu timeout.
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
    """
    Cria e inicia a aplicação Flask. Projetada para rodar dentro de
    uma thread daemon, sem reloader e sem modo debug.

    :return: None.
    """
    from app import create_app

    app = create_app()
    log.info(f"Flask iniciando em http://{HOST}:{PORT}")
    app.run(host=HOST, port=PORT, debug=False, use_reloader=False)


def _start_server_thread() -> threading.Thread:
    """
    Inicia o servidor Flask em uma thread daemon separada, permitindo
    que a thread principal gerencie a interface (Webview ou console).

    :return: (threading.Thread) Referência à thread do servidor Flask.
    """
    t = threading.Thread(target=_run_flask, daemon=True, name="flask-server")
    t.start()
    return t


# =====================================================================
# Funções — Modos de Execução (Webview / Browser)
# =====================================================================

def _run_webview_mode():
    """
    Modo padrão: inicia o servidor Flask em thread e abre a aplicação
    em uma janela nativa via pywebview (fullscreen, redimensionável).
    Encerra a aplicação quando a janela é fechada.

    :return: None. Encerra o processo ao fechar a janela.
    """
    import webview
    from app.version import APP_NAME

    log.info("Modo: Webview (janela nativa)")

    _start_server_thread()

    if not _wait_for_server(HOST, PORT):
        log.error("Servidor não respondeu a tempo. Abortando.")
        sys.exit(1)

    log.info("Servidor pronto. Abrindo janela Webview.")

    # ✅ Caminho absoluto do ícone

    webview.create_window(
        APP_NAME,
        f"http://{HOST}:{PORT}",
        width=1100,
        height=750,
        resizable=True,
        fullscreen=True,
    )
    webview.start(
        icon=icon_path(),  # ← ícone na taskbar e na janela
    )

    log.info("Janela Webview fechada. Encerrando.")


def _run_browser_mode():
    """
    Modo browser: aloca console Win32, inicia o servidor Flask em thread,
    abre o navegador padrão do sistema e mantém o processo vivo até
    Ctrl+C ou fechamento do console.

    :return: None. Encerra via KeyboardInterrupt ou fechamento da janela.
    """
    from app.version import APP_NAME, __version__

    _alloc_console()
    _add_console_log_handler()

    log.info("=" * 50)
    log.info(f"  {APP_NAME} v{__version__}")
    log.info("  Modo: Browser (console ativo)")
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


# =====================================================================
# Funções — Atualização Automática (Updater)
# =====================================================================

def _check_update():
    """
    Verifica se há atualizações disponíveis no repositório GitHub.
    Silencia erros para não travar a inicialização da aplicação.

    :return: None.
    """
    try:
        from app.updater import check_and_offer_update
        from app.version import __version__, APP_NAME, GITHUB_REPO

        log.info("Verificando atualizações...")
        check_and_offer_update(__version__, GITHUB_REPO, APP_NAME)
    except Exception as e:
        log.warning(f"Falha ao verificar atualização: {e}")


# =====================================================================
# Função Principal — Main
# =====================================================================

def main():
    """
    Ponto de entrada principal da aplicação. Detecta o modo de execução
    (Webview ou Browser), verifica atualizações e delega para o modo
    correspondente.

    :return: None.
    """
    log.info("Iniciando Sisport...")
    log.info(f"Dados em: {APP_DIR}")
    log.info(f"Log em:   {LOG_FILE}")

    # ── Garante instância única ──
    _mutex = _ensure_single_instance()

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
