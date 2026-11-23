"""Persistência local tolerante a arquivos ausentes, inválidos ou bloqueados."""
import json
import os
from pathlib import Path

class SaveData:
    """Salva recordes separados por dificuldade e a preferência de áudio."""

    def __init__(self, path=None):
        """Carrega dados válidos ou mantém os valores iniciais seguros."""
        base = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "FoxFeast"
        self.path = Path(path) if path is not None else base / "save.json"
        self.records = [0, 0]
        self.muted = False
        self.music_muted = False
        self.writable = True
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            records = data.get("records", [0, 0])
            if isinstance(records, list) and len(records) == 2:
                self.records = [max(0, n) if type(n) is int else 0 for n in records]
            self.muted = data.get("muted") is True
            self.music_muted = data.get("music_muted", self.muted) is True
        except (OSError, ValueError, TypeError, AttributeError):
            pass

    def write(self):
        """Grava via arquivo temporário; falhas não interrompem o jogo."""
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            temp = self.path.with_suffix(".tmp")
            temp.write_text(json.dumps({"records": self.records, "muted": self.muted,
                                        "music_muted": self.music_muted}),
                            encoding="utf-8")
            temp.replace(self.path)
            self.writable = True
        except OSError:
            self.writable = False

    def register(self, score, difficulty):
        """Registra apenas um novo recorde da dificuldade correspondente."""
        if score > self.records[difficulty]:
            self.records[difficulty] = score
            self.write()
