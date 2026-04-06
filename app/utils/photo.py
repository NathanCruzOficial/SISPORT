# =====================================================================
# app/utils/photo.py
# Módulo de Gerenciamento de Fotos de Visitantes — Decodifica fotos
# recebidas como Data URL (base64) e retorna os bytes + mimetype
# para armazenamento direto no banco de dados (BLOB).
# Também realiza migração automática de fotos legadas (disco → banco).
# =====================================================================

# ─────────────────────────────────────────────────────────────────────
# Imports
# ─────────────────────────────────────────────────────────────────────
import base64
import re
import mimetypes
import logging

from ..extensions import db

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────
# Variáveis Globais — Regex de Data URL
# ─────────────────────────────────────────────────────────────────────

DATAURL_RE = re.compile(
    r"^data:image/(png|jpeg|jpg);base64,(.+)$", re.IGNORECASE | re.DOTALL
)


# =====================================================================
# Função — Parse de Data URL para bytes + mimetype
# =====================================================================

def parse_photo_data_url(photo_data_url: str) -> tuple[bytes, str]:
    """
    Decodifica uma foto em formato Data URL (base64) e retorna os bytes
    da imagem junto com o mimetype correspondente.

    :param photo_data_url: (str) Foto em formato Data URL base64
                           (ex: 'data:image/jpeg;base64,/9j/4AAQ...').
    :return: (tuple[bytes, str]) Tupla com (bytes_da_imagem, mimetype).
             Ex: (b'\\xff\\xd8...', 'image/jpeg')
    :raises ValueError: Se o Data URL for inválido, vazio ou corrompido.
    """
    photo_data_url = (photo_data_url or "").strip()
    m = DATAURL_RE.match(photo_data_url)
    if not m:
        raise ValueError("Foto inválida — formato Data URL não reconhecido.")

    ext = m.group(1).lower()
    mimetype = "image/png" if ext == "png" else "image/jpeg"
    b64 = m.group(2)

    img_bytes = base64.b64decode(b64, validate=True)

    if len(img_bytes) < 100:
        raise ValueError("Imagem vazia ou corrompida.")

    return img_bytes, mimetype


# =====================================================================
# Função — Migração Automática de Fotos (Disco → Banco)
# =====================================================================

def migrate_photos_from_disk():
    """
    Varre a pasta UPLOADS_DIR procurando fotos de visitantes que ainda
    estão em disco. Para cada foto encontrada:
      1. Localiza o visitante pelo CPF (nome da subpasta).
      2. Lê os bytes da imagem.
      3. Salva como BLOB no banco (photo_data + photo_mimetype).
      4. Apaga o arquivo e a subpasta do disco.

    Chamada automaticamente em create_app() durante a inicialização.
    Se a pasta UPLOADS_DIR não existir ou estiver vazia, retorna
    silenciosamente sem fazer nada.

    :return: None
    """
    from ..paths import UPLOADS_DIR
    from ..models.visitor import Visitor

    if not UPLOADS_DIR.is_dir():
        return

    # ── Coleta todas as fotos existentes ─────────────────────────
    photo_files = []
    for cpf_folder in UPLOADS_DIR.iterdir():
        if not cpf_folder.is_dir():
            continue
        for file in cpf_folder.iterdir():
            if file.is_file() and file.suffix.lower() in (".jpg", ".jpeg", ".png"):
                photo_files.append((cpf_folder.name, file))

    if not photo_files:
        # Pasta existe mas está vazia — tenta remover
        _cleanup_empty_uploads_dir(UPLOADS_DIR)
        return

    logger.info(f"[MIGRATE] {len(photo_files)} foto(s) encontrada(s) em disco. Migrando para o banco...")

    migrated = 0
    skipped  = 0
    errors   = 0
    files_to_delete = []

    for cpf, file_path in photo_files:

        visitor = db.session.query(Visitor).filter(
            Visitor.cpf == cpf
        ).one_or_none()

        if not visitor:
            logger.warning(f"[MIGRATE] CPF {cpf} — visitante não encontrado no banco. Pulando.")
            skipped += 1
            continue

        # Pula se já tem foto no banco
        if visitor.photo_data and len(visitor.photo_data) > 100:
            logger.info(f"[MIGRATE] {cpf} — já tem foto no banco. Apagando arquivo legado.")
            files_to_delete.append(file_path)
            skipped += 1
            continue

        try:
            img_bytes = file_path.read_bytes()

            if len(img_bytes) < 100:
                logger.warning(f"[MIGRATE] {cpf} — arquivo muito pequeno ({len(img_bytes)} bytes). Pulando.")
                skipped += 1
                continue

            mime, _ = mimetypes.guess_type(str(file_path))
            if not mime or not mime.startswith("image/"):
                mime = "image/jpeg"

            visitor.photo_data     = img_bytes
            visitor.photo_mimetype = mime

            files_to_delete.append(file_path)
            migrated += 1

            size_kb = len(img_bytes) / 1024
            logger.info(f"[MIGRATE] ✅ {cpf} — {file_path.name} ({size_kb:.1f} KB, {mime})")

        except Exception as e:
            logger.error(f"[MIGRATE] ❌ {cpf} — {e}")
            errors += 1

    # ── Commit no banco ──────────────────────────────────────────
    db.session.commit()

    # ── Apagar arquivos migrados ─────────────────────────────────
    for f in files_to_delete:
        try:
            f.unlink()
        except OSError as e:
            logger.warning(f"[MIGRATE] Não conseguiu apagar {f}: {e}")

    # ── Limpar subpastas e pasta raiz ────────────────────────────
    _cleanup_empty_uploads_dir(UPLOADS_DIR)

    logger.info(
        f"[MIGRATE] Concluído — Migrados: {migrated} | Pulados: {skipped} | Erros: {errors}"
    )


def _cleanup_empty_uploads_dir(uploads_dir):
    """
    Remove subpastas vazias e, se possível, a própria pasta uploads.

    :param uploads_dir: (Path) Caminho da pasta UPLOADS_DIR.
    :return: None
    """
    if not uploads_dir.is_dir():
        return

    # Remove subpastas vazias
    for cpf_folder in uploads_dir.iterdir():
        if cpf_folder.is_dir():
            try:
                cpf_folder.rmdir()
            except OSError:
                pass

    # Tenta remover a pasta raiz
    try:
        uploads_dir.rmdir()
        logger.info(f"[MIGRATE] 🗑️ Pasta '{uploads_dir}' removida (vazia).")
    except OSError:
        pass
