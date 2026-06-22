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
__version__ = "1.3.2"

# Nome da aplicação exibido em diálogos de atualização e interfaces.
APP_NAME = "SISPORT"

# Repositório GitHub no formato 'id', consultado pela API do
# GitHub para verificar a existência de novas versões (releases).
GITHUB_REPO_ID = 1154415144

