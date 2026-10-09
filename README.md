# SISPORT

Sistema de controle de visitantes e registro de visitas, desenvolvido em Python com Flask e SQLAlchemy. O projeto pode ser executado localmente no Windows em uma janela de aplicativo ou no navegador.

> **Estado da documentação:** esta página apresenta uma visão geral. A arquitetura e os fluxos estão sendo documentados a partir do código existente; os pontos ainda não verificados serão identificados como pendentes.

## Visão geral

O SISPORT reúne funcionalidades para identificação de visitantes, manutenção dos seus dados e registro de entradas e saídas.

Entre as funcionalidades presentes no código estão:

- Identificação e cadastro de visitantes, incluindo validação de dados.
- Captura, armazenamento e exibição de fotos.
- Registro de visitas, com destino, entrada e saída.
- Consulta de visitas e geração de relatórios para impressão.
- Administração de categorias de visitantes, destinos e configurações.
- Banco de dados SQLite e suporte a migrações.
- Inicialização como aplicativo Windows ou execução pelo navegador.
- Verificação de atualizações e rotinas de inicialização/log.

## Tecnologias

| Área | Tecnologias identificadas |
|---|---|
| Backend | Python, Flask |
| Persistência | SQLite, SQLAlchemy, Flask-Migrate/Alembic |
| Interface | HTML, Jinja2, Bootstrap, CSS e JavaScript |
| Captura de imagem | API de mídia do navegador e processamento de fotos no backend |
| Empacotamento | PyInstaller e scripts/configuração de instalador |
| Versionamento e automação | Git e GitHub Actions |

## Estrutura do projeto

```text
SISPORT/
├── app/
│   ├── controllers/   # Operações de fluxo e parte das regras da aplicação
│   ├── models/        # Modelos e acesso a dados via SQLAlchemy
│   ├── services/      # Serviços auxiliares, como fotos e relatórios
│   ├── views/         # Rotas Flask e preparação de respostas
│   ├── templates/     # Páginas e componentes Jinja2/HTML
│   ├── static/        # CSS, JavaScript, imagens e bibliotecas locais
│   ├── utils/         # Validadores e utilitários
│   ├── config.py      # Configurações Flask
│   ├── extensions.py  # Extensões compartilhadas
│   └── __init__.py    # Factory da aplicação Flask
├── docs/              # Documentação técnica do projeto
├── migrations/        # Migrações do banco de dados
├── package/           # Arquivos relacionados ao empacotamento
├── installer/         # Arquivos do instalador
├── main.py            # Ponto de entrada
├── requirements.txt   # Dependências Python
└── TASKS.md           # Lista de tarefas do projeto
```

A separação entre pastas é uma descrição da organização atual, não uma afirmação de que todas as responsabilidades estejam completamente isoladas. Consulte [a documentação técnica](docs/README.md) para ver o levantamento da arquitetura e suas pendências.

## Executar em ambiente de desenvolvimento

Os comandos abaixo são um ponto de partida para um ambiente Python local. Dependências específicas do Windows podem ser necessárias para recursos de janela nativa.

1. Clone o repositório e entre na pasta:

   ```powershell
   git clone https://github.com/NathanCruzOficial/SISPORT.git
   cd SISPORT
   ```

2. Crie e ative um ambiente virtual:

   ```powershell
   py -m venv .venv
   .\.venv\Scripts\Activate.ps1
   ```

3. Instale as dependências:

   ```powershell
   python -m pip install -r requirements.txt
   ```

4. Inicie o sistema:

   ```powershell
   python main.py
   ```

   Para solicitar a execução no navegador, use:

   ```powershell
   python main.py --browser
   ```

> Antes de usar o sistema com dados reais, confira as configurações locais, as rotinas de backup e as medidas de proteção de dados. Não publique bancos de dados, fotos, logs ou informações pessoais em commits, issues ou pull requests.

## Documentação

Consulte o [índice da documentação](docs/README.md).

- [Arquitetura atual](docs/arquitetura_atual.md) — inventário inicial das camadas e responsabilidades observadas no código.
- [Tarefas do projeto](TASKS.md) — acompanhamento de atividades existentes.

## Escopo desta documentação

A documentação é construída gradualmente com base no código versionado. Primeiro registramos o comportamento e a estrutura existentes; propostas de refatoração serão documentadas separadamente, sem serem confundidas com o funcionamento atual.
