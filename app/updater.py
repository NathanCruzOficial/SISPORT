# =====================================================================
# updater.py
# Módulo de Atualização Automática — Verifica novas versões no GitHub,
# oferece ao usuário via diálogo e exibe progresso visual durante o
# download e instalação.
# =====================================================================

# ─────────────────────────────────────────────────────────────────────
# Imports
# ─────────────────────────────────────────────────────────────────────

import re
import sys
import time
import hashlib
import logging
import subprocess
from pathlib import Path

import requests
from packaging import version

from app.dialogs import ask_yes_no, show_info, show_error, ProgressWindow
from app.paths import UPDATE_DIR

log = logging.getLogger("sisport.updater")


class UpdateCancelled(RuntimeError):
    """Download interrompido pelo usuário via botão Cancelar."""


class DownloadFailedOffline(RuntimeError):
    """Todas as tentativas de download falharam — o app segue offline."""


# =====================================================================
# Funções — Verificação de Integridade
# =====================================================================

def _extract_sha256_from_body(body: str) -> str | None:
    """
    Extrai o hash SHA-256 do corpo (body) de uma release do GitHub.

    Procura pelo padrão 'sha256:<hash_hex>' no texto da release.

    :param body: (str) Corpo/descrição da release no GitHub.
    :return: (str | None) Hash SHA-256 em lowercase, ou None se não encontrado.
    """
    match = re.search(r"sha256:([a-fA-F0-9]{64})", body or "")
    return match.group(1).lower() if match else None


def _verify_file_hash(file_path: str, expected_hash: str) -> bool:
    """
    Verifica a integridade de um arquivo comparando seu hash SHA-256
    com o hash esperado publicado na release.

    :param file_path:     (str) Caminho absoluto do arquivo baixado.
    :param expected_hash: (str) Hash SHA-256 esperado (64 caracteres hex).
    :return: (bool) True se o hash corresponde, False caso contrário.
    """
    sha256 = hashlib.sha256()

    with open(file_path, "rb") as f:
        for block in iter(lambda: f.read(8192), b""):
            sha256.update(block)

    actual = sha256.hexdigest().lower()
    expected = expected_hash.lower()

    if actual != expected:
        log.error(
            f"Hash inválido!\n"
            f"  Esperado: {expected}\n"
            f"  Obtido:   {actual}"
        )
        return False

    log.info(f"Integridade verificada (SHA-256: {actual[:16]}...)")
    return True


# =====================================================================
# Funções — Comunicação com GitHub API
# =====================================================================

def _get_latest_releases(repo_id: int) -> list[dict]:
    """
    Consulta a API do GitHub para obter as releases mais recentes
    de um repositório público, usando o ID numérico imutável.

    Retorna uma lista de releases (estáveis e pre-releases),
    permitindo ao chamador decidir qual utilizar.

    :param repo_id: (int) ID numérico do repositório no GitHub.
    :return: (list[dict]) Lista de releases retornadas pela API.
    :raises requests.HTTPError: Se a requisição falhar (404, 403, etc.).
    """
    url = f"https://api.github.com/repositories/{repo_id}/releases"
    r = requests.get(url, params={"per_page": 10}, timeout=10)
    r.raise_for_status()
    return r.json()


def _find_best_release(
    releases: list[dict], current_version: str
) -> tuple[dict, bool] | tuple[None, None]:
    """
    Analisa a lista de releases e retorna a mais adequada para
    oferecer ao usuário, junto com a flag de obrigatoriedade.

    Prioridade:
        1. Release estável (prerelease=False) → atualização obrigatória.
        2. Pre-release (prerelease=True) → atualização opcional.

    Em ambos os casos, só retorna se a versão for maior que a atual.

    :param releases:        (list[dict]) Releases do GitHub.
    :param current_version: (str) Versão atualmente instalada.
    :return: (tuple) (release_dict, is_mandatory) ou (None, None).
    """
    current = version.parse(current_version)

    best_stable = None
    best_prerelease = None

    for rel in releases:
        if rel.get("draft", False):
            continue

        tag = (rel.get("tag_name") or "").lstrip("v").strip()
        if not tag:
            continue

        try:
            rel_version = version.parse(tag)
        except version.InvalidVersion:
            continue

        if rel_version <= current:
            continue

        if not rel.get("prerelease", False):
            if best_stable is None or rel_version > version.parse(
                (best_stable.get("tag_name") or "").lstrip("v")
            ):
                best_stable = rel
        else:
            if best_prerelease is None or rel_version > version.parse(
                (best_prerelease.get("tag_name") or "").lstrip("v")
            ):
                best_prerelease = rel

    # Estável tem prioridade e é obrigatória
    if best_stable:
        return best_stable, True

    # Pre-release é opcional
    if best_prerelease:
        return best_prerelease, False

    return None, None


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


