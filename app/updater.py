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


# =====================================================================
# Funções — Download com Progresso Visual
# =====================================================================

def _download_with_progress(
    url: str, filename: str, progress: ProgressWindow, max_retries: int = 3
) -> str:
    """
    Baixa o instalador exibindo progresso visual em tempo real,
    com suporte a retentativas automáticas em caso de falha.

    :param url:         (str) URL de download do asset.
    :param filename:    (str) Nome do arquivo de destino.
    :param progress:    (ProgressWindow) Janela de progresso ativa.
    :param max_retries: (int) Número máximo de tentativas (padrão: 3).
    :return: (str) Caminho absoluto do arquivo baixado.
    :raises RuntimeError: Se todas as tentativas falharem.
    """
    UPDATE_DIR.mkdir(parents=True, exist_ok=True)
    file_path = UPDATE_DIR / filename

    for attempt in range(1, max_retries + 1):
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

            log.info(f"Download concluído: {file_path}")
            return str(file_path)

        except Exception as e:
            log.warning(f"Tentativa {attempt}/{max_retries} falhou: {e}")

            if attempt < max_retries:
                wait = attempt * 2  # backoff: 2s, 4s, 6s
                progress.update_status(
                    f"Falha no download. Tentando novamente em {wait}s..."
                )
                time.sleep(wait)
            else:
                raise RuntimeError(
                    f"Download falhou após {max_retries} tentativas: {e}"
                )


# =====================================================================
# Função Principal — Verificação e Oferta de Atualização
# =====================================================================

def check_and_offer_update(
    current_version: str, repo_id: int, app_name: str
) -> None:
    """
    Verifica se há uma versão mais recente no GitHub e oferece
    atualização ao usuário com feedback visual completo.

    Comportamento por tipo de release:
        - Release estável (prerelease=False) → OBRIGATÓRIA.
          O usuário é informado e a atualização prossegue sem opção
          de recusa. O aplicativo não inicia até que a atualização
          seja concluída.
        - Pre-release (prerelease=True) → OPCIONAL.
          O usuário pode aceitar ou recusar via diálogo Sim/Não.

    Segurança:
        - Verifica integridade do instalador via SHA-256 (se publicado).
        - Retry automático com backoff em caso de falha no download.
        - Arquivo corrompido/adulterado é removido e a atualização é abortada.

    Fluxo:
        1. Consulta as releases mais recentes via API do GitHub (por ID).
        2. Seleciona a melhor release disponível (estável > pre-release).
        3. Exibe diálogo adequado (obrigatório ou opcional).
        4. Abre janela de progresso visual.
        5. Baixa o instalador com barra de progresso e retry.
        6. Verifica integridade SHA-256 (se hash disponível).
        7. Executa o instalador e encerra a aplicação.

    :param current_version: (str) Versão atualmente instalada (ex: '1.2.0').
    :param repo_id:         (int) ID numérico do repositório no GitHub.
    :param app_name:        (str) Nome da aplicação para exibir nos diálogos.
    :return: None.
    """
    progress = None
    mandatory = False  # valor padrão seguro para o bloco except

    try:
        # ── Ignora versão de desenvolvimento ──
        if current_version == "dev":
            log.info("Versão de desenvolvimento detectada — update ignorado.")
            return

        # ── Consulta GitHub ──
        log.info("Verificando atualizações no GitHub...")
        releases = _get_latest_releases(repo_id)

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

        # ── Diálogo ao usuário ──
                # ── Diálogo ao usuário ──
        if mandatory:
            accepted = ask_yes_no(
                f"{app_name} — Atualização Obrigatória",
                f"Uma atualização obrigatória está disponível.\n\n"
                f"  Versão instalada:   {current_version}\n"
                f"  Versão disponível:  {latest}\n\n"
                "O aplicativo não pode continuar sem esta atualização.\n\n"
                "Deseja atualizar agora?",
            )

            if not accepted:
                log.info(
                    "Usuário recusou atualização obrigatória — "
                    "encerrando aplicação."
                )
                sys.exit(0)
        else:
            accepted = ask_yes_no(
                f"{app_name} — Atualização Disponível",
                f"Uma nova versão (pré-release) do {app_name} "
                f"está disponível!\n\n"
                f"  Versão instalada:   {current_version}\n"
                f"  Versão disponível:  {latest}\n\n"
                "Esta é uma versão de teste. Deseja atualizar agora?",
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

        # ── Abre janela de progresso ──
        progress = ProgressWindow(f"{app_name} — Atualizando")
        progress.show()
        progress.update_progress(0, "Preparando download...")

        time.sleep(0.5)

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

        # ── Instalação ──
        progress.update_progress(100, "Download concluído e verificado!")
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
