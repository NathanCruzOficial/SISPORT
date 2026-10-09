# Documentação do SISPORT

Este diretório reúne a documentação técnica do SISPORT. O conteúdo descreve primeiro o sistema **como está implementado**, sem pressupor que a arquitetura atual seja a arquitetura ideal.

## Documentos

| Documento | Conteúdo | Estado |
|---|---|---|
| [Arquitetura atual](arquitetura_atual.md) | Estrutura da aplicação, responsabilidades observadas e pontos que precisam ser confirmados. | Levantamento inicial |
| Fluxos funcionais | Passo a passo dos principais casos de uso, começando pelo cadastro e registro de visita. | A elaborar |
| Modelo de dados | Entidades, relacionamentos e restrições relevantes do banco. | A elaborar |
| Decisões técnicas | Motivos de decisões importantes e alternativas consideradas. | A elaborar |

## Como ler esta documentação

- **Confirmado no código:** foi observado nos arquivos do repositório.
- **Pendente de verificação:** precisa ser conferido em mais arquivos ou durante a execução.
- **Proposta:** ideia futura; não significa que já exista no sistema.

## Critério de atualização

Quando uma mudança de código alterar um fluxo ou uma responsabilidade importante, atualize o documento relacionado na mesma atividade, sempre que possível. Evite duplicar aqui explicações completas que já pertencem a outro documento; use links para manter um único lugar como referência.
