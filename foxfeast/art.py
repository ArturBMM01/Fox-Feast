"""Arte vetorial original, quadros de animação e partículas do jogo."""
import math
import random
import pygame
from pygame import draw
from .config import WIDTH, HEIGHT, MINT, GOLD, ORANGE

class Art:
    """Desenha personagens uma vez e reutiliza sprites em cache."""

    def __init__(self):
        """Prepara o fundo e um cache inicialmente vazio de personagens."""
        self.cache = {}
        self.background = pygame.Surface((WIDTH, HEIGHT))
        for y in range(HEIGHT):
            k = y / HEIGHT
            draw.line(self.background, (int(9 + 5 * k), int(21 + 10 * k),
                                               int(31 + 9 * k)), (0, y), (WIDTH, y))
        rng = random.Random(27)
        self.stars = [(rng.randrange(WIDTH), rng.randrange(HEIGHT), rng.random() * 6)
                      for _ in range(40)]

    def backdrop(self, screen, time):
        """Desenha o fundo com vaga-lumes de brilho suave."""
        screen.blit(self.background, (0, 0))
        for x, y, phase in self.stars:
            strength = 0.5 + 0.5 * math.sin(time * 1.4 + phase)
            color = (int(36 + strength * 30), int(65 + strength * 28), 66)
            draw.circle(screen, color, (x, int(y + math.sin(time + phase) * 3)), 2)

    def sprite(self, kind, size, frame=0, direction=(1, 0), variant=0):
        """Obtém um quadro orientado e escalado do cache de sprites."""
        key = kind, size, frame % 4, direction, variant
        if key in self.cache:
            return self.cache[key]
        s = pygame.Surface((64, 64), pygame.SRCALPHA)
        if kind == "fox":
            self._fox(s, frame % 4)
        elif kind == "croc":
            self._croc(s, frame % 4, variant)
        elif kind == "hunter":
            self._hunter(s, frame % 4, variant, direction == (0, -1))
        else:
            self._fruit(s, frame % 4)
        if direction == (-1, 0):
            s = pygame.transform.flip(s, True, False)
        elif direction == (0, -1) and kind != "hunter":
            s = pygame.transform.rotate(s, 90)
        elif direction == (0, 1) and kind != "hunter":
            s = pygame.transform.rotate(s, -90)
        s = pygame.transform.smoothscale(s, (size, size))
        self.cache[key] = s
        return s

    @staticmethod
    def _fox(s, frame):
        """Ilustra uma raposa lateral com cauda branca e mandíbula animada."""
        ink, orange, light, cream = (54, 33, 34), ORANGE, (255, 175, 88), (255, 239, 201)
        bob = (0, 1, 0, -1)[frame]
        draw.ellipse(s, (0, 0, 0, 40), (8, 48, 48, 9))
        draw.polygon(s, ink, [(28, 36), (6, 17 + bob), (3, 38), (12, 50), (30, 46)])
        draw.polygon(s, orange, [(27, 36), (7, 20 + bob), (6, 38), (14, 47), (28, 44)])
        draw.polygon(s, cream, [(7, 20 + bob), (6, 37), (14, 34)])
        draw.ellipse(s, ink, (18, 27, 31, 27))
        draw.ellipse(s, orange, (20, 29, 27, 23))
        leg = (0, 3, 0, -3)[frame]
        draw.line(s, ink, (25, 47), (22 + leg, 55), 6)
        draw.line(s, ink, (42, 47), (45 - leg, 55), 6)
        draw.polygon(s, ink, [(28, 29), (28, 7), (40, 18), (48, 10), (53, 34)])
        draw.polygon(s, orange, [(30, 28), (30, 11), (40, 21), (47, 14), (51, 34)])
        draw.polygon(s, (115, 56, 51), [(32, 15), (33, 25), (38, 22)])
        draw.polygon(s, light, [(30, 26), (45, 23), (59, 34), (48, 46), (32, 41)])
        draw.polygon(s, cream, [(33, 34), (45, 36), (58, 34), (48, 46), (35, 42)])
        if frame in (1, 2):
            draw.polygon(s, ink, [(47, 38), (60, 36), (53, 43)])
        draw.circle(s, ink, (58, 34), 4)
        draw.ellipse(s, ink, (43, 25, 5, 7))
        draw.circle(s, (255, 255, 245), (45, 26), 1)
        draw.line(s, (91, 48, 35), (42, 22), (49, 23), 2)
        # Lenço turquesa, marca visual do personagem.
        draw.polygon(s, MINT, [(29, 38), (34, 40), (31, 49), (25, 46)])

    @staticmethod
    def _croc(s, frame, variant):
        """Ilustra os pequenos jacarés que a raposa coleta pelo mapa."""
        palettes = [(107, 201, 120), (243, 115, 126), (196, 131, 222),
                    (242, 178, 92), (107, 184, 224), (229, 131, 181), (120, 238, 218)]
        color = palettes[variant % len(palettes)]
        dark = tuple(int(c * 0.50) for c in color)
        y = (0, 2, 0, -1)[frame]
        draw.ellipse(s, (0, 0, 0, 40), (7, 45, 51, 9))
        draw.polygon(s, dark, [(24, 34), (3, 21 + y), (8, 42), (27, 48)])
        draw.polygon(s, color, [(23, 35), (6, 26 + y), (12, 40), (26, 44)])
        draw.ellipse(s, dark, (15, 27, 34, 23))
        draw.ellipse(s, color, (17, 26, 32, 21))
        draw.rect(s, dark, (35, 28, 27, 16), border_radius=6)
        draw.rect(s, color, (35, 28, 26, 12), border_radius=5)
        for x in (20, 29, 38):
            draw.polygon(s, dark, [(x, 28), (x + 4, 20), (x + 8, 28)])
        for x in (43, 50, 57):
            draw.polygon(s, (248, 241, 201), [(x, 38), (x + 4, 38), (x + 2, 43)])
        draw.circle(s, color, (43, 25), 7)
        draw.circle(s, (250, 244, 215), (44, 24), 4)
        draw.circle(s, (29, 43, 41), (45, 24), 2)
        draw.circle(s, dark, (57, 31), 2)
        leg = (0, 3, 0, -3)[frame]
        draw.line(s, dark, (23, 42), (20 + leg, 49), 5)
        draw.line(s, dark, (39, 42), (43 - leg, 49), 5)
        if variant != 0 and variant != 6:
            draw.line(s, (52, 37, 54), (39, 19), (48, 22), 3)

    @staticmethod
    def _hunter(s, frame, variant, back=False):
        """Desenha um caçador cartunesco com chapéu, casaco e espingarda.

        Os quatro quadros alternam as pernas. O personagem continua em pé
        ao andar para cima ou para baixo, em vez de girar como um objeto.
        Azul indica vulnerabilidade; nesse estado, a arma fica abaixada.
        """
        colors = [(200, 89, 75), (190, 123, 200), (222, 166, 69),
                  (85, 152, 203), (176, 123, 77)]
        afraid = variant == 6
        coat = (111, 219, 225) if afraid else colors[(variant - 1) % len(colors)]
        dark = tuple(int(c * 0.55) for c in coat)
        ink, skin = (30, 34, 39), (241, 191, 141)
        bob = (0, 1, 0, -1)[frame]
        stride = (-4, 0, 4, 0)[frame]
        draw.ellipse(s, (0, 0, 0, 55), (12, 54, 43, 8))
        # Botas e calças animadas ficam atrás do casaco.
        draw.line(s, ink, (27, 44), (23 + stride, 55), 8)
        draw.line(s, ink, (38, 44), (42 - stride, 55), 8)
        draw.rect(s, (77, 60, 45), (17 + stride, 53, 12, 6), border_radius=2)
        draw.rect(s, (77, 60, 45), (37 - stride, 53, 12, 6), border_radius=2)
        draw.rect(s, dark, (17, 27 + bob, 28, 23), border_radius=6)
        draw.rect(s, coat, (19, 27 + bob, 24, 21), border_radius=5)
        draw.line(s, (222, 204, 157), (30, 30 + bob), (30, 46), 3)
        draw.rect(s, ink, (18, 43, 27, 5), border_radius=1)
        draw.rect(s, GOLD, (29, 43, 6, 5), 1)
        # Cabeça, nariz, cabelo e chapéu com aba larga.
        draw.rect(s, ink, (22, 10 + bob, 23, 22), border_radius=6)
        draw.rect(s, skin, (24, 12 + bob, 19, 18), border_radius=5)
        draw.rect(s, skin, (41, 20 + bob, 5, 6), border_radius=2)
        if back:
            draw.rect(s, (87, 60, 43), (23, 13 + bob, 20, 17), border_radius=5)
            draw.rect(s, dark, (22, 32 + bob, 18, 12), border_radius=3)
            draw.rect(s, (185, 165, 112), (25, 34 + bob, 12, 7), 1, border_radius=2)
        else:
            draw.circle(s, ink, (39, 20 + bob), 2)
            if afraid:
                draw.circle(s, (251, 247, 224), (39, 19 + bob), 3)
                draw.circle(s, ink, (40, 19 + bob), 1)
                draw.ellipse(s, ink, (37, 25 + bob, 4, 5))
            else:
                draw.line(s, ink, (35, 16 + bob), (43, 18 + bob), 2)
                draw.rect(s, (94, 59, 39), (31, 25 + bob, 12, 3), border_radius=1)
        draw.rect(s, (48, 62, 42), (22, 4 + bob, 22, 12), border_radius=4)
        draw.rect(s, (104, 120, 64), (24, 5 + bob, 18, 9), border_radius=3)
        draw.rect(s, (49, 62, 40), (15, 13 + bob, 36, 5), border_radius=2)
        draw.rect(s, coat, (25, 10 + bob, 17, 3))
        # A espingarda é um elemento visual; as colisões usam contato.
        if afraid:
            draw.line(s, (102, 69, 41), (39, 34 + bob), (46, 43 + bob), 6)
            draw.line(s, (155, 173, 178), (46, 43 + bob), (56, 56), 4)
            draw.circle(s, skin, (43, 39 + bob), 4)
        else:
            draw.polygon(s, (116, 73, 43), [(19, 33 + bob), (32, 33 + bob),
                                                   (42, 36 + bob), (25, 42 + bob)])
            draw.rect(s, (43, 47, 52), (33, 31 + bob, 30, 6), border_radius=1)
            draw.line(s, (169, 184, 187), (38, 32 + bob), (61, 32 + bob), 2)
            draw.rect(s, (82, 58, 39), (37, 35 + bob, 10, 5), border_radius=1)
            draw.circle(s, skin, (28, 38 + bob), 4)
            draw.circle(s, skin, (45, 38 + bob), 4)

    @staticmethod
    def _fruit(s, frame):
        """Desenha a fruta dourada que ativa o banquete."""
        draw.circle(s, (255, 196, 87, 32), (32, 34), 26)
        draw.circle(s, GOLD, (32, 34), 17)
        draw.circle(s, (255, 228, 145), (27, 28), 5)
        draw.line(s, (151, 117, 62), (32, 21), (36, 10), 4)
        draw.ellipse(s, MINT, (35, 9, 16, 8))
        draw.polygon(s, (255, 246, 211), [(32, 24), (35, 32), (42, 34),
                                               (35, 37), (32, 44), (29, 37),
                                               (22, 34), (29, 32)])


