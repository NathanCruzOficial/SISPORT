# =====================================================================
# version.py
# Metadados da Aplicação — Define a versão atual, nome da aplicação
# e repositório GitHub utilizado pelo módulo de atualização automática
# (updater.py) para verificar novas releases disponíveis.
# =====================================================================

# ─────────────────────────────────────────────────────────────────────
# Constantes — Identificação da Aplicação
# ─────────────────────────────────────────────────────────────────────

# Versão atual da aplicação (Semantic Versioning: MAJOR.MINOR.PATCH).
# Utilizada pelo updater.py para comparar com a release mais recente no GitHub.
__version__ = "1.1.0"

# Nome da aplicação exibido em diálogos de atualização e interfaces.
APP_NAME = "SISPORT - Controle de Visitantes"

# Repositório GitHub no formato 'owner/repo', consultado pela API do
# GitHub para verificar a existência de novas versões (releases).
GITHUB_REPO = "NathanCruzOficial/SISPORT-GUEs"
