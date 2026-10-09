# Arquitetura atual do SISPORT

> **Status:** levantamento inicial, baseado no código versionado na branch `main`. Este documento descreve a implementação observada; não é uma proposta de arquitetura ideal. Os detalhes serão refinados à medida que cada fluxo for rastreado.

## 1. Visão geral

O SISPORT é uma aplicação Python que usa Flask para receber requisições e renderizar páginas HTML, SQLAlchemy para persistência em SQLite e Jinja2 para templates. O ponto de entrada `main.py` inicia a aplicação e coordena aspectos de execução local, logging, atualização e modo de abertura.

A aplicação Flask é criada por `app.create_app()`, em `app/__init__.py`. Nessa factory, o sistema carrega a configuração, inicializa extensões e registra os blueprints de visitantes e administração.

## 2. Mapa de diretórios relevantes

| Caminho | Responsabilidade observada |
|---|---|
| `main.py` | Ponto de entrada; prepara diretórios e logs e coordena a inicialização do aplicativo. |
| `app/__init__.py` | Factory Flask, registro dos blueprints, configuração de contexto dos templates e rotas/helpers globais. |
| `app/config.py` | Configuração Flask, incluindo URI do banco SQLite e pasta de uploads. |
| `app/extensions.py` | Instâncias compartilhadas de extensões, incluindo SQLAlchemy e Flask-Migrate. |
| `app/views/visitor_views.py` | Rotas de identificação, cadastro, check-in/check-out, fotos, consultas e relatórios de visitantes. |
| `app/views/admin_settings.py` | Rotas de administração e configurações. |
| `app/controllers/visitor_controller.py` | Operações do fluxo de visitantes: validação, sessão do wizard, consultas, gravações e check-in/check-out. |
| `app/controllers/report_controller.py` | Operações auxiliares relacionadas a relatórios. |
| `app/controllers/config_registry.py` | Registro/organização de configurações. |
| `app/models/` | Modelos SQLAlchemy para visitantes, visitas, fotos temporárias, categorias, destinos e configurações. |
| `app/services/photo_service.py` | Serviço relacionado a fotos. |
| `app/services/report_service.py` | Serviço relacionado a relatórios. |
| `app/utils/` | Funções auxiliares, incluindo validação, máscaras e tratamento de fotos. |
| `app/templates/` | Templates HTML/Jinja2, incluindo páginas, componentes e telas administrativas. |
| `app/static/` | CSS, JavaScript, imagens, modelos e bibliotecas estáticas. |
| `migrations/` | Histórico de migrações do banco de dados. |
| `package/` e `installer/` | Arquivos de empacotamento e instalação. |

## 3. Como as camadas funcionam hoje

O código apresenta uma **separação parcial por camadas**, com responsabilidades que se sobrepõem.

### Views

As funções de `app/views/` recebem requisições HTTP, leem formulários e parâmetros, chamam operações de outras partes do sistema, exibem mensagens e redirecionam ou renderizam templates.

Entretanto, `visitor_views.py` também consulta modelos e o banco diretamente e contém funções auxiliares de preparação/validação de dados. Portanto, as views não atuam apenas como uma camada HTTP fina.

### Controllers

`app/controllers/visitor_controller.py` contém operações importantes do domínio de visitantes, mas também acessa a sessão Flask e executa consultas e gravações SQLAlchemy. Entre as funções observadas estão:

- `find_visitor_by_cpf()`
- `wizard_step1_submit()`
- `wizard_step2_submit()`
- `create_visitor_if_not_exists_from_wizard()`
- `register_checkin()`
- `checkout_visit()`
- `visitor_photo_update()`

O controller, portanto, combina validações, coordenação do fluxo, acesso à persistência e operações ligadas à sessão. Essa é uma constatação sobre o código atual, não uma recomendação automática de mover funções.

### Models e persistência

Os modelos em `app/models/` representam os dados usados pela aplicação. A configuração observada usa SQLite com SQLAlchemy. As consultas e gravações, porém, não estão exclusivamente nos models: também aparecem nos controllers e nas views.

### Services e utils

Há serviços separados para fotos e relatórios, além de utilitários de validação e tratamento de imagens. O uso dessas pastas deve ser mapeado função por função antes de concluir se as responsabilidades estão bem delimitadas.

## 4. Fluxo observado: cadastro de visitante

O fluxo abaixo foi montado a partir de `app/views/visitor_views.py` e `app/controllers/visitor_controller.py`.

```text
Usuário
  |
  v
View: /wizard/step1 (POST)
  |
  v
Controller: wizard_step1_submit()
  |-- normaliza e valida os dados
  |-- verifica campos duplicados
  |-- atualiza session["wizard"]
  v
View: /wizard/step2 (POST)
  |
  v
Controller: wizard_step2_submit()
  |-- processa a foto, se enviada
  |-- guarda a foto temporariamente no banco
  v
Controller: wizard_create_visitor_and_finish()
  |-- cria/recupera o visitante
  |-- encerra os dados temporários do wizard
  v
View redireciona para /checkin/<visitor_id>
  |
  v
Usuário informa destino e, conforme configuração, motivo
  |
  v
Controller: register_checkin()
  |-- cria a visita
  |-- grava o check-in no banco
  v
View apresenta mensagem e redireciona
```

**Observação:** também existe a rota `/wizard/finish`, que cria/recupera o visitante e registra o check-in no mesmo handler. A relação entre esse caminho e o fluxo atual de duas etapas precisa ser revisada para documentar se ambos continuam sendo usados pelos templates.

## 5. Fluxo observado: check-out

Em `app/views/visitor_views.py`, a rota `/checkout/<visit_id>` recebe a requisição, interpreta opcionalmente um horário de saída e chama `checkout_visit()`. O controller localiza a visita, registra o horário de saída se ainda estiver em aberto e confirma a transação no banco. A view trata exceções com mensagem ao usuário e redireciona para a tela de visitas em aberto.

## 6. Pontos que precisam de investigação

Estes itens são pendências de documentação e revisão, não necessariamente defeitos:

- [ ] Confirmar quais rotas de cadastro são usadas atualmente pelos templates, especialmente `/wizard/step2` e `/wizard/finish`.
- [ ] Mapear as rotas de administração e as operações que executam consultas/gravações diretamente nas views.
- [ ] Registrar o modelo de dados e os relacionamentos reais, incluindo categorias, destinos, visitas e fotos temporárias.
- [ ] Descrever inicialização, migrações, backups, atualização e tratamento de erros a partir dos arquivos correspondentes.
- [ ] Identificar quais verificações de duplicidade são regras de negócio e quais são protegidas também por restrições no banco.
- [ ] Executar e registrar testes dos principais fluxos antes de sugerir refatorações.

## 7. Princípio para as próximas etapas

A ordem será:

1. Descrever um fluxo real com base no código.
2. Confirmar o entendimento nos templates, rotas, controllers e models relacionados.
3. Registrar dúvidas e comportamentos não verificados.
4. Só então decidir se há uma melhoria de arquitetura que vale a pena implementar.

Não vamos renomear pastas nem criar camadas novas apenas para seguir um modelo teórico. Qualquer refatoração deve resolver um problema identificado e ser acompanhada de testes.
