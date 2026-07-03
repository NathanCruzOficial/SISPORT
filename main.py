# =====================================================================
# main.py
# Ponto de Entrada Unificado — Responsável por inicializar a aplicação
# Sisport em dois modos: janela nativa (Webview) ou navegador padrão.
# Gerencia logging, detecção de tecla SHIFT, alocação de console
# Win32, servidor Flask em thread, verificação de atualizações e
# atualização automática do banco de dados via Flask-Migrate/Alembic.
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

# =====================================================================
# Imports
# =====================================================================
import ctypes
import logging
import platform
import sys
import threading
import time
import webbrowser
import shutil
from datetime import datetime
from pathlib import Path

from app.paths import APP_DIR, ensure_app_dirs, log_path, icon_path


# =====================================================================
# AppUserModelID (Windows)
# =====================================================================
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
# Variáveis Globais — Banco de Dados / Migrations
# =====================================================================

# Se você já tem usuários com bancos criados antes do Alembic,
# gere primeiro uma migration "baseline schema".
#
# Depois de gerar essa migration, você pode colocar aqui o ID dela.
#
# Exemplo:
#   LEGACY_BASELINE_REVISION = "a1b2c3d4e5f6"
#
# Se ficar como None, bancos legados serão marcados como "head".
# Isso é aceitável somente na primeira versão com migrations.
#
# RECOMENDAÇÃO:
# Depois que você criar novas migrations além da baseline, preencha
# esta constante com o ID da migration baseline.
LEGACY_BASELINE_REVISION = "71cb9dafd972"


# =====================================================================
# Detecção de instância existente do sistema
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
# Funções — Banco de Dados / Migrations
# =====================================================================

def _get_migrations_dir() -> str:
    """
    Localiza o diretório de migrations do Alembic.

    Em desenvolvimento:
        ./migrations

    Em build PyInstaller:
        tenta localizar migrations dentro de sys._MEIPASS, caso tenha
        sido incluída no .spec.

    :return: Caminho string para o diretório migrations.
    """
    if getattr(sys, "frozen", False):
        base_dir = Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
        bundled_migrations = base_dir / "migrations"

        if bundled_migrations.exists():
            return str(bundled_migrations)

    project_migrations = Path(__file__).resolve().parent / "migrations"

    if project_migrations.exists():
        return str(project_migrations)

    return "migrations"


def _get_sqlite_database_path(app) -> Path | None:
    """
    Obtém o caminho físico do arquivo SQLite a partir da configuração
    SQLALCHEMY_DATABASE_URI.

    :param app: Instância Flask.
    :return: Path do banco SQLite ou None se não for SQLite.
    """
    try:
        from sqlalchemy.engine import make_url

        uri = app.config.get("SQLALCHEMY_DATABASE_URI")

        if not uri:
            return None

        url = make_url(uri)

        if url.drivername != "sqlite":
            return None

        database = url.database

        if not database or database == ":memory:":
            return None

        db_path = Path(database)

        # Flask-SQLAlchemy 3.x trata caminhos relativos SQLite como
        # relativos à pasta instance da aplicação.
        if not db_path.is_absolute():
            db_path = Path(app.instance_path) / db_path

        return db_path.resolve()
    except Exception as e:
        log.warning(f"Não foi possível identificar o caminho do banco SQLite: {e}")
        return None


def fazer_backup_banco(caminho_banco: str | Path) -> Path | None:
    """
    Faz backup do arquivo SQLite antes de aplicar migrations.

    :param caminho_banco: Caminho do arquivo de banco.
    :return: Caminho do backup criado ou None se não houve backup.
    """
    origem = Path(caminho_banco)

    if not origem.exists():
        log.info("Banco ainda não existe. Backup não necessário.")
        return None

    pasta_backup = origem.parent / "backups"
    pasta_backup.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    destino = pasta_backup / f"{origem.stem}_backup_{timestamp}{origem.suffix}"

    shutil.copy2(origem, destino)

    log.info(f"Backup do banco criado em: {destino}")
    return destino


def _database_has_tables(db) -> bool:
    """
    Verifica se o banco possui tabelas.

    :param db: Instância SQLAlchemy.
    :return: True se houver tabelas, False caso contrário.
    """
    from sqlalchemy import inspect

    inspector = inspect(db.engine)
    tables = inspector.get_table_names()

    # Ignora tabela interna do Alembic caso ela seja a única.
    real_tables = [table for table in tables if table != "alembic_version"]

    return len(real_tables) > 0


def _database_has_alembic_version(db) -> bool:
    """
    Verifica se o banco já possui controle de versão do Alembic.

    :param db: Instância SQLAlchemy.
    :return: True se existir tabela alembic_version, False caso contrário.
    """
    from sqlalchemy import inspect

    inspector = inspect(db.engine)
    tables = inspector.get_table_names()

    return "alembic_version" in tables


