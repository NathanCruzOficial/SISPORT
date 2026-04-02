# =====================================================================
# app/paths.py
# Caminhos Centralizados do SISPORT — Responsável por definir e
# gerenciar todos os diretórios e caminhos de arquivos utilizados
# pela aplicação (banco de dados, uploads, logs, configurações e
# backups), com suporte multiplataforma (Windows, macOS, Linux).
# =====================================================================

# ─────────────────────────────────────────────────────────────────────
# Imports
# ─────────────────────────────────────────────────────────────────────
from __future__ import annotations

import os
import sys
from pathlib import Path


# ─────────────────────────────────────────────────────────────────────
# Constantes — Nome do Diretório Raiz da Aplicação
# ─────────────────────────────────────────────────────────────────────

# Nome da pasta raiz criada no diretório de dados do sistema operacional.
APP_DIR_NAME = "SISPORT"


# =====================================================================
# Função Interna — Resolução do Diretório Base por Plataforma
# =====================================================================

def _get_base_dir() -> Path:
    """
    Determina o diretório base da aplicação de acordo com o sistema
    operacional, seguindo as convenções de cada plataforma:

    - Windows:  %LOCALAPPDATA%/SISPORT
                (fallback: ~/AppData/Local/SISPORT)
    - macOS:    ~/Library/Application Support/SISPORT
    - Linux:    $XDG_DATA_HOME/SISPORT
                (fallback: ~/.local/share/SISPORT)

    :return: (Path) Caminho absoluto do diretório raiz da aplicação.
    """
    if sys.platform == "win32":
        base = os.environ.get("LOCALAPPDATA")
        if not base:
            base = str(Path.home() / "AppData" / "Local")
        return Path(base) / APP_DIR_NAME

    elif sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / APP_DIR_NAME

    else:
        base = os.environ.get("XDG_DATA_HOME", str(Path.home() / ".local" / "share"))
        return Path(base) / APP_DIR_NAME
    




# ─────────────────────────────────────────────────────────────────────
# Localizadores dos arquivos do sistema
# ─────────────────────────────────────────────────────────────────────

# =====================================================================
# Funções — Resolução de Recursos do Sistema (PyInstaller)
# =====================================================================

def resource_path(relative_path: str) -> str:
    """
    Resolve caminho de recurso do SISTEMA (somente leitura).
    Arquivos empacotados pelo PyInstaller (_MEIPASS / _internal).

    Em dev:   caminho relativo ao diretório de trabalho.
    No .exe:  caminho dentro de _MEIPASS.

    :param relative_path: (str) Caminho relativo (ex: 'static/img/icone.ico').
    :return: (str) Caminho absoluto resolvido.
    """
    if getattr(sys, "_MEIPASS", False):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.abspath("."), relative_path)


def icon_path() -> str:
    """
    Retorna o caminho absoluto do ícone da aplicação.
    Funciona tanto em dev quanto no .exe empacotado.

    Ajuste o caminho relativo conforme a estrutura do seu projeto.

    :return: (str) Caminho do icone.ico.
    """
    return resource_path(os.path.join("icone.ico"))




# ─────────────────────────────────────────────────────────────────────
# Constantes — Diretórios da Aplicação
# ─────────────────────────────────────────────────────────────────────

APP_DIR     = _get_base_dir()        # Diretório raiz da aplicação
DB_DIR      = APP_DIR / "db"         # Banco de dados SQLite
UPLOADS_DIR = APP_DIR / "uploads"    # Fotos de visitantes (por CPF)
LOG_DIR     = APP_DIR / "logs"       # Arquivos de log
CONFIG_DIR  = APP_DIR / "config"     # Configurações (settings.json)
BACKUP_DIR  = APP_DIR / "backups"    # Backups do banco de dados
UPDATE_DIR  = APP_DIR / "update"     # Arquivo temporário do instalador baixado

# Tupla com todos os diretórios que devem ser criados na inicialização.
_ALL_DIRS = (DB_DIR, UPLOADS_DIR, LOG_DIR, CONFIG_DIR, BACKUP_DIR, UPDATE_DIR)


# =====================================================================
# Função — Criação dos Diretórios da Aplicação
# =====================================================================

def ensure_app_dirs() -> None:
    """
    Cria todos os diretórios necessários para o funcionamento da
    aplicação, caso ainda não existam. Chamada durante a inicialização
    na factory create_app().

    Diretórios criados: db, uploads, logs, config, backups.
    """
    for d in _ALL_DIRS:
        d.mkdir(parents=True, exist_ok=True)


# =====================================================================
# Funções — Resolução de Caminhos de Arquivos Específicos
# =====================================================================

def db_path(filename: str = "data.sqlite3") -> Path:
    """
    Retorna o caminho absoluto para um arquivo de banco de dados.

    :param filename: (str) Nome do arquivo (padrão: 'data.sqlite3').
    :return: (Path) Caminho completo: DB_DIR/<filename>.
    """
    return DB_DIR / filename


def log_path(filename: str = "sisport.log") -> Path:
    """
    Retorna o caminho absoluto para um arquivo de log.

    :param filename: (str) Nome do arquivo (padrão: 'sisport.log').
    :return: (Path) Caminho completo: LOG_DIR/<filename>.
    """
    return LOG_DIR / filename


def config_path(filename: str = "settings.json") -> Path:
    """
    Retorna o caminho absoluto para um arquivo de configuração.

    :param filename: (str) Nome do arquivo (padrão: 'settings.json').
    :return: (Path) Caminho completo: CONFIG_DIR/<filename>.
    """
    return CONFIG_DIR / filename
