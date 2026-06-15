# SISPORT — Sistema de Controle de Portaria

> Aplicação Windows/Web para registro e controle de visitantes, desenvolvida para o Grupamento de Unidades Escola da 9ª Brigada de Infantaria Motorizada do Exército Brasileiro.

---

## 🚀 Visão geral

O **SISPORT** oferece um fluxo completo de controle de visitantes, do cadastro à saída, com atenção especial às necessidades de operação militar:

- Cadastro de visitante em **wizard guiado** (dados pessoais, foto, destino)
- **Check-in automático** no momento do cadastro
- **Check-out manual** em visitas abertas
- **Relatórios diários imprimíveis** em formato A4
- **Timer de permanência** em tempo real para visitas abertas
- **Identificação por CPF** com histórico de visitas e foto
- Modo de execução **Webview** ou **Browser** com console opcional

---

## ⚙️ Funcionalidades principais

- Cadastro completo do visitante com validação de dados
- Captura de foto via webcam ou opção de pular imagem
- Armazenamento de fotos em banco de dados ou arquivos
- Lista de visitas em aberto e fechamento com confirmação
- Relatório de visitas com layout de conferência e vistos oficiais
- Impressão otimizada para A4, com paginação e rodapé padronizado
- Interface responsiva usando Bootstrap 5
- Atualização automática via módulo interno de updater

---

## 🏗️ Arquitetura do projeto

- **Backend:** Python + Flask + SQLAlchemy
- **Frontend:** HTML5 + Bootstrap 5 + JavaScript puro
- **Templates:** Jinja2
- **Execução nativa:** PyWebView para janela local
- **Modo browser:** abre o sistema no navegador padrão
- **Impressão/PDF:** WeasyPrint / window.print()
- **Windows-only:** pywin32, pythonnet, console Win32 e mutex de instância única

---

## 📦 Estrutura principal

- `main.py` — launcher do aplicativo
  - detecta modo Webview ou browser
  - valida instância única no Windows
  - aloca console quando necessário
  - inicia servidor Flask e abre interface
- `app/__init__.py` — factory Flask
  - cria app e configura configurações
  - registra blueprints de visitor e admin
  - garante diretórios, banco de dados e migrações legadas
- `app/config.py` — configurações de ambiente
- `app/extensions.py` — inicialização de extensões (SQLAlchemy)
- `app/paths.py` — caminhos de diretórios, uploads e logs
- `app/version.py` — metadados da aplicação
- `app/views/` — rotas de visitante e administração
- `app/models/` — modelo de visitante, visitas e configuração
- `app/static/` — CSS, JS, imagens e arquivos de terceiros
- `app/templates/` — páginas do sistema e relatórios de impressão

---

## 📁 Diretórios relevantes

- `app/static/js/`
  - `camera.js` — captura de foto via webcam
  - `mask.js` — máscaras de CPF e telefone
- `app/templates/`
  - `visitor_wizard.html` — fluxo de cadastro em 3 etapas
  - `report_page.html` / `open_visits.html` — listagens e relatórios
  - `print.html` — layout imprimível A4 com paginação
  - `admin/` — interface de configuração administrativa
- `app/models/` — persistência de visitantes, visitas e configurações
- `app/services/` — lógica de foto e relatórios
- `app/utils/` — utilitários de validação e processamento de imagens

---

## 🧩 Modo de execução

### Modo padrão

```bash
python main.py
```

Abre a aplicação em uma janela nativa via PyWebView.

### Modo browser

```bash
python main.py --browser
```

Ou mantenha a tecla **SHIFT** pressionada ao iniciar:
- abre no navegador padrão
- exibe o console Win32 para logs e depuração

---

## 🛠️ Instalação

Use Python 3.10+ no Windows.

```bash
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

Em seguida, execute:

```bash
python main.py
```

---

## 📋 Dependências principais

- `Flask==3.0.3`
- `Flask-SQLAlchemy==3.1.1`
- `SQLAlchemy==2.0.36`
- `pywebview==5.3`
- `pywin32==311`
- `weasyprint==68.1`
- `reportlab==4.4.10`
- `pillow==12.1.1`
- `requests==2.32.5`

> Veja `requirements.txt` para a lista completa de dependências.

---

## 🧪 Build e empacotamento

O projeto pode ser empacotado com PyInstaller:

```bash
pyinstaller --noconsole --onefile main.py
```

Também há artefatos de instalação em:

- `package/`
- `installer/`

---

## 💡 Notas técnicas

- O launcher usa mutex do Windows para garantir instância única.
- O modo browser cria um console Win32 quando necessário.
- A fábrica Flask garante criação do banco, migrações de foto e seeds padrão.

---

## 📜 Licença

Uso interno — Exército Brasileiro.
