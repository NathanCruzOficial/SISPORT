# =====================================================================
# masks.py
# Funções de Mascaramento de Dados Pessoais — Responsável por aplicar
# máscaras de privacidade em dados sensíveis de visitantes (nome,
# nome da mãe, telefone e e-mail) para exibição em relatórios e
# interfaces onde a informação completa não deve ser exposta.
# =====================================================================

# ─────────────────────────────────────────────────────────────────────
# Imports
# ─────────────────────────────────────────────────────────────────────
import re


# ─────────────────────────────────────────────────────────────────────
# Variáveis Globais — Tokens Ignorados
# ─────────────────────────────────────────────────────────────────────

# Partículas comuns em nomes brasileiros que são ignoradas ao gerar
# iniciais (preposições e conjunções sem valor identificador).
_SKIP_TOKENS = {"da", "de", "do", "das", "dos", "e"}


# =====================================================================
# Funções — Mascaramento de Nomes
# =====================================================================

def mask_name_first_plus_initials(value: str | None, *, uppercase: bool = True) -> str:
    """
    Mantém o primeiro nome completo e substitui os demais por iniciais,
    ignorando partículas comuns (da, de, do, etc.).

    Exemplo: "NATHAN DA CRUZ CARDOSO" → "NATHAN C. C."

    :param value:     (str | None) Nome completo do visitante.
    :param uppercase: (bool) Se True, retorna em caixa alta (padrão: True).
    :return: (str) Nome mascarado com iniciais. Retorna "" se vazio/None.
    """
    if not value:
        return ""

    # normaliza espaços
    raw = " ".join(value.strip().split())
    if not raw:
        return ""

    parts = raw.split(" ")
    first = parts[0]
    rest = parts[1:]

    initials = []
    for p in rest:
        token = p.strip().strip(".")
        if not token:
            continue

        # se quiser ignorar "da/de/do/das/dos/e", comente este bloco
        if token.lower() in _SKIP_TOKENS:
            continue

        initials.append(token[0] + ".")

    result = first
    if initials:
        result += " " + " ".join(initials)

    return result.upper() if uppercase else result


def mask_mom_name_keep_first(value: str | None, *, uppercase: bool = True) -> str:
    """
    Mantém apenas o primeiro nome da mãe, descartando sobrenomes
    e partículas. Útil para exibição parcial em relatórios.

    Exemplo: "Maria de Souza" → "MARIA"

    :param value:     (str | None) Nome completo da mãe.
    :param uppercase: (bool) Se True, retorna em caixa alta (padrão: True).
    :return: (str) Primeiro nome da mãe. Retorna "" se vazio/None.
    """
    if not value:
        return ""
    parts = [p for p in value.strip().split() if p]
    if not parts:
        return ""
    res = parts[0]
    return res.upper() if uppercase else res


# =====================================================================
# Funções — Mascaramento de Telefone
# =====================================================================

def mask_phone_last4(value: str | None) -> str:
    """
    Mascara o telefone mantendo apenas os últimos 4 dígitos visíveis.
    Aceita qualquer formato de entrada (com ou sem pontuação).

    Exemplo: "(21) 99876-1234" → "(**) *****-1234"

    :param value: (str | None) Telefone em qualquer formato.
    :return: (str) Telefone mascarado. Retorna "" se vazio/None.
    """
    if not value:
        return ""
    digits = re.sub(r"\D+", "", value)
    if len(digits) < 4:
        return "*" * len(digits)
    return f"(**) *****-{digits[-4:]}"


# =====================================================================
# Funções — Mascaramento de E-mail
# =====================================================================

def mask_email_2first_2last_before_at(value: str | None) -> str:
    """
    Mascara a parte local do e-mail, mantendo os 2 primeiros e os
    2 últimos caracteres antes do '@'. O domínio permanece visível.

    Exemplo: "joaosilva@gmail.com" → "jo**va@gmail.com"

    Tratamento por tamanho da parte local:
    - Até 2 caracteres:  mantém o primeiro + "*"
    - 3 caracteres:      mantém os 2 primeiros + "*"
    - 4+ caracteres:     mantém 2 primeiros + "**" + 2 últimos

    :param value: (str | None) Endereço de e-mail completo.
    :return: (str) E-mail mascarado. Retorna "" se vazio/None ou sem '@'.
    """
    if not value or "@" not in value:
        return ""
    local, domain = value.split("@", 1)
    local = local.strip()
    domain = domain.strip()
    if not local or not domain:
        return ""

    if len(local) <= 2:
        masked_local = local[:1] + "*"
    elif len(local) == 3:
        masked_local = local[:2] + "*"
    else:
        masked_local = f"{local[:2]}**{local[-2:]}"
    return f"{masked_local}@{domain}"
