# =================================================================
# app/defaults.py
# Valores padrão de TODAS as configurações do SISPORT
# =================================================================
#
# ➜  Adicionou uma config nova? Basta adicionar aqui.
#    O seed grava no banco automaticamente na próxima execução.
#    O get_setting() já usa como fallback.
#    O snapshot é gerado automaticamente.
#
# Formato:
#   "chave": ("valor_padrão", "tipo")
#
# Tipos suportados:
#   "str"       → retorna string direto
#   "int"       → converte pra int
#   "bool"      → "1" = True, qualquer outra coisa = False
#   "list"      → split por vírgula, retorna lista limpa
#   "password"  → retorna True/False se existe valor (nunca expõe o hash)
# =================================================================

DEFAULTS: dict[str, tuple[str, str]] = {
    # ── Geral — Instituição ─────────────────────────────────────
    "inst_name":                        ("Grupamento de Unidades Escola / 9ª Brigada de Infantaria Motorizada", "str"),
    "inst_short_name":                  ("GUEs/9ª Bda Inf Mtz", "str"),
    "header_line_1":                    ("", "str"),
    "header_line_2":                    ("", "str"),

    # ── Segurança ───────────────────────────────────────────────
    "admin_password_hash":              ("", "password"),

    # ── Visitantes ──────────────────────────────────────────────
    "visitor_categories":               ("civil,militar,ex-militar,prestador", "list"),
    "visitor_father_name_required":     ("0", "bool"),   # ← NOVO
    "visitor_email_required":           ("0", "bool"),    # ← NOVO
    "visitor_empresa_required":         ("0", "bool"),    # ← NOVO


    # ── Retenção / Banco de Dados ───────────────────────────────
    "retention_days":                   ("0", "int"),
    "retention_action":                 ("delete", "str"),
    "retention_anonymize_delete_photo": ("0", "bool"),
}


# =================================================================
# Conversores — transforma o valor string do banco pro tipo certo
# =================================================================

def _convert(value: str, type_hint: str):
    """Converte o valor bruto (string) para o tipo definido."""
    match type_hint:
        case "int":
            try:
                return int(value)
            except (ValueError, TypeError):
                return 0
        case "bool":
            return value == "1"
        case "list":
            return [item.strip() for item in value.split(",") if item.strip()]
        case "password":
            return bool(value)
        case _:
            return value


def get_default(key: str) -> str:
    """Retorna apenas o valor padrão bruto (string) de uma chave."""
    entry = DEFAULTS.get(key)
    return entry[0] if entry else ""


def build_snapshot(get_setting_fn) -> dict:
    """
    Gera o snapshot COMPLETO de configurações para o template.
    Lê cada chave do DEFAULTS, busca no banco e converte.

    Também gera versões auxiliares:
      - listas ganham uma versão "_raw" (string original)
    """
    snap = {}

    for key, (default, type_hint) in DEFAULTS.items():
        raw_value = get_setting_fn(key, default)

        # Nome no snapshot: password vira "has_<key>"
        if type_hint == "password":
            snap_key = f"has_{key}" if not key.startswith("has_") else key
        else:
            snap_key = key

        snap[snap_key] = _convert(raw_value, type_hint)

        # Lista: adiciona versão _raw para formulários
        if type_hint == "list":
            snap[f"{key}_raw"] = raw_value

    return snap
