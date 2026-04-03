// app/static/js/confirm_modal.js

/**
 * confirmAction — Abre o modal de confirmação estilizado.
 * Substitui o confirm() nativo do navegador.
 *
 * Uso:
 *   <form onsubmit="return confirmAction(event, 'Sua mensagem aqui')">
 *
 * @param {Event}  e   — Evento de submit do form
 * @param {string} msg — Mensagem exibida no modal
 * @returns {boolean} false (sempre cancela o submit nativo)
 */
function confirmAction(e, msg) {
    e.preventDefault();

    const form  = e.target;
    const modal = new bootstrap.Modal(document.getElementById('confirmModal'));

    // Define a mensagem
    document.getElementById('confirmModalMsg').textContent =
        msg || 'Tem certeza que deseja continuar?';

    // Remove listeners antigos clonando o botão
    const btnOk  = document.getElementById('confirmModalOk');
    const newBtn = btnOk.cloneNode(true);
    btnOk.parentNode.replaceChild(newBtn, btnOk);

    // Ao confirmar, submete o form
    newBtn.addEventListener('click', () => {
        modal.hide();
        form.submit();
    });

    modal.show();
    return false;
}
