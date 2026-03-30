// =====================================================================
// static/js/mask.js
// Máscaras de Input — Aplica máscaras de formatação automática aos
// campos de formulário (CPF, telefone, CNPJ) utilizando a biblioteca
// IMask.js. Executado após o carregamento completo do DOM para
// garantir que todos os inputs já estejam disponíveis na página.
//
// Dependência externa:
//   - IMask.js (https://imask.js.org/) — deve ser carregado antes
//     deste script via <script> no template base.
// =====================================================================

document.addEventListener('DOMContentLoaded', function () {

  // ═══════════════════════════════════════════════════════════════════
  // Máscara — CPF: 000.000.000-00
  // Seletor: input[name="cpf"]
  // ═══════════════════════════════════════════════════════════════════
  const cpfInputs = document.querySelectorAll('input[name="cpf"]');
  cpfInputs.forEach(input => {
    IMask(input, {
      mask: '000.000.000-00'
    });
  });

  // ═══════════════════════════════════════════════════════════════════
  // Máscara — Telefone Celular: (00) 0 0000-0000
  // Seletor: input[name="phone"]
  // Formato padrão brasileiro com 9º dígito.
  // ═══════════════════════════════════════════════════════════════════
  const phoneInputs = document.querySelectorAll('input[name="phone"]');
  phoneInputs.forEach(input => {
    IMask(input, {
      mask: '(00) 0 0000-0000'
    });
  });

  // ═══════════════════════════════════════════════════════════════════
  // Máscara — CNPJ: 00.000.000/0000-00
  // Seletor: input[name="cnpj"]
  // ═══════════════════════════════════════════════════════════════════
  const cnpjInputs = document.querySelectorAll('input[name="cnpj"]');
  cnpjInputs.forEach(input => {
    IMask(input, {
      mask: '00.000.000/0000-00'
    });
  });

  // ═══════════════════════════════════════════════════════════════════
  // Novas máscaras podem ser adicionadas aqui seguindo o mesmo padrão:
  //   1. Selecionar os inputs via querySelectorAll
  //   2. Aplicar IMask com o pattern desejado
  // ═══════════════════════════════════════════════════════════════════

});
