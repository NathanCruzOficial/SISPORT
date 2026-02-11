import re

def normalize_phone(value: str) -> str:
    return re.sub(r"\D", "", value or "")

def normalize_cpf(value: str) -> str:
    """Retorna CPF apenas com dígitos. Ex: '123.456.789-09' -> '12345678909'."""
    return re.sub(r"\D", "", value or "")

def is_valid_cpf(value: str) -> bool:
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