class Particles:
    """Partículas leves e textos de pontuação com vida limitada."""

    def __init__(self):
        """Inicia as coleções de partículas e números flutuantes."""
        self.items = []
        self.labels = []
        self.rng = random.Random()

    def burst(self, x, y, color, count=10, label=None):
        """Cria uma pequena explosão visual no ponto de uma interação."""
        for _ in range(count):
            angle = self.rng.random() * math.tau
            speed = self.rng.uniform(25, 105)
            self.items.append([x, y, math.cos(angle) * speed, math.sin(angle) * speed,
                               self.rng.uniform(0.25, 0.6), color])
        if label:
            self.labels.append([x, y, str(label), 0.9])
        self.items = self.items[-240:]

    def update(self, dt):
        """Envelhece partículas e remove elementos que já desapareceram."""
        for item in self.items:
            item[0] += item[2] * dt
            item[1] += item[3] * dt
            item[4] -= dt
        self.items = [p for p in self.items if p[4] > 0]
        for label in self.labels:
            label[1] -= dt * 28
            label[3] -= dt
        self.labels = [p for p in self.labels if p[3] > 0]

    def draw(self, screen, text):
        """Desenha partículas e números sobre o cenário."""
        for x, y, vx, vy, life, color in self.items:
            draw.circle(screen, color, (int(x), int(y)), max(1, int(life * 6)))
        for x, y, label, life in self.labels:
            text(label, (int(x), int(y)), 19, GOLD, center=True)
