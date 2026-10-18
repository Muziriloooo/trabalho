"""Servidor local com abertura do navegador, usado por iniciar.bat."""
import sys
import webbrowser
from pathlib import Path

from waitress import create_server

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def main():
    from app import app

    try:
        server = create_server(app, host="127.0.0.1", port=5000)
    except OSError:
        print("Nao foi possivel abrir a porta 5000. Verifique se o site ja esta aberto em outro terminal.", flush=True)
        return 1

    print("SENTINELA AI iniciado na porta local 5000.", flush=True)
    print("Mantenha esta janela aberta. Para encerrar, pressione Ctrl+C.", flush=True)
    print("Se o navegador nao abrir, digite http://127.0.0.1:5000 nele.", flush=True)
    # O socket ja esta em escuta: o navegador pode conectar enquanto o loop inicia.
    try:
        webbrowser.open("http://127.0.0.1:5000", new=2)
    except webbrowser.Error:
        pass  # O servidor continua disponivel para abertura manual.
    try:
        server.run()
    except KeyboardInterrupt:
        pass
    finally:
        server.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
