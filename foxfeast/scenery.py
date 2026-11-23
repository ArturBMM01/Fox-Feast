"""Ambientes desenhados por código, sem alterar colisões ou regras."""
from dataclasses import dataclass
import math
import random
import pygame
from pygame import draw
from .config import WIDTH, HEIGHT, TILE, COLS, ROWS, BOARD_X, BOARD_Y

@dataclass(frozen=True)
class Theme:
    """Materiais, iluminação e efeito de ambiente de uma fase."""

    name: str
    material: str
    floor: tuple[int, int, int]
    wall: tuple[int, int, int]
    accent: tuple[int, int, int]
    sky: tuple[int, int, int]
    weather: str


THEMES = (
    Theme("FLORESTA / VAGA-LUMES", "forest", (39, 36, 25), (28, 81, 49),
          (132, 194, 89), (10, 30, 22), "fireflies"),
    Theme("RIO / PASSARELAS", "river", (75, 55, 37), (22, 69, 98),
          (102, 192, 213), (10, 27, 44), "water"),
    Theme("RUÍNAS / PEDRA ANTIGA", "ruins", (43, 48, 47), (91, 103, 96),
          (184, 174, 121), (26, 31, 34), "dust"),
    Theme("BOSQUE / CHUVA", "rain", (42, 37, 32), (47, 73, 45),
          (126, 168, 145), (15, 27, 33), "rain"),
    Theme("LAGO / NENÚFARES", "lake", (43, 53, 62), (18, 48, 77),
          (113, 180, 222), (9, 20, 45), "water"),
    Theme("ILHAS / AREIA E PALMEIRAS", "islands", (78, 63, 41), (170, 143, 86),
          (239, 200, 115), (42, 37, 28), "leaves"),
    Theme("TEMPLO / RAÍZES", "temple", (48, 39, 37), (112, 87, 58),
          (226, 178, 89), (35, 24, 25), "dust"),
    Theme("CAVERNAS / CRISTAIS", "cave", (24, 36, 44), (40, 57, 74),
          (91, 232, 206), (8, 19, 30), "crystals"),
    Theme("FORTALEZA / MURALHAS", "fortress", (47, 43, 43), (104, 57, 49),
          (220, 128, 81), (37, 20, 24), "embers"),
    Theme("PÂNTANO / BIOLUMINESCÊNCIA", "heart", (33, 28, 46), (58, 38, 80),
          (213, 126, 239), (25, 12, 37), "spores"),
)


def tint(color, factor, lift=0):
    """Clareia ou escurece uma cor mantendo os canais no intervalo válido."""
    return tuple(max(0, min(255, int(c * factor + lift))) for c in color)


