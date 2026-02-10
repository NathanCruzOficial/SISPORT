import threading
import time
import webview
from app import create_app

# Sobe o servidor Flask em thread separada.
def _run_flask():
    """
    Executa o servidor Flask localmente para ser carregado pelo webview.
    """
    app = create_app()
    app.run(host="127.0.0.1", port=5000, debug=False, use_reloader=False)

# Aguarda o servidor estar de pé (simples).
def _wait_server():
    """
    Dá um pequeno tempo para o Flask iniciar antes de abrir a janela.
    """
    time.sleep(0.8)

# Ponto de entrada do app desktop.
def main():
    """
    Inicia Flask + abre uma janela nativa apontando para a app local.
    """
    t = threading.Thread(target=_run_flask, daemon=True)
    t.start()
    _wait_server()

    webview.create_window(
        "Cruz - Controle de Visitantes",
        "http://127.0.0.1:5000",
        width=1100,
        height=750,
        resizable=True,
    )
    webview.start()

if __name__ == "__main__":
    main()
