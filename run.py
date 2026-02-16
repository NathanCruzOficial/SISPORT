from sqlalchemy import true

from app import create_app

# Função principal para iniciar o servidor Flask local.
def main():
    app = create_app()
    # host 127.0.0.1 => acessível só no computador local.
    app.run(host="127.0.0.1", port=5000, debug=true)

if __name__ == "__main__":
    main()
