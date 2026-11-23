"""Configurações compartilhadas; medidas em pixels ou segundos."""
from dataclasses import dataclass

WIDTH, HEIGHT = 1200, 840
TILE = 28
BOARD_X, BOARD_Y = 48, 174
COLS, ROWS = 25, 21
FPS = 60
BG = (10, 20, 30)
PANEL = (17, 33, 43)
TEXT = (239, 244, 225)
MUTED = (147, 173, 174)
MINT = (111, 232, 182)
GOLD = (255, 203, 105)
ORANGE = (255, 135, 76)
PINK = (244, 121, 142)
DIRECTIONS = ((1, 0), (0, 1), (-1, 0), (0, -1))


@dataclass(frozen=True)
class Difficulty:
    """Regras de uma dificuldade, sem alterar os mapas."""

    name: str
    lives: int
    enemy_factor: float
    power_seconds: float


DIFFICULTIES = (
    Difficulty("Explorador", 5, 0.78, 9.0),
    Difficulty("Arcade", 3, 1.0, 7.0),
)
