import base64
import os
import re
from flask import current_app

DATAURL_RE = re.compile(r"^data:image/(png|jpeg|jpg);base64,(.+)$", re.IGNORECASE)

def save_visitor_photo_from_dataurl(*, cpf: str, photo_data_url: str) -> str:
    """
    Salva foto do visitante em UPLOAD_FOLDER/<cpf>/foto.jpg (ou png)
    e retorna o caminho relativo para servir via /uploads/<path>.
    Ex: '19780798773/foto.jpg'
    """
    photo_data_url = (photo_data_url or "").strip()
    m = DATAURL_RE.match(photo_data_url)
    if not m:
        raise ValueError("Foto inválida.")

    ext = m.group(1).lower()
    ext = "jpg" if ext in ("jpeg", "jpg") else "png"
    b64 = m.group(2)

    img_bytes = base64.b64decode(b64, validate=True)

    base = current_app.config["UPLOAD_FOLDER"]  # ex: app/uploads
    folder = os.path.join(base, cpf)
    os.makedirs(folder, exist_ok=True)

    filename = f"foto.{ext}"
    abs_path = os.path.join(folder, filename)

    with open(abs_path, "wb") as f:
        f.write(img_bytes)

    # caminho relativo usado na rota /uploads/<path:filename>
    return f"{cpf}/{filename}"