def _cleanup_old_installers(keep: str | None = None) -> None:
    """
    Remove instaladores antigos do diretório de updates, mantendo
    somente o instalador da versão atual (se informado).

    :param keep: (str|None) Nome do arquivo que deve ser preservado.
    :return: None.
    """
    if not UPDATE_DIR.exists():
        return

    for entry in UPDATE_DIR.iterdir():
        try:
            if not entry.is_file():
                continue
            if entry.name.lower().endswith(".exe"):
                if keep and entry.name.lower() == keep.lower():
                    continue
                entry.unlink(missing_ok=True)
                log.info("Instalador antigo removido: %s", entry.name)
        except OSError as e:
            log.warning(
                "Falha ao remover instalador antigo %s: %s", entry.name, e
            )


# =====================================================================
# Funções — Download com Progresso Visual
# =====================================================================

def _update_reconnect_status(progress: ProgressWindow) -> None:
    """
    Coloca a janela de progresso em modo "reconectando" durante uma
    queda de conexão. A barra volta ao looping (indeterminada), para
    não parecer que o download congelou.
    """
    try:
        if progress is not None:
            if hasattr(progress, "set_indeterminate"):
                progress.set_indeterminate(
                    "Conexão interrompida. Tentando restabelecer conexão..."
                )
            elif hasattr(progress, "update_status"):
                progress.update_status(
                    "Conexão interrompida. Tentando restabelecer conexão..."
                )
    except Exception:
        pass


def _download_with_progress(
    url: str,
    filename: str,
    progress: ProgressWindow,
    reconnect_timeout: int = 60,
    retry_interval: int = 2,
) -> str:
    """
    Baixa o instalador exibindo progresso visual em tempo real.

    - Cancelamento pelo usuário → UpdateCancelled (intencional, sem erro).
    - Queda de conexão → tenta restabelecer a cada 2s por até 60s.
    - Se a conexão não voltar → DownloadFailedOffline.

    :param url:               (str) URL de download do asset.
    :param filename:          (str) Nome do arquivo de destino.
    :param progress:          (ProgressWindow) Janela de progresso ativa.
    :param reconnect_timeout: (int) Tempo total de reconexão em segundos.
    :param retry_interval:    (int) Intervalo entre tentativas de reconexão.
    :return: (str) Caminho absoluto do arquivo baixado.
    :raises UpdateCancelled: Se o usuário cancelar.
    :raises DownloadFailedOffline: Se a conexão não retornar a tempo.
    """
    UPDATE_DIR.mkdir(parents=True, exist_ok=True)
    file_path = UPDATE_DIR / filename

    if progress is not None and hasattr(progress, "reset_cancel"):
        progress.reset_cancel()
    if progress is not None and hasattr(progress, "set_cancel_visible"):
        progress.set_cancel_visible(True)

    reconnect_deadline = time.monotonic() + reconnect_timeout

    while True:
        # Respeita cancelamento também entre tentativas.
        if progress is not None and hasattr(progress, "is_cancelled"):
            if progress.is_cancelled():
                raise UpdateCancelled("Download cancelado pelo usuário.")

        try:
            if file_path.exists():
                file_path.unlink()

            with requests.get(url, stream=True, timeout=120) as r:
                r.raise_for_status()

                total = int(r.headers.get("content-length", 0))
                downloaded = 0
                chunk_size = 1024 * 256  # 256 KB

                with open(file_path, "wb") as f:
                    for chunk in r.iter_content(chunk_size=chunk_size):
                        if not chunk:
                            continue

                        if progress is not None and hasattr(progress, "is_cancelled"):
                            if progress.is_cancelled():
                                raise UpdateCancelled(
                                    "Download cancelado pelo usuário."
                                )

                        f.write(chunk)
                        downloaded += len(chunk)

                        if total > 0:
                            percent = (downloaded / total) * 100
                            downloaded_mb = downloaded / (1024 * 1024)
                            total_mb = total / (1024 * 1024)
                            progress.update_progress(
                                percent,
                                f"Baixando atualização... "
                                f"{downloaded_mb:.1f} MB / {total_mb:.1f} MB",
                            )
                        else:
                            downloaded_mb = downloaded / (1024 * 1024)
                            progress.update_status(
                                f"Baixando atualização... {downloaded_mb:.1f} MB"
                            )

            # Verifica se o download está completo
            if total > 0 and file_path.stat().st_size != total:
                raise RuntimeError("Download incompleto — tamanho não confere.")

            if progress is not None and hasattr(progress, "set_cancel_visible"):
                progress.set_cancel_visible(False)

            log.info(f"Download concluído: {file_path}")
            return str(file_path)

        except UpdateCancelled:
            raise

        except Exception as e:
            log.warning("Falha de conexão durante o download: %s", e)

            # Esgotou o tempo de reconexão → erro definitivo de conexão.
            if time.monotonic() >= reconnect_deadline:
                raise DownloadFailedOffline(
                    "Conexão com o servidor não restabelecida após 1 minuto."
                )

            # Barra volta ao looping indicando que o sistema está tentando
            # resolver sozinho, sem parecer travado.
            _update_reconnect_status(progress)

            # Aguarda o intervalo antes de tentar restabelecer.
            time.sleep(retry_interval)

            if progress is not None and hasattr(progress, "is_cancelled"):
                if progress.is_cancelled():
                    raise UpdateCancelled("Download cancelado pelo usuário.")

            if time.monotonic() >= reconnect_deadline:
                raise DownloadFailedOffline(
                    "Conexão com o servidor não restabelecida após 1 minuto."
                )

            # Volta ao início do laço e tenta novamente.
            continue


