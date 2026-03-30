# SISPORT — Sistema de Controle de Portaria

> Sistema web para registro e controle de entrada e saída de visitantes,
> desenvolvido para o **Grupamento de Unidades Escola / 9ª Brigada de Infantaria Motorizada** — **Exército Brasileiro**.

---

## 📋 Visão Geral

O **SISPORT** é uma aplicação web que gerencia o fluxo de visitantes em
organizações militares, oferecendo:

- **Cadastro guiado** de visitantes em 3 etapas (dados pessoais → foto via webcam → destino)
- **Registro automático** de check-in (entrada) no momento do cadastro
- **Check-out manual** (saída) com um clique
- **Timer em tempo real** de permanência para visitas em aberto
- **Relatório diário imprimível** em formato A4, com numeração de páginas, campos de conferência e vistos de autoridades
- **Identificação por CPF** — vincula foto, histórico e dados do visitante

---

## 🧱 Stack Tecnológica

| Camada       | Tecnologia                                                     |
| ------------ | -------------------------------------------------------------- |
| **Backend**  | Python · Flask · Jinja2                                        |
| **Frontend** | HTML5 · Bootstrap 5 · Bootstrap Icons · JavaScript (vanilla)   |
| **Impressão**| CSS `@page` (A4) · compatível com WeasyPrint e `window.print()`|
| **Webcam**   | API `MediaDevices.getUserMedia` (módulo `camera.js`)           |
| **Máscaras** | IMask.js (CPF e telefone via `mask.js`)                        |

---

## 📁 Estrutura de Diretórios (Templates)

templates/ ├── base.html # Layout base (navbar, footer, Bootstrap) ├── visitor_wizard.html # Wizard de cadastro — 3 etapas ├── report.html # Relatório de visitas (tela) └── print_day.html # Relatório imprimível A4 (standalone)

static/ ├── js/ │ ├── camera.js # Controle da webcam (etapa 2 do wizard) │ └── mask.js # Máscaras de CPF e telefone (IMask) └── img/ └── avatar-placeholder.jpg # Foto padrão quando não há imagem


## 📄 Templates

### `visitor_wizard.html`

Formulário guiado em **3 etapas** para cadastro completo de um novo visitante:

| Etapa | Nome           | Descrição                                                        |
| ----- | -------------- | ---------------------------------------------------------------- |
| **1** | Identificação  | Nome, CPF, filiação (mãe/pai), celular, e-mail, empresa         |
| **2** | Foto           | Captura via webcam (`camera.js`) ou opção de pular               |
| **3** | Local/Destino  | Setor/pessoa a visitar + registro automático do check-in         |

**Rotas (POST):**

| Rota                       | Ação                                             |
| -------------------------- | ------------------------------------------------ |
| `visitor.wizard_step1`     | Valida dados pessoais → avança para etapa 2      |
| `visitor.wizard_step2`     | Salva foto (Data URL base64) → avança para etapa 3 |
| `visitor.wizard_finish`    | Finaliza cadastro + registra check-in da visita   |

**Variáveis de contexto:**

wizard.step         # int  — Etapa atual (1, 2 ou 3)
wizard.name         # str  — Nome completo
wizard.cpf          # str  — CPF do visitante
wizard.mom_name     # str  — Nome da mãe
wizard.father_name  # str  — Nome do pai (opcional)
wizard.phone        # str  — Celular
wizard.email        # str  — E-mail (opcional)
wizard.empresa      # str  — Vínculo empresarial (opcional)

report.html
Listagem de visitas com timer de permanência em tempo real (atualizado a cada 1 segundo via JavaScript).

Reutilizado por duas views:

report.html
Listagem de visitas com timer de permanência em tempo real (atualizado a cada 1 segundo via JavaScript).

Reutilizado por duas views:

report.html
Listagem de visitas com timer de permanência em tempo real (atualizado a cada 1 segundo via JavaScript).

Reutilizado por duas views:

Variáveis de contexto:

title          # str          — Título dinâmico da página
visits         # list[Visit]  — Lista de visitas do dia/abertas
show_checkout  # bool         — Se True, exibe coluna "Ação"

print_day.html
Documento standalone (não herda de base.html) otimizado para impressão em A4.

## Recursos de impressão:

Configuração @page com margens de 12mm
Numeração automática: "Página X de Y" no rodapé central
Timestamp de geração no rodapé esquerdo
Cabeçalho da tabela (<thead>) repete em cada página
Linhas não quebram no meio (page-break-inside: avoid)
Bloco de conferência e vistos nunca são quebrados entre páginas
Elementos com classe .no-print são ocultados na impressão
Estrutura do documento impresso:

