# =====================================================================
# photo_service.py
# Módulo de Gerenciamento de Fotos de Visitantes — Responsável por
# sanitizar o CPF para uso como nome de diretório, decodificar fotos
# recebidas em formato Data URL (base64) e salvá-las (ou substituí-las)
# no sistema de arquivos, organizadas por CPF do visitante.
# =====================================================================

# ─────────────────────────────────────────────────────────────────────
# Imports
# ─────────────────────────────────────────────────────────────────────
import base64
import os
import re
from flask import current_app


# =====================================================================
# Função — Sanitização de CPF para Nome de Diretório
# =====================================================================

def sanitize_cpf(cpf: str) -> str:
    """
    Remove todos os caracteres não numéricos do CPF, retornando
    apenas os dígitos. Utilizado para gerar nomes de pasta seguros.

    Exemplo: '123.456.789-00' → '12345678900'

    :param cpf: (str) CPF com ou sem formatação.
    :return: (str) Somente os dígitos do CPF (ou string vazia se nulo).
    """
    return re.sub(r"\D+", "", cpf or "")


# =====================================================================
# Função — Salvamento / Substituição de Foto de Perfil
# =====================================================================

def save_or_replace_profile_photo(data_url: str, cpf: str) -> str:
    """
    Decodifica uma foto em formato Data URL (base64) e salva no disco,
    substituindo qualquer foto anterior do mesmo visitante.

    Estrutura de armazenamento:
        UPLOAD_FOLDER/<cpf_sanitizado>/foto.jpg
        Exemplo: uploads/12345678900/foto.jpg

    Fluxo:
    1. Valida a presença do separador ',' na Data URL.
    2. Extrai o header e o payload base64 (sempre salva como .jpg).
    3. Sanitiza o CPF para uso como nome de diretório.
    4. Cria a pasta do visitante dentro de UPLOAD_FOLDER (se necessário).
    5. Decodifica os bytes e sobrescreve o arquivo no disco.
    6. Retorna o caminho relativo para armazenamento no banco.

    :param data_url: (str) Foto em formato Data URL base64
                     (ex: 'data:image/jpeg;base64,/9j/4AAQ...').
    :param cpf:      (str) CPF do visitante (com ou sem formatação).
    :return: (str) Caminho relativo da foto salva (ex: '12345678900/foto.jpg').
    :raises ValueError: Se a Data URL for ausente/inválida ou o CPF for vazio.
    """
    if not data_url or "," not in data_url:
        raise ValueError("Foto inválida (data URL ausente).")

    header, b64data = data_url.split(",", 1)

    # Padroniza para jpg (mais leve), independentemente do tipo original.
    ext = "jpg"
    if "image/png" in header:
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
