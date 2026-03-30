# =====================================================================
# photo.py
# Módulo de Gerenciamento de Fotos de Visitantes — Responsável por
# decodificar fotos recebidas como Data URL (base64), salvá-las no
# sistema de arquivos organizado por CPF e retornar o caminho
# relativo para servir via rota estática (/uploads/<path>).
# =====================================================================

# ─────────────────────────────────────────────────────────────────────
# Imports
# ─────────────────────────────────────────────────────────────────────
import base64
import os
import re
from flask import current_app


# ─────────────────────────────────────────────────────────────────────
# Variáveis Globais — Regex de Data URL
# ─────────────────────────────────────────────────────────────────────

# Expressão regular para validar e extrair extensão + payload base64
# de uma Data URL de imagem (suporta PNG e JPEG/JPG).
DATAURL_RE = re.compile(r"^data:image/(png|jpeg|jpg);base64,(.+)$", re.IGNORECASE)


# =====================================================================
# Função — Salvamento de Foto a partir de Data URL
# =====================================================================

def save_visitor_photo_from_dataurl(*, cpf: str, photo_data_url: str) -> str:
    """
    Decodifica uma foto em formato Data URL (base64) e salva no disco,
    organizada em subpasta por CPF do visitante.

    Estrutura de armazenamento:
        UPLOAD_FOLDER/<cpf>/foto.<ext>
        Exemplo: uploads/19780798773/foto.jpg

    Fluxo:
    1. Valida o Data URL contra o regex DATAURL_RE.
    2. Extrai a extensão (normaliza jpeg/jpg → jpg) e o payload base64.
    3. Decodifica os bytes da imagem.
    4. Cria a pasta do visitante (por CPF) dentro de UPLOAD_FOLDER.
    5. Salva o arquivo binário no disco.
    6. Retorna o caminho relativo para uso na rota /uploads/<path>.

    :param cpf:            (str) CPF do visitante (usado como nome da subpasta).
    :param photo_data_url: (str) Foto em formato Data URL base64
                           (ex: 'data:image/jpeg;base64,/9j/4AAQ...').
    :return: (str) Caminho relativo da foto salva (ex: '19780798773/foto.jpg').
    :raises ValueError: Se o Data URL for inválido ou não corresponder ao formato esperado.
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