Cabeçalho institucional — Ministério da Defesa → EB → GUEs/9ª Bda Inf Mtz
Metadados — Data do documento, timestamp de geração, total de visitas
Tabela de visitas — Status, entrada, saída, tempo, nome, telefone, CPF, destino
Conferência — Campos manuais (nome, posto/graduação, assinatura)
Vistos — Oficial de Dia · Adjunto do Of Dia · Comandante da Guarda
Variáveis de contexto:

visits        # list[Visit]      — Lista de visitas do dia
today         # date             — Data de referência do relatório
generated_at  # datetime | None  — Timestamp de geração (fallback JS se None)

## 🗺️ Rotas Identificadas

Método,Rota (endpoint),Descrição
GET,visitor.identify,Tela de identificação (busca por CPF)
GET,visitor.wizard,Wizard — exibe etapa atual
POST,visitor.wizard_step1,Processa etapa 1 (dados pessoais)
POST,visitor.wizard_step2,Processa etapa 2 (foto webcam)
POST,visitor.wizard_finish,Processa etapa 3 + finaliza cadastro
GET,visitor.report_today,Relatório do dia (todas as visitas)
GET,visitor.open_visits,Visitas em aberto (sem check-out)
GET,visitor.report_today_print,Relatório imprimível (A4)
POST,visitor.checkout,Registra check-out (saída) da visita
GET,visitor.uploaded_file,Serve a foto do visitante

### 🔧 Assets JavaScript
camera.js
Controla a webcam na etapa 2 do wizard de cadastro:

Ativa/desativa stream de vídeo (getUserMedia)
Captura snapshot do <video> → gera Data URL (base64)
Preenche o campo hidden photo_data_url
Habilita/desabilita botões conforme o estado da câmera
Expõe ensurePhoto() usada no onsubmit do formulário

Atributo,Elemento,Função
"data-camera=""1""",Container,Identifica o bloco de câmera
data-open,Button,Ativa a câmera
data-capture,Button,Captura foto
data-close,Button,Desativa a câmera
data-preview,Img,Exibe prévia da foto capturada
data-enable-on-capture,Button,Habilitado após captura

mask.js
Aplica máscaras de formatação nos campos de input via IMask:

CPF: 000.000.000-00
Telefone: (00) 0 0000-0000


## 📊 Modelo de Dados (inferido)

```

┌──────────────┐         ┌──────────────┐
│   Visitor     │         │    Visit      │
├──────────────┤         ├──────────────┤
│ id           │◄───┐    │ id            │
│ name         │    │    │ visitor_id ───┘  (FK)
│ cpf          │    │    │ check_in       │
│ mom_name     │    │    │ check_out      │
│ father_name  │    │    │ destination    │
│ phone        │         └──────────────┘
│ email        │
│ empresa      │
│ photo_rel_path│
└──────────────┘

```

## 🖨️ Impressão
O relatório imprimível (print_day.html) é um documento HTML standalone projetado para gerar PDFs limpos em A4. Compatível com:


window.print() — impressão direta pelo navegador
WeasyPrint — geração de PDF no backend (Python)

## 🏛️ Contexto Institucional
O sistema foi desenvolvido para uso em Organizações Militares do Exército Brasileiro, especificamente:

Ministério da Defesa
└── Exército Brasileiro
    └── Grupamento de Unidades Escola / 9ª Brigada de Infantaria Motorizada

Campo,Autoridade
Responsável,"Nome, Posto/Grad, Assinatura"
Visto Of Dia,Oficial de Dia
Visto Adj Of Dia,Adjunto do Oficial de Dia
Visto Cmt Gda,Comandante da Guarda

## 📝 Licença
Uso interno — Exército Brasileiro.

Pronto, Danilo! O README foi construído 100% a partir das informações extraídas dos 3 templates que você me enviou. Ele cobre:

- **Visão geral** do sistema
- **Stack** tecnológica
- **Estrutura** de diretórios
- **Documentação detalhada** de cada template
- **Mapa de rotas** (inferido dos `url_for`)
- **Assets JS** e seus data attributes
- **Modelo de dados** (inferido das variáveis de contexto)
- **Contexto institucional** militar

Se quiser que eu ajuste algo ou adicione mais seções (como instalação, deploy, etc.), é só falar! 🚀