# =====================================================================
# Função Principal — Verificação e Oferta de Atualização
# =====================================================================

def check_and_offer_update(
    current_version: str,
    repo_id: int,
    app_name: str,
    progress_window=None,
) -> None:
    """
    Verifica se há uma versão mais recente no GitHub e oferece
    atualização ao usuário com feedback visual completo.

    Comportamento por tipo de release:
        - Release estável (prerelease=False) → OBRIGATÓRIA.
          Inicia o download automaticamente, sem perguntar. A janela
          não pode ser fechada manualmente (somente encerrando o
          processo).
        - Pre-release (prerelease=True) → OPCIONAL.
          O usuário pode aceitar ou recusar via diálogo Sim/Não.

    Caso não haja conexão/erro de rede, a atualização é ignorada
    silenciosamente e o app continua normalmente.

    :param current_version: (str) Versão atualmente instalada (ex: '1.2.0').
    :param repo_id:         (int) ID numérico do repositório no GitHub.
    :param app_name:        (str) Nome da aplicação para exibir nos diálogos.
    :param progress_window: (ProgressWindow|LoadingWindow|None) Janela já
        existente (splash) a ser reutilizada. Se None, uma ProgressWindow
        própria será criada.
    :return: None.
    """
    progress = progress_window
    mandatory = False

    # ── Consulta GitHub (offline/erro de rede seguem normalmente) ──
    try:
        log.info("Verificando atualizações no GitHub...")
        releases = _get_latest_releases(repo_id)
    except (requests.RequestException, OSError) as e:
        log.warning(f"Falha de rede ao verificar atualizações: {e}")
        if progress is not None:
            try:
                progress.update_status("Sem conexão — continuando...")
                progress.update()
            except Exception:
                pass
        return

    if not releases:
        log.info("Nenhuma release encontrada no repositório.")
        return

    # ── Seleciona a melhor release ──
    rel, mandatory = _find_best_release(releases, current_version)

    if rel is None:
        log.info("Aplicação já está na versão mais recente.")
        return

    latest = (rel.get("tag_name") or "").lstrip("v").strip()
    release_type = "OBRIGATÓRIA" if mandatory else "opcional"
    log.info(
        f"Versão atual: {current_version} | "
        f"Disponível: {latest} ({release_type})"
    )

    # ── Atualização obrigatória: sem pergunta ──
    if mandatory:
        log.info("Atualização obrigatória — iniciando automaticamente.")
        if progress is not None:
            progress.set_indeterminate(
                "Atualização obrigatória encontrada! Preparando download..."
            )
    else:
        accepted = ask_yes_no(
            f"{app_name} — Nova atualização disponível",
            "Encontramos uma nova versão (versão de testes) para você.\n\n"
            "Deseja baixar e instalar agora?\n"
            "Se preferir, pode continuar usando a versão atual.",
        )

        if not accepted:
            log.info("Usuário recusou a atualização opcional.")
            return

    # ── Localiza o instalador e hash ──
    asset = _pick_installer_asset(rel)
    installer_url = asset["browser_download_url"]
    file_name = asset["name"]
    expected_hash = _extract_sha256_from_body(rel.get("body", ""))

    if expected_hash:
        log.info(f"Hash SHA-256 encontrado na release: {expected_hash[:16]}...")
    else:
        log.warning("Nenhum hash SHA-256 publicado na release.")

    # ── Reutiliza splash ou cria uma ProgressWindow ──
    if progress is None:
        progress = ProgressWindow(f"{app_name} — Atualizando")
        progress.show()
        progress.update_progress(0, "Preparando download...")
    else:
        if hasattr(progress, "set_closable"):
            progress.set_closable(False)
        progress.update_progress(0, "Preparando download...")

    try:
        # ── Remove instaladores de versões anteriores ──
        _cleanup_old_installers()

        # ── Download com progresso e retry ──
        installer_path = _download_with_progress(
            installer_url, file_name, progress
        )

        # ── Verificação de integridade ──
        if expected_hash:
            progress.update_status("Verificando integridade do arquivo...")
            time.sleep(0.3)

            if not _verify_file_hash(installer_path, expected_hash):
                Path(installer_path).unlink(missing_ok=True)
                raise RuntimeError(
                    "Arquivo corrompido ou adulterado! "
                    "O hash SHA-256 não corresponde ao publicado na release.\n"
                    "O download foi removido por segurança."
                )

        # ── Instalação silenciosa ──
        progress.update_progress(100, "Download concluído!")
        time.sleep(0.3)

        # Splash continua vivo com indicador de instalação
        progress.set_indeterminate("Instalando nova versão... Por favor, aguarde.")
        if hasattr(progress, "set_closable"):
            progress.set_closable(True)

        proc = subprocess.Popen(
            [
                installer_path,
                "/VERYSILENT",        # sem wizard, sem janelas
                "/SUPPRESSMSGBOXES",  # suprime qualquer MessageBox
                "/NORESTART",         # nunca reinicia o Windows
            ],
            shell=False,
        )

        # Aguarda: o InnoSetup (CloseApplications=yes) manda WM_CLOSE no splash
        # quando for substituir o .exe. Nesse momento o app encerra e libera o
        # arquivo. Se o instalador terminar sem fechar (ex.: dev), encerramos
        # em seguida. O timeout de 120s é só rede de segurança.
        try:
            deadline = time.monotonic() + 120.0
            while proc.poll() is None and time.monotonic() < deadline:
                if hasattr(progress, "is_alive") and not progress.is_alive():
                    sys.exit(0)
                time.sleep(0.25)
        finally:
            progress.close()
            sys.exit(0)

    except UpdateCancelled:
        log.info("Download cancelado pelo usuário.")
        if progress is not None:
            try:
                progress.set_status("Cancelando operação...")
                progress.set_cancel_visible(False)
            except Exception:
                pass

        time.sleep(0.5)

        if mandatory:
            if progress is not None:
                progress.close()
            sys.exit(1)

        # Opcional: cancelamento intencional — segue normalmente, sem erro.
        return

    except DownloadFailedOffline:
        log.warning("Falha de conexão persistente — sem comunicação com o servidor.")

        if progress is not None:
            try:
                progress.set_cancel_visible(False)
            except Exception:
                pass

        if mandatory:
            show_error(
                f"{app_name} — Erro de Conexão",
                "Não foi possível conectar ao servidor de atualizações.\n"
                "Verifique sua conexão com a internet.\n\n"
                "O aplicativo será encerrado por segurança.",
            )
            if progress is not None:
                progress.close()
            sys.exit(1)

        # Atualização opcional: informa e segue em modo offline.
        show_error(
            f"{app_name} — Erro de Conexão",
            "Não foi possível conectar ao servidor de atualizações.\n"
            "O aplicativo continuará normalmente em modo offline.",
        )

        if progress is not None:
            try:
                if progress is progress_window:
                    progress.set_closable(True)
                progress.set_indeterminate("Sem conexão — continuando offline...")
            except Exception:
                pass
        return

    except Exception as e:
        log.error(f"Erro durante atualização: {e}", exc_info=True)

        # Se a janela era o splash compartilhado e a atualização era
        # opcional, mantém o splash aberto para o app continuar.
        if progress is not None and progress is progress_window and not mandatory:
            try:
                progress.set_closable(True)
                progress.set_indeterminate("Falha na atualização — continuando...")
            except Exception:
                pass
        else:
            if progress is not None:
                progress.close()

        error_msg = (
            f"Não foi possível concluir a atualização.\n\n"
            f"Erro: {e}\n\n"
        )

        if mandatory:
            error_msg += "O aplicativo será encerrado por segurança."
            show_error(f"{app_name} — Erro Crítico", error_msg)
            sys.exit(1)
        else:
            error_msg += "O aplicativo continuará normalmente."
            show_error(f"{app_name} — Erro", error_msg)
