"""Ponto de entrada: execute este arquivo para abrir o Fox Feast."""

import os
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")


def main():
    """Inicia o aplicativo depois de verificar a dependência obrigatória."""
    try:
        from foxfeast.app import App
    except ModuleNotFoundError as error:
        if error.name != "pygame":
            raise
        print("Falta instalar o Pygame. No terminal desta pasta, execute:")
        print("python -m pip install -r requirements.txt")
        raise SystemExit(1) from error
    App().run()


if __name__ == "__main__":
    main()