def _stamp_legacy_database_if_needed(db, migrations_dir: str):
    """
    Bancos antigos criados com db.create_all() não possuem a tabela
    alembic_version. Nesses casos, precisamos marcar o banco como estando
    em uma revisão base para que as próximas migrations funcionem.

    :param db: Instância SQLAlchemy.
    :param migrations_dir: Diretório de migrations.
    :return: None.
    """
    from flask_migrate import stamp

    has_tables = _database_has_tables(db)
    has_alembic = _database_has_alembic_version(db)

    if not has_tables:
        log.info("Banco vazio/novo detectado. Alembic criará a estrutura via upgrade.")
        return

    if has_alembic:
        log.info("Banco já possui controle Alembic.")
        return

    revision = LEGACY_BASELINE_REVISION or "head"

    log.warning(
        "Banco legado detectado sem tabela alembic_version. "
        f"Marcando banco como revisão Alembic: {revision}"
    )

    stamp(directory=migrations_dir, revision=revision)

    log.info("Banco legado marcado com sucesso no Alembic.")


def _run_post_migration_tasks():
    """
    Executa tarefas de dados que devem acontecer depois do upgrade
    estrutural do banco.

    Essas funções devem ser idempotentes, ou seja, seguras para rodar
    várias vezes sem duplicar dados ou corromper informações.

    :return: None.
    """
    try:
        from app.seed import seed_defaults

        log.info("Sincronizando dados padrão...")
        seed_defaults()
        log.info("Dados padrão sincronizados.")
    except Exception as e:
        log.warning(f"Falha ao executar seed_defaults(): {e}")

    try:
        from app.utils.photo import migrate_photos_from_disk

        log.info("Verificando migração de fotos do disco para o banco...")
        migrate_photos_from_disk()
        log.info("Migração/verificação de fotos concluída.")
    except Exception as e:
        log.warning(f"Falha ao executar migrate_photos_from_disk(): {e}")


def atualizar_banco(app):
    """
    Atualiza automaticamente o banco de dados usando Flask-Migrate/Alembic.

    Fluxo:
      1. Entra no app_context.
      2. Faz backup do SQLite, se o arquivo existir.
      3. Detecta banco legado sem alembic_version.
      4. Marca banco legado com stamp, se necessário.
      5. Aplica migrations pendentes com upgrade().
      6. Executa tarefas pós-migration.

    :param app: Instância Flask criada por create_app().
    :return: None.
    """
    from app.extensions import db
    from flask_migrate import upgrade

    migrations_dir = _get_migrations_dir()

    with app.app_context():
        log.info("Iniciando verificação/atualização do banco de dados...")
        log.info(f"Diretório de migrations: {migrations_dir}")

        sqlite_path = _get_sqlite_database_path(app)

        if sqlite_path:
            fazer_backup_banco(sqlite_path)
        else:
            log.info("Banco não é SQLite ou caminho não identificado. Backup automático ignorado.")

        _stamp_legacy_database_if_needed(db, migrations_dir)

        log.info("Aplicando migrations pendentes...")
        upgrade(directory=migrations_dir)
        log.info("Migrations aplicadas com sucesso.")

        _run_post_migration_tasks()

        log.info("Banco de dados atualizado com sucesso.")


# =====================================================================
# Funções — Servidor Flask (Thread e Polling)
# =====================================================================

def _wait_for_server(host: str, port: int, timeout: float = 60.0) -> bool:
    """
    Aguarda o servidor Flask ficar pronto fazendo polling via conexão
    TCP. Mais confiável que um sleep fixo.

    :param host:    (str)   Endereço do servidor.
    :param port:    (int)   Porta do servidor.
    :param timeout: (float) Tempo máximo de espera em segundos.
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

    Antes de iniciar o servidor, aplica automaticamente as migrations
    pendentes do banco de dados.

    :return: None.
    """
    from app import create_app

    app = create_app()

    try:
        atualizar_banco(app)
    except Exception as e:
        log.exception(f"Falha crítica ao atualizar banco de dados: {e}")
        raise

    log.info(f"Flask iniciando em http://{HOST}:{PORT}")

    app.run(
        host=HOST,
        port=PORT,
        debug=True,
        use_reloader=False,
    )


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

    webview.create_window(
        APP_NAME,
        f"http://{HOST}:{PORT}",
        width=1100,
        height=750,
        resizable=True,
        fullscreen=True,
    )

    webview.start(
        icon=icon_path(),
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
        from app.version import __version__, APP_NAME, GITHUB_REPO_ID

        log.info("Verificando atualizações...")
        check_and_offer_update(__version__, GITHUB_REPO_ID, APP_NAME)
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

    # Garante instância única.
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
