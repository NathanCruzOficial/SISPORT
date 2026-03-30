# =====================================================================
# validators.py
# Módulo de Validações — Reúne funções utilitárias para normalização
# e validação de CPF, telefone e e-mail. Utilizado como camada de
# verificação antes da persistência de dados no sistema.
# =====================================================================

# ─────────────────────────────────────────────────────────────────────
# Imports
# ─────────────────────────────────────────────────────────────────────
import re
import unicodedata


# =====================================================================
# Funções — Normalização e Validação de Telefone
# =====================================================================

def normalize_phone(value: str) -> str:
    """
    Remove todos os caracteres não numéricos de um telefone.

    :param value: (str) Telefone com ou sem formatação.
    :return: (str) Apenas os dígitos do telefone. Ex: '(21) 99999-0000' → '21999990000'.
    """
    return re.sub(r"\D", "", value or "")


# =====================================================================
# Funções — Normalização e Validação de CPF
# =====================================================================

def normalize_cpf(value: str) -> str:
    """
    Remove todos os caracteres não numéricos de um CPF.

    :param value: (str) CPF com ou sem formatação.
    :return: (str) Apenas os dígitos do CPF. Ex: '123.456.789-09' → '12345678909'.
    """
    return re.sub(r"\D", "", value or "")

def is_valid_cpf(value: str) -> bool:
    """
    Valida um CPF utilizando o algoritmo oficial dos dígitos verificadores.
    Rejeita sequências repetidas (ex: '111.111.111-11') e CPFs com
    tamanho diferente de 11 dígitos.

    :param value: (str) CPF a ser validado (com ou sem formatação).
    :return: (bool) True se o CPF for válido, False caso contrário.
    """
    cpf = normalize_cpf(value)

    # Precisa ter 11 dígitos
    if len(cpf) != 11:
        return False

    # Rejeita CPFs com todos os dígitos iguais (000..., 111..., etc.)
    if cpf == cpf[0] * 11:
        return False

    # Cálculo do 1º dígito verificador
    sum1 = sum(int(cpf[i]) * (10 - i) for i in range(9))
    d1 = (sum1 * 10) % 11
    d1 = 0 if d1 == 10 else d1

    # Cálculo do 2º dígito verificador
    sum2 = sum(int(cpf[i]) * (11 - i) for i in range(10))
    d2 = (sum2 * 10) % 11
    d2 = 0 if d2 == 10 else d2

    return cpf[-2:] == f"{d1}{d2}"


# =====================================================================
# Variáveis Globais — Regex de E-mail
# =====================================================================

# Expressão regular compilada para validação de e-mail conforme RFC 5321.
# Verifica tamanho total (≤254), local-part (≤64), caracteres permitidos
# e estrutura do domínio (ao menos um ponto, sem hífen no início/fim).
_EMAIL_RE = re.compile(
    r"^(?=.{1,254}$)"                    # tamanho total
    r"(?=.{1,64}@)"                      # local-part <= 64
    r"[A-Za-z0-9]"                       # começa com alfanum
    r"(?:[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]{0,62}[A-Za-z0-9])?"
    r"@"
    r"(?!-)"                             # domínio não começa com hífen
    r"[A-Za-z0-9-]{1,63}"
    r"(?:\.[A-Za-z0-9-]{1,63})+$"        # exige ao menos um ponto
    r"$"
)


# =====================================================================
# Funções — Normalização e Validação de E-mail
# =====================================================================

def normalize_email(raw: str) -> str:
    """
    Normaliza um e-mail para validação e armazenamento: remove espaços,
    aplica normalização Unicode (NFKC) e converte para minúsculo.

    :param raw: (str | None) E-mail bruto informado pelo usuário.
    :return: (str) E-mail normalizado em minúsculo, ou string vazia se None.
    """
    if raw is None:
        return ""
    s = str(raw).strip()
    s = unicodedata.normalize("NFKC", s)
    return s.lower()

def is_valid_email(raw: str) -> bool:
    """
    Valida um e-mail de forma prática e robusta. Verifica ausência de
    espaços, pontos consecutivos, pontos no início/fim, conformidade
    com a regex _EMAIL_RE e regras adicionais no domínio.

    :param raw: (str) E-mail a ser validado.
    :return: (bool) True se o e-mail for válido, False caso contrário.
    """
    email = normalize_email(raw)
    if not email:
        return False

    if any(ch.isspace() for ch in email):
        return False
    if ".." in email:
        return False
    if email.startswith(".") or email.endswith("."):
        return False

    if not _EMAIL_RE.match(email):
        return False

    local, domain = email.rsplit("@", 1)
    if domain.startswith(".") or domain.endswith("."):
        return False
    if domain.startswith("-") or domain.endswith("-"):
        return False

    return True

def validate_required_email(raw: str) -> str:
    """
    Valida um e-mail como campo obrigatório. Normaliza o valor e
    verifica se é válido; caso contrário, levanta exceção com
    mensagem amigável para o usuário.

    :param raw: (str) E-mail bruto informado pelo usuário.
    :return: (str) E-mail normalizado e validado.
    :raises ValueError: Se o e-mail estiver vazio ou for inválido.
    """
    email = normalize_email(raw)
    if email == "":
        raise ValueError("E-mail é obrigatório.")
    if not is_valid_email(email):
        raise ValueError("E-mail inválido. Verifique e tente novamente.")
    return email
