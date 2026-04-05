# =====================================================================
# views/config_registry.py
# Registro das Abas e Seções da Página de Configurações do SISPORT
# =====================================================================

"""
Define a estrutura de abas (tabs) e seções exibidas na página
de configurações administrativas. Cada aba pode conter múltiplas
seções, cada uma apontando para um template parcial (partial).

Adicionar uma nova seção = adicionar um dict aqui + criar o template.
"""

SETTINGS_TABS = [
    # ── Aba: Geral ──────────────────────────────────────────────────
    {
        "key": "general",
        "label": "Geral",
        "icon": "bi-gear",
        "description": "Informações da instituição e personalização",
        "sections": [
            {
                "key": "institution",
                "label": "Dados da Instituição",
                "icon": "bi-building",
                "template": "admin/sections/general_institution.html",
            },
        ],
    },

    # ── Aba: Segurança ──────────────────────────────────────────────
    {
        "key": "security",
        "label": "Segurança",
        "icon": "bi-shield-lock",
        "description": "Senha administrativa e controle de acesso",
        "sections": [
            {
                "key": "password",
                "label": "Senha Administrativa",
                "icon": "bi-key",
                "template": "admin/sections/security_password.html",
            },
        ],
    },

    # ── Aba: Visitantes ─────────────────────────────────────────────
    {
        "key": "visitors",
        "label": "Visitantes",
        "icon": "bi-people",
        "description": "Categorias e regras de cadastro",
        "sections": [
            {
                "key": "categories",
                "label": "Categorias de Visitante",
                "icon": "bi-tags",
                "template": "admin/sections/visitors_categories.html",
            },
            {
                "key": "Registro",
                "label": "Dados de registro",
                "icon": "bi-people",
                "template": "admin/sections/visitors_fields.html",
            },
        ],
    },

    # ── Aba: Banco de Dados ─────────────────────────────────────────
    {
        "key": "database",
        "label": "Banco de Dados",
        "icon": "bi-database",
        "description": "Retenção, backup e transferência de dados",
        "sections": [
            {
                "key": "retention",
                "label": "Retenção de Dados",
                "icon": "bi-trash3",
                "template": "admin/sections/database_retention.html",
            },
            {
                "key": "backup",
                "label": "Backup e Restauração",
                "icon": "bi-download",
                "template": "admin/sections/database_backup.html",
            },
            {
                "key": "export_import",
                "label": "Exportar / Importar Configurações",
                "icon": "bi-arrow-left-right",
                "template": "admin/sections/database_export_import.html",
            },
            {
                "key": "data_visitors",
                "label": "Exportar / Importar Visitantes",
                "icon": "bi-people-fill",
                "template": "admin/sections/database_visitors_data.html",
            },
        ],
    },
]