class Scenery:
    """Pré-renderiza o ambiente e anima uma camada leve de clima.

    Os materiais ocupam as mesmas células do labirinto. A decoração nunca
    adiciona paredes nem muda a posição de itens, personagens ou saídas.
    """

    def __init__(self, maze, stage_index):
        """Prepara chão, obstáculos, margem externa e partículas da fase."""
        self.theme = THEMES[stage_index]
        self.maze = maze
        self.rng = random.Random(maze.stage.seed + 1907)
        self.board = pygame.Surface((maze.cols * TILE, maze.rows * TILE))
        self.board.fill(self.theme.wall)
        self.background = pygame.Surface((WIDTH, HEIGHT))
        self._background()
        for y in range(maze.rows):
            for x in range(maze.cols):
                rect = pygame.Rect(x * TILE, y * TILE, TILE, TILE)
                if (x, y) in maze.floor:
                    self._floor(rect, (x, y))
                else:
                    self._wall(rect, x, y)
        candidates = sorted(set((x, y) for y in range(maze.rows) for x in range(maze.cols)) - maze.floor)
        self.water_points = self.rng.sample(candidates, min(28, len(candidates)))
        self.motes = [(self.rng.randrange(maze.cols * TILE), self.rng.randrange(maze.rows * TILE),
                       self.rng.random() * math.tau) for _ in range(28)]

    def _background(self):
        """Desenha iluminação e silhuetas fora da área de jogo."""
        sky = self.theme.sky
        for y in range(HEIGHT):
            color = tint(sky, 0.65 + 0.5 * y / HEIGHT)
            draw.line(self.background, color, (0, y), (WIDTH, y))
        # Uma margem ilustrada nas laterais reforça a paisagem sem cobrir o HUD.
        for x in (8, 1160):
            for y in range(145, HEIGHT, 81):
                leaf = tint(self.theme.accent, 0.19)
                draw.line(self.background, leaf, (x + 8, y + 53), (x + 11, y + 5), 2)
                for offset in (17, 30, 42):
                    draw.line(self.background, leaf, (x + 10, y + offset),
                                     (x + 25, y + offset - 10), 2)

    def _floor(self, rect, cell):
        """Ilustra o corredor como terra, ponte, laje ou pedra de passagem."""
        theme, material = self.theme, self.theme.material
        draw.rect(self.board, theme.floor, rect)
        x, y = rect.topleft
        if material in ("river", "islands"):
            # Passarelas com tábuas e parafusos, cercadas pela água/areia.
            draw.rect(self.board, tint(theme.floor, 0.60), rect, 2)
            horizontal = any(p[0] != cell[0] for p in self.maze.neighbors[cell])
            for step in (5, 12, 19, 26):
                if horizontal:
                    draw.line(self.board, tint(theme.floor, 0.56),
                                     (x + step, y + 2), (x + step, y + 25))
                else:
                    draw.line(self.board, tint(theme.floor, 0.56),
                                     (x + 2, y + step), (x + 25, y + step))
            draw.circle(self.board, (137, 126, 100), (x + 4, y + 4), 1)
        elif material in ("ruins", "temple", "fortress", "lake"):
            stone = rect.inflate(-3, -3)
            draw.rect(self.board, tint(theme.floor, 1.16), stone, border_radius=5)
            draw.line(self.board, tint(theme.floor, 1.4),
                             (x + 6, y + 4), (x + 17, y + 4))
            if material == "temple":
                draw.circle(self.board, (110, 85, 49), (x + 4, y + 23), 1)
        else:
            for _ in range(3):
                px, py = x + self.rng.randrange(4, 25), y + self.rng.randrange(4, 25)
                draw.circle(self.board, tint(theme.floor, 1.24), (px, py), 1)
            if material == "rain" and self.rng.random() < 0.25:
                draw.arc(self.board, (57, 77, 78), (x + 2, y + 13, 22, 10), 0, math.pi, 1)
            if material == "cave":
                draw.line(self.board, (43, 56, 66), (x + 5, y + 23), (x + 12, y + 20))

    def _wall(self, rect, gx, gy):
        """Escolhe um material realmente diferente para os obstáculos."""
        t = self.theme
        x, y = rect.topleft
        cx, cy = rect.center
        draw.rect(self.board, t.wall, rect)
        if t.material == "forest":
            draw.rect(self.board, (34, 40, 24), rect)
            draw.rect(self.board, (88, 61, 34), (cx - 3, cy, 6, 13))
            for ox, oy, radius in ((-6, -1, 8), (6, 0, 8), (0, -6, 10)):
                draw.circle(self.board, tint(t.wall, 0.9 + self.rng.random() * .4),
                                   (cx + ox, cy + oy), radius)
            draw.arc(self.board, (78, 129, 62), (cx - 7, cy - 13, 15, 14), .3, 2.6, 2)
            if (gx * 3 + gy) % 19 == 0:
                draw.rect(self.board, (178, 129, 55), (cx - 2, cy + 4, 5, 7), border_radius=1)
                draw.rect(self.board, (250, 210, 97), (cx - 1, cy + 5, 3, 4))
        elif t.material in ("river", "lake"):
            self._water(rect, gx, gy)
        elif t.material in ("ruins", "temple", "fortress"):
            self._masonry(rect, gx, gy)
        elif t.material == "rain":
            draw.circle(self.board, (32, 57, 38), (cx, cy), 13)
            draw.line(self.board, (123, 112, 81), (cx, cy + 10), (cx + 1, cy - 5), 3)
            draw.ellipse(self.board, (137, 88, 70), (cx - 10, cy - 8, 21, 11))
            draw.ellipse(self.board, (177, 126, 92), (cx - 8, cy - 8, 16, 5))
            draw.circle(self.board, (222, 189, 137), (cx - 3, cy - 5), 2)
            draw.line(self.board, (80, 116, 72), (x + 4, y + 23), (x + 2, y + 15), 2)
        elif t.material == "islands":
            for _ in range(3):
                draw.circle(self.board, (205, 176, 111),
                                   (x + self.rng.randrange(28), y + self.rng.randrange(28)), 1)
            draw.line(self.board, (103, 73, 40), (cx + 2, cy + 12), (cx - 1, cy - 1), 4)
            for dx, dy in ((-12, -3), (-10, -10), (1, -12), (12, -7), (12, 1)):
                draw.line(self.board, (40, 92, 57), (cx - 1, cy - 2), (cx + dx, cy + dy), 4)
                draw.line(self.board, (78, 127, 65), (cx - 1, cy - 3), (cx + dx, cy + dy - 1))
        elif t.material == "cave":
            draw.polygon(self.board, (30, 43, 57),
                                [(x, y + 6), (x + 8, y), (x + 24, y + 3), (x + 28, y + 22), (x + 9, y + 27)])
            if (gx + gy) % 3 != 0:
                for ox, height in ((-6, 13), (0, 23), (7, 15)):
                    points = [(cx + ox - 4, y + 24), (cx + ox - 5, y + 22 - height // 2),
                              (cx + ox, y + 24 - height), (cx + ox + 4, y + 22 - height // 2),
                              (cx + ox + 3, y + 24)]
                    draw.polygon(self.board, (44, 147, 144), points)
                    draw.line(self.board, (133, 242, 217),
                                     (cx + ox, y + 24 - height), (cx + ox + 1, y + 22), 1)
        elif t.material == "heart":
            draw.arc(self.board, (97, 63, 103), (x - 6, y - 4, 40, 35), .1, 2.8, 7)
            draw.arc(self.board, (144, 88, 146), (x - 3, y, 34, 29), .1, 2.8, 2)
            draw.line(self.board, (77, 48, 86), (cx - 10, y + 24), (cx + 9, y + 3), 4)
            if (gx + gy) % 3 == 0:
                draw.circle(self.board, (115, 58, 145), (cx, cy), 6)
                draw.circle(self.board, (227, 135, 240), (cx, cy), 3)

    def _water(self, rect, gx, gy):
        """Desenha rios com correnteza ou lago com folhas e flores aquáticas."""
        t, x, y = self.theme, rect.x, rect.y
        for dy in (6, 19):
            draw.arc(self.board, tint(t.wall, 1.45), (x + 2, y + dy, 24, 6), .15, 2.9, 1)
        if t.material == "river" and (gx + gy * 3) % 7 == 0:
            draw.ellipse(self.board, (52, 68, 66), (x + 4, y + 9, 19, 13))
            draw.arc(self.board, (107, 124, 111), (x + 6, y + 8, 14, 11), .2, 2.6, 2)
        elif t.material == "lake" and (gx * 5 + gy) % 3 != 0:
            draw.circle(self.board, (52, 103, 79), (x + 14, y + 14), 10)
            draw.polygon(self.board, t.wall, [(x + 14, y + 14), (x + 24, y + 8), (x + 24, y + 15)])
            draw.arc(self.board, (87, 145, 99), (x + 6, y + 5, 16, 16), .5, 2.9, 1)
            if (gx + gy) % 5 == 0:
                for dx, dy in ((-3, 0), (3, 0), (0, -3), (0, 3)):
                    draw.circle(self.board, (221, 158, 192), (x + 13 + dx, y + 13 + dy), 3)
                draw.circle(self.board, (252, 213, 121), (x + 13, y + 13), 2)

    def _masonry(self, rect, gx, gy):
        """Ilustra lajes rachadas, pedras entalhadas ou tijolos de fortaleza."""
        t, x, y = self.theme, rect.x, rect.y
        if t.material == "fortress":
            for row in range(3):
                yy = y + row * 9
                draw.line(self.board, (53, 37, 38), (x, yy), (x + 28, yy), 2)
                seam = x + (9 if row % 2 else 20)
                draw.line(self.board, (53, 37, 38), (seam, yy), (seam, yy + 9), 2)
            if (gx + gy) % 4 == 0:
                draw.line(self.board, (29, 30, 35), (x + 7, y + 3), (x + 7, y + 25), 3)
                draw.line(self.board, (29, 30, 35), (x + 20, y + 3), (x + 20, y + 25), 3)
                draw.line(self.board, (44, 42, 44), (x + 3, y + 14), (x + 25, y + 14), 3)
            return
        draw.rect(self.board, tint(t.wall, .65), rect, 2, border_radius=3)
        draw.line(self.board, tint(t.wall, 1.4), (x + 4, y + 3), (x + 23, y + 3), 2)
        if t.material == "ruins":
            draw.lines(self.board, (45, 57, 53), False,
                              [(x + 19, y + 3), (x + 14, y + 12), (x + 18, y + 18), (x + 11, y + 25)], 2)
            draw.line(self.board, (66, 94, 57), (x + 2, y + 23), (x + 13, y + 23), 3)
        else:
            draw.rect(self.board, (157, 118, 63), (x + 7, y + 7, 14, 14), 2)
            draw.lines(self.board, (208, 165, 85), False,
                              [(x + 10, y + 17), (x + 10, y + 11), (x + 17, y + 11), (x + 17, y + 16)], 2)
            if (gx + gy) % 3 == 0:
                draw.line(self.board, (64, 50, 33), (x + 1, y + 7), (x + 25, y + 26), 4)

    def backdrop(self, screen, time):
        """Aplica a iluminação da região e pequenas luzes na margem."""
        screen.blit(self.background, (0, 0))
        for i in range(12):
            x = 773 + int(359 * ((i * .173 + time * .009) % 1))
            y = 107 + int(45 * (0.5 + .5 * math.sin(time * .6 + i)))
            draw.circle(screen, tint(self.theme.accent, .35), (x, y), 1)

    def ambient(self, screen, time):
        """Desenha clima atrás dos personagens para preservar sua leitura."""
        t = self.theme
        if t.weather == "water":
            for i, (x, y) in enumerate(self.water_points):
                cx = self.maze.origin[0] + x * TILE + 14
                cy = self.maze.origin[1] + y * TILE + 14
                radius = 3 + int((time * 5 + i) % 9)
                draw.ellipse(screen, tint(t.accent, .45),
                                    (cx - radius, cy - radius // 3, radius * 2, max(2, radius // 2)), 1)
            return
        for i, (x, y, phase) in enumerate(self.motes):
            if t.weather == "rain":
                px = self.maze.origin[0] + int((x - time * 40) % (self.maze.cols * TILE))
                py = self.maze.origin[1] + int((y + time * 235) % (self.maze.rows * TILE - 12))
                draw.line(screen, (79, 112, 121), (px, py), (max(self.maze.origin[0], px - 4), py + 10))
            elif t.weather in ("fireflies", "spores", "crystals", "embers", "dust", "leaves"):
                px = self.maze.origin[0] + int((x + math.sin(time + phase) * 5) % (self.maze.cols * TILE))
                py = self.maze.origin[1] + int((y - time * (7 if t.weather != "leaves" else 15)) % (self.maze.rows * TILE))
                if t.weather == "leaves":
                    draw.ellipse(screen, tint(t.accent, .58), (px, py, 5, 2))
                else:
                    color = tint(t.accent, .45 + .4 * (0.5 + .5 * math.sin(time * 2 + phase)))
                    draw.circle(screen, color, (px, py), 2 if t.weather in ("spores", "fireflies") else 1)
