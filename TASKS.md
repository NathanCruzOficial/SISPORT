# Plano de Tarefas — SISPORT

Este documento reúne pontos fortes e pontos de melhoria da aplicação, com sugestões de ações para deixar o projeto mais profissional e sustentável.

---

## ✅ Pontos fortes

- **Arquitetura modular**: `app/__init__.py` já usa factory Flask e blueprints.
- **Fluxo de cadastro estruturado**: wizard de 3 etapas facilita o processo de registro.
- **Suporte a Webview e browser**: alternativa nativa e web para execução no Windows.
- **Impressão profissional**: relatório A4 com paginação, rodapé e detalhes de conferência.
- **Armazenamento de fotos no banco**: modelo de foto temporária e foto definitiva bem separado.
- **Boas práticas de logs**: logger central e log em arquivo configurado no launcher.
- **Atualização automática**: há módulo de updater integrado.

---

## ⚠️ Pontos a melhorar

### 1. Qualidade de código e organização

- Falta de **testes automatizados** (unitários e de integração).
- Uso de **sessão para wizard** e armazenamento temporário de estado pode ser frágil.
- Estrutura de rotas e controllers pode ser melhor separada em camadas de serviço, validação e persistência.
- Validações estão espalhadas entre views e controllers — ideal centralizar em utilitários/validators.
- Comentários do código são bons, mas há potencial para **tipagem mais consistente** e **docstrings** extras.

### 2. Segurança

- `SECRET_KEY` tem fallback fixo (`sisport-local-dev-key`) no `app/config.py`.
- Não há proteção explícita contra CSRF em formulários Flask.
- Controle de acesso/ autenticação para áreas administrativas parece ausente.
- Ainda que use SQLAlchemy, é possível melhorar a validação de entrada e tratamento de erros.

### 3. Arquitetura e manutenção

- Fotos armazenadas diretamente em BLOB no banco podem crescer rapidamente.
- Retenção de dados e limpeza de registros antigos não está documentada.
- Modo de execução depende fortemente do Windows (pywin32, mutex), o que limita portabilidade.
- Migrações de schema são manuais (ALTER TABLE), sem um sistema de migrations dedicado.

### 4. Experiência do usuário

- Controle de fluxo do wizard pode ser melhorado com feedback em tempo real.
- A interface pode ganhar mensagens de erro mais amigáveis e confirmações claras.
- Não há indicação de suporte móvel / responsividade para telas pequenas.
- Possibilidade de adicionar buscas e filtros avançados no relatório de visitas.

### 5. DevOps e documentação

- README foi melhorado, mas faltam instruções de configuração avançada, deploy e manutenção.
- Não há arquivos de CI/CD, linting ou formatação automática.
- Ausência de um guia de instalação para ambientes Windows com dependências específicas.
- Não há métricas de desempenho ou monitoramento sugerido.

---

## 🎯 Prioridades recomendadas

### Alta prioridade

- Adicionar **testes automatizados** (backend, validação e rotas principais).
- Implementar **CSRF** e melhorar `SECRET_KEY` com variável de ambiente.
- Criar **autenticação administrativa** para proteger configurações e relatórios.
- Definir **migrações de banco** com Alembic ou similar.
- Revisar a lógica de wizard para usar um armazenamento mais robusto que sessão simples.

### Média prioridade

- Melhorar a estrutura de código com serviços e validators separados.
- Adicionar **tratamento de erros centralizado** e páginas de erro customizadas.
- Documentar o processo de deploy e criar um `setup`/`install` mais claro.
- Avaliar armazenamento de imagens: banco vs sistema de arquivos + links.
- Incluir linting/formatting (`black`, `flake8`, `isort`) e CI básico.

### Baixa prioridade

- Aperfeiçoar UX de relatórios e filtros de pesquisa.
- Adicionar dashboard com estatísticas de visitas (gráficos, contadores).
- Tornar a interface mais responsiva para tablets e telas pequenas.
- Planejar rotinas de retenção e limpeza de dados legados.

---

## 🛠️ Tarefas sugeridas

### Arquitetura

- [ ] Criar camada de serviços separada de `views` e `controllers`.
- [ ] Adotar `app/services/` e mover lógica de negócio para lá.
- [ ] Revisar o uso de `session` no wizard e considerar persistência temporária no banco.

### Segurança

- [ ] Ativar CSRF com `Flask-WTF` ou middleware equivalente.
- [ ] Forçar `SECRET_KEY` via variável de ambiente em produção.
- [ ] Adicionar login/roles para o painel administrativo.

### Qualidade de código

- [ ] Configurar `Black`, `isort` e `flake8`.
- [ ] Escrever testes para: cadastro, check-in, check-out, upload de foto, relatório.
- [ ] Adicionar tipagem estática com `typing` e `mypy` onde fizer sentido.

### Banco de dados

- [ ] Implementar migrações com `Alembic`.
- [ ] Avaliar modelo de foto: BLOB vs arquivos no `uploads/`.
- [ ] Criar rotina de retenção e exclusão de visitas antigas.

### DevOps / Documentação

- [ ] Criar arquivo `CONTRIBUTING.md` básico.
- [ ] Adicionar `TASKS.md` ou `ROADMAP.md` para equipe.
- [ ] Criar pipeline de CI para rodar testes e lint.
- [ ] Documentar dependências específicas do Windows e build PyInstaller.

---

## 📌 Recomendações para um padrão profissional

- Use um modelo de branches e revisão de PRs claros.
- Tenha `requirements.txt` separado por ambiente (base / dev / prod).
- Mantenha documentação de deploy e configuração de ambiente atualizada.
- Priorize código testável e com responsabilidades bem definidas.
- Garanta que o sistema esteja sempre seguro antes de rodar em produção.

---

## 📎 Observações finais

Este arquivo foi elaborado para ajudar você a transformar o SISPORT em um projeto mais profissional e sustentável. Ele combina os pontos fortes já existentes no código atual com melhorias práticas que fazem diferença em manutenção, segurança e qualidade.
