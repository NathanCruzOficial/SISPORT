import base64
import os
import re
from flask import current_app

def sanitize_cpf(cpf: str) -> str:
    """Remove caracteres não numéricos do CPF (para pasta)."""
    return re.sub(r"\D+", "", cpf or "")

def save_or_replace_profile_photo(data_url: str, cpf: str) -> str:
    """
    Salva (ou substitui) a foto do visitante em uploads/<cpf>/foto.jpg.
    Retorna o caminho RELATIVO (ex.: '12345678900/foto.jpg').
    """
    if not data_url or "," not in data_url:
        raise ValueError("Foto inválida (data URL ausente).")

    header, b64data = data_url.split(",", 1)

    # Vamos padronizar para jpg (mais leve).
    ext = "jpg"
    if "image/png" in header:
        # Aceita png, mas ainda salvaremos como jpg se quiser (aqui manteremos jpg).
        ext = "jpg"

    cpf_dir = sanitize_cpf(cpf)
    if not cpf_dir:
        raise ValueError("CPF inválido para salvar foto.")

    base_upload = current_app.config["UPLOAD_FOLDER"]
    target_dir = os.path.join(base_upload, cpf_dir)
    os.makedirs(target_dir, exist_ok=True)

    filename = f"foto.{ext}"
    abs_path = os.path.join(target_dir, filename)

    raw = base64.b64decode(b64data)
    with open(abs_path, "wb") as f:
        f.write(raw)

    return f"{cpf_dir}/{filename}"
