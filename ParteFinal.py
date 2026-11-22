"""Fox Feast — Banquete no Pântano."""

__version__ = "1.5.0"

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

"""Entidades móveis com movimento contínuo entre centros das células."""
from .levels import Cell, Maze

class Actor:
    """Move uma entidade pela grade, sem atravessar paredes.

    A posição visual interpola origem e destino. A lógica só escolhe
    curvas em centros de células, evitando desalinhamentos no labirinto.
    """

    def __init__(self, cell: Cell):
        """Define o ponto inicial e prepara os dados de interpolação."""
        self.spawn = cell
        self.reset()

    def reset(self):
        """Devolve a entidade ao ponto inicial e interrompe o movimento."""
        self.cell = self.spawn
        self.target = self.spawn
        self.progress = 0.0
        self.direction = (1, 0)
        self.moving = False

    @property
    def position(self) -> tuple[float, float]:
        """Retorna a posição interpolada, em unidades de célula."""
        return (self.cell[0] + (self.target[0] - self.cell[0]) * self.progress,
                self.cell[1] + (self.target[1] - self.cell[1]) * self.progress)

    def advance(self, distance: float, maze: Maze, choose) -> list[Cell]:
        """Percorre a distância e informa todas as células alcançadas."""
        reached = []
        while distance > 1e-9:
            if not self.moving:
                direction = choose(self)
                target = (self.cell[0] + direction[0], self.cell[1] + direction[1])
                if target not in maze.neighbors[self.cell]:
                    break
                self.direction = direction
                self.target = target
                self.moving = True
            step = min(distance, 1.0 - self.progress)
            self.progress += step
            distance -= step
            if self.progress >= 1.0 - 1e-9:
                self.cell = self.target
                self.progress = 0.0
                self.moving = False
                reached.append(self.cell)
        return reached


class Fox(Actor):
    """Raposa controlada pelo jogador, com curva antecipada e inversão."""

    def __init__(self, cell: Cell):
        """Cria a raposa sem uma direção de movimento solicitada."""
        super().__init__(cell)
        self.queued = (0, 0)

    def request(self, direction: Cell):
        """Guarda a próxima curva; inversões de sentido são imediatas."""
        self.queued = direction
        if self.moving and direction == (-self.direction[0], -self.direction[1]):
            self.cell, self.target = self.target, self.cell
            self.progress = 1.0 - self.progress
            self.direction = direction

    def choose(self, maze: Maze) -> Cell:
        """Prioriza a curva pedida; segue reto enquanto ela não for possível."""
        target = (self.cell[0] + self.queued[0], self.cell[1] + self.queued[1])
        if target in maze.neighbors[self.cell]:
            return self.queued
        return self.direction if self.queued != (0, 0) else (0, 0)


class Hunter(Actor):
    """Caçador perseguidor com personalidade e tempo de reaparecimento."""

    def __init__(self, cell: Cell, index: int):
        """Define a personalidade e atrasa a primeira saída do caçador."""
        super().__init__(cell)
        self.index = index
        self.sleep = 1.7 + index * 0.4

    def choose(self, world) -> Cell:
        """Caça continuamente, podendo inverter a rota para seguir a raposa.

        Perto da raposa todos usam a menor rota até ela. Mais longe,
        alguns interceptam seu caminho. Rotas equivalentes evitam outros
        caçadores, para o grupo se distribuir pelos cruzamentos.
        """
        options = world.maze.neighbors[self.cell]
        fox_cell = world.fox.target if world.fox.moving else world.fox.cell
        fox_distances = world.distance_field(fox_cell)
        if world.power > 0:
            best = max(options, key=lambda p: fox_distances[p])
        else:
            close = fox_distances[self.cell] <= 5
            target = self.pursuit_target(world, fox_cell, close)
            distances = world.distance_field(target)
            occupied = [h.target if h.moving else h.cell for h in world.hunters
                        if h is not self and h.sleep <= 0]
            reverse = (self.cell[0] - self.direction[0], self.cell[1] - self.direction[1])
            best = min(options, key=lambda p: (
                distances[p],
                0 if close else occupied.count(p),
                p == reverse,
                p[1], p[0],
            ))
        return best[0] - self.cell[0], best[1] - self.cell[1]

    def pursuit_target(self, world, fox_cell: Cell, close: bool) -> Cell:
        """Mira na raposa ou em pontos adiante dela, respeitando paredes e curvas."""
        role = self.index % 3
        if close or role == 0 or not world.fox.moving:
            return fox_cell
        target = fox_cell
        direction = world.fox.direction
        queued = world.fox.queued
        used_turn = queued == (0, 0)
        lookahead = 2 if role == 1 else 4
        for _ in range(lookahead):
            turn = (target[0] + queued[0], target[1] + queued[1])
            if not used_turn and turn in world.maze.neighbors[target]:
                direction = queued
                used_turn = True
            ahead = (target[0] + direction[0], target[1] + direction[1])
            if ahead not in world.maze.neighbors[target]:
                break
            target = ahead
        return target


"""Labirintos reproduzíveis e busca em largura para navegação."""
from collections import deque
from dataclasses import dataclass
import random
from .config import COLS, ROWS, DIRECTIONS, TILE, BOARD_X, BOARD_Y

Cell = tuple[int, int]


@dataclass(frozen=True)
class Stage:
    """Identidade visual e dificuldade de uma fase."""

    title: str
    subtitle: str
    seed: int
    color: tuple[int, int, int]
    enemies: int
    speed: float
    power_factor: float
    shortcuts: int
    cols: int = COLS
    rows: int = ROWS
    spread_spawns: bool = False


STAGES = (
    Stage("Bosque das lanternas", "FÁCIL · 2 caçadores no caminho.",
          17, (53, 117, 95), 2, 3.30, 1.00, 18, 17, 13),
    Stage("Margens do rio", "MÉDIA · 4 caçadores no caminho.",
          17, (48, 125, 119), 4, 3.30, 1.00, 24, 19, 15, True),
    Stage("Ruínas do rio", "DIFÍCIL · 14 caçadores no caminho.",
          17, (57, 101, 139), 14, 3.30, 1.00, 35),
)


class Maze:
    """Gera um mapa conectado e guarda sua lista de vizinhos.

    A busca em profundidade abre corredores. Depois, passagens extras
    criam circuitos para escapar dos inimigos. As sementes fixas fazem
    cada fase ter sempre o mesmo desenho, facilitando testes e treino.
    """

    def __init__(self, stage: Stage):
        """Constrói corredores, atalhos, vizinhos, frutas e pontos de saída."""
        self.stage = stage
        self.cols, self.rows = stage.cols, stage.rows
        self.origin = (BOARD_X + (COLS - self.cols) * TILE // 2,
                       BOARD_Y + (ROWS - self.rows) * TILE // 2)
        self.start = (1, 1)
        rng = random.Random(stage.seed)
        self.floor = {self.start}
        stack = [self.start]
        while stack:
            x, y = stack[-1]
            options = [(x + dx * 2, y + dy * 2) for dx, dy in DIRECTIONS
                       if 0 < x + dx * 2 < self.cols - 1
                       and 0 < y + dy * 2 < self.rows - 1
                       and (x + dx * 2, y + dy * 2) not in self.floor]
            if not options:
                stack.pop()
                continue
            nx, ny = rng.choice(options)
            self.floor.update({(nx, ny), ((x + nx) // 2, (y + ny) // 2)})
            stack.append((nx, ny))
        walls = [(x, y) for y in range(1, self.rows - 1)
                 for x in range(1, self.cols - 1) if (x, y) not in self.floor]
        rng.shuffle(walls)
        opened = 0
        for x, y in walls:
            horizontal = (x - 1, y) in self.floor and (x + 1, y) in self.floor
            vertical = (x, y - 1) in self.floor and (x, y + 1) in self.floor
            if horizontal != vertical:
                self.floor.add((x, y))
                opened += 1
                if opened == stage.shortcuts:
                    break
        self.neighbors = {
            p: [(p[0] + dx, p[1] + dy) for dx, dy in DIRECTIONS
                if (p[0] + dx, p[1] + dy) in self.floor]
            for p in sorted(self.floor)
        }
        # Os quatro cantos ímpares são sempre corredores do algoritmo.
        self.fruits = {(1, self.rows - 2), (self.cols - 2, 1),
                       (self.cols - 2, self.rows - 2), (self.cols // 2 | 1, self.rows // 2 | 1)}
        distances = self.distances(self.start)
        if stage.spread_spawns:
            self.spawns = self.distributed_spawns(distances)
            return
        # Entradas distribuídas em torno da área inicial: a perseguição
        # começa mais cedo, preservando pelo menos dez passos de segurança.
        candidates = sorted(self.floor, key=lambda p: (abs(distances[p] - 18), p))
        self.spawns = []
        for p in candidates:
            if distances[p] < 10:
                continue
            if all(abs(p[0] - q[0]) + abs(p[1] - q[1]) > 4
                   for q in self.spawns):
                self.spawns.append(p)
                if len(self.spawns) == stage.enemies:
                    break

    def distributed_spawns(self, distances: dict[Cell, int]) -> list[Cell]:
        """Espalha as entradas pela área, longe da raposa e das frutas.

        A cada escolha, maximiza a menor separação física das entradas
        anteriores e da posição inicial. O desempate favorece distância
        de percurso maior até a raposa. Não depende da ordem de um set.
        """
        candidates = {p for p in self.floor
                      if distances[p] >= 14 and p not in self.fruits}
        spawns = []
        while candidates and len(spawns) < self.stage.enemies:
            references = [self.start, *spawns]
            cell = max(sorted(candidates), key=lambda p: (
                min(abs(p[0] - q[0]) + abs(p[1] - q[1]) for q in references),
                distances[p], p[1], p[0],
            ))
            spawns.append(cell)
            candidates.remove(cell)
        return spawns

    def distances(self, target: Cell) -> dict[Cell, int]:
        """Calcula a menor distância de cada corredor ao destino (BFS)."""
        result = {target: 0}
        queue = deque([target])
        while queue:
            current = queue.popleft()
            for cell in self.neighbors.get(current, []):
                if cell not in result:
                    result[cell] = result[current] + 1
                    queue.append(cell)
        return result

    def direction_to(self, origin: Cell, target: Cell) -> Cell:
        """Informa o primeiro passo de uma rota mais curta."""
        distances = self.distances(target)
        best = min(self.neighbors[origin], key=lambda p: distances.get(p, 9999))
        return best[0] - origin[0], best[1] - origin[1]

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

"""Laço principal, entrada do usuário e transições da interface."""
import pygame
from .audio import Audio
from .art import Particles
from .config import WIDTH, HEIGHT, FPS, MINT, GOLD, PINK
from .storage import SaveData
from .ui import Renderer, board_point
from .world import World

KEY_DIRECTIONS = {
    pygame.K_RIGHT: (1, 0), pygame.K_d: (1, 0),
    pygame.K_LEFT: (-1, 0), pygame.K_a: (-1, 0),
    pygame.K_UP: (0, -1), pygame.K_w: (0, -1),
    pygame.K_DOWN: (0, 1), pygame.K_s: (0, 1),
}


class App:
    """Conecta modelo, interface, som e armazenamento sem misturar funções."""

    def __init__(self, save_path=None, window_size=None):
        """Inicializa os serviços e abre uma janela adequada ao monitor."""
        pygame.mixer.pre_init(22050, -16, 1, 512)
        pygame.init()
        pygame.display.set_caption("Fox Feast — Banquete no Pântano")
        info = pygame.display.Info()
        scale = min(1.0, info.current_w * 0.93 / WIDTH, info.current_h * 0.87 / HEIGHT)
        initial_size = window_size or (int(WIDTH * scale), int(HEIGHT * scale))
        self.window = pygame.display.set_mode(initial_size, pygame.RESIZABLE)
        self.canvas = pygame.Surface((WIDTH, HEIGHT))
        self.renderer = Renderer(self.canvas)
        pygame.display.set_icon(self.renderer.art.sprite("fox", 64))
        self.save = SaveData(save_path)
        self.audio = Audio(self.save.muted, self.save.music_muted)
        self.particles = Particles()
        self.screen_name = "menu"
        self.world = None
        self.difficulty = 1
        self.running = True
        self.focus = 0
        self.mouse = (-1, -1)
        self.time = 0.0
        self.fullscreen = False
        self.windowed_size = initial_size
        self.last_events = []
        self.renderer.draw(self)

    def viewport(self):
        """Calcula a área de desenho, mantendo a proporção da imagem."""
        width, height = self.window.get_size()
        scale = min(width / WIDTH, height / HEIGHT)
        w, h = max(1, int(WIDTH * scale)), max(1, int(HEIGHT * scale))
        return pygame.Rect((width - w) // 2, (height - h) // 2, w, h)

    def logical_mouse(self, position):
        """Converte coordenadas da janela para as da interface lógica."""
        rect = self.viewport()
        if not rect.collidepoint(position):
            return (-1, -1)
        return ((position[0] - rect.x) * WIDTH / rect.width,
                (position[1] - rect.y) * HEIGHT / rect.height)

    def change_screen(self, name):
        """Muda de tela e reposiciona a seleção de teclado."""
        self.screen_name = name
        self.focus = 0
        self.mouse = (-1, -1)
        self.renderer.draw(self)

    def action(self, action):
        """Executa uma ação compartilhada por botões e atalhos."""
        self.audio.play("click")
        if action == "music":
            self.audio.set_music_muted(not self.audio.music_muted)
            self.save.music_muted = self.audio.music_muted
            self.save.write()
        elif action == "effects":
            self.audio.set_muted(not self.audio.muted)
            self.save.muted = self.audio.muted
            self.save.write()
        elif action in ("start", "restart"):
            self.world = World(self.difficulty)
            self.particles = Particles()
            self.change_screen("game")
        elif action in ("instructions", "credits"):
            self.change_screen(action)
        elif action in ("menu", "back"):
            if self.world:
                self.save.register(self.world.score, self.world.difficulty_index)
            self.change_screen("menu")
        elif action == "difficulty":
            self.difficulty = 1 - self.difficulty
        elif action == "pause":
            if self.world and self.world.status == "playing":
                self.change_screen("pause")
        elif action == "resume":
            self.change_screen("game")
        elif action == "next":
            self.world.next_stage()
            self.particles = Particles()
            self.change_screen("game")
        elif action == "quit":
            self.running = False

    def process_event(self, event):
        """Trata eventos de janela, teclas e cliques sem bloquear o laço."""
        if event.type == pygame.QUIT:
            self.running = False
        elif event.type == pygame.VIDEORESIZE and not self.fullscreen:
            self.windowed_size = (max(600, event.w), max(420, event.h))
            self.window = pygame.display.set_mode(self.windowed_size, pygame.RESIZABLE)
        elif event.type in (pygame.WINDOWFOCUSLOST, pygame.WINDOWMINIMIZED):
            if self.screen_name == "game" and self.world.status == "playing":
                self.change_screen("pause")
        elif event.type == pygame.MOUSEMOTION:
            self.mouse = self.logical_mouse(event.pos)
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            pos = self.logical_mouse(event.pos)
            for rect, action in self.renderer.buttons:
                if rect.collidepoint(pos):
                    self.action(action)
                    break
        elif event.type == pygame.KEYDOWN:
            self._key(event)

    def _key(self, event):
        """Resolve atalhos globais antes dos controles de cada tela."""
        key = event.key
        if key in (pygame.K_m, pygame.K_n):
            self.action("effects" if key == pygame.K_m else "music")
            return
        if key == pygame.K_F11:
            self.fullscreen = not self.fullscreen
            if self.fullscreen:
                self.windowed_size = self.window.get_size()
                self.window = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
            else:
                self.window = pygame.display.set_mode(self.windowed_size, pygame.RESIZABLE)
            return
        live = (self.screen_name == "game" and self.world.status == "playing")
        if live:
            if key in KEY_DIRECTIONS:
                self.world.fox.request(KEY_DIRECTIONS[key])
            elif key == pygame.K_SPACE:
                self.world.request_dash()
            elif key in (pygame.K_p, pygame.K_ESCAPE):
                self.action("pause")
            return
        if key == pygame.K_ESCAPE:
            self.action("resume" if self.screen_name == "pause" else "back")
            return
        if key == pygame.K_p and self.screen_name == "pause":
            self.action("resume")
            return
        buttons = self.renderer.buttons
        if not buttons:
            return
        if key in (pygame.K_DOWN, pygame.K_s, pygame.K_TAB, pygame.K_RIGHT):
            delta = -1 if key == pygame.K_TAB and event.mod & pygame.KMOD_SHIFT else 1
            self.focus = (self.focus + delta) % len(buttons)
            self.mouse = (-1, -1)
        elif key in (pygame.K_UP, pygame.K_w, pygame.K_LEFT):
            self.focus = (self.focus - 1) % len(buttons)
            self.mouse = (-1, -1)
        elif key in (pygame.K_RETURN, pygame.K_SPACE):
            self.action(buttons[self.focus % len(buttons)][1])

    def update(self, dt):
        """Atualiza apenas uma partida ativa; pausa congela todos os temporizadores."""
        dt = max(0.0, min(dt, 0.05))
        self.time += dt
        self.last_events = []
        if self.screen_name == "game" and self.world.status == "playing":
            previous_status = self.world.status
            self.world.update(dt)
            self.last_events = self.world.events[:]
            self.world.events.clear()
            for name, pos, points in self.last_events:
                self.audio.play(name)
                color = {"eat": MINT, "power": GOLD, "hunter": GOLD,
                         "hit": PINK, "dash": MINT, "clear": GOLD}[name]
                x, y = board_point(pos, self.world.maze)
                self.particles.burst(x, y, color, 4 if name == "eat" else 20,
                                     points if name in ("power", "hunter", "clear") else None)
            if self.world.status != previous_status:
                self.focus = 0
                self.save.register(self.world.score, self.world.difficulty_index)
            self.particles.update(dt)

    def draw(self):
        """Renderiza e apresenta a imagem escalada com margens proporcionais."""
        self.renderer.draw(self)
        rect = self.viewport()
        self.window.fill((4, 10, 17))
        if rect.size == (WIDTH, HEIGHT):
            self.window.blit(self.canvas, rect)
        else:
            self.window.blit(pygame.transform.smoothscale(self.canvas, rect.size), rect)
        pygame.display.flip()

    def run(self):
        """Mantém entrada, atualização e desenho a até 60 quadros por segundo."""
        clock = pygame.time.Clock()
        try:
            while self.running:
                dt = clock.tick(FPS) / 1000.0
                for event in pygame.event.get():
                    self.process_event(event)
                self.update(dt)
                self.draw()
        finally:
            self.close()

    def close(self):
        """Persiste a pontuação e libera os recursos do Pygame."""
        if self.world:
            self.save.register(self.world.score, self.world.difficulty_index)
        pygame.quit()

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

"""Regras da partida, independentes da interface e da placa de som."""
from math import ceil, hypot
from .config import DIFFICULTIES
from .entities import Fox, Hunter
from .levels import Maze, STAGES

class World:
    """Controla vidas, coleta, colisões, poderes e progressão das fases."""

    def __init__(self, difficulty=1):
        """Começa uma campanha com os recursos da dificuldade escolhida."""
        self.difficulty_index = difficulty
        self.rules = DIFFICULTIES[difficulty]
        self.score = 0
        self.lives = self.rules.lives
        self.elapsed = 0.0
        self.eaten = 0
        self.hunters_defeated = 0
        self.events = []
        self.load_stage(0)

    def load_stage(self, index):
        """Prepara uma fase preservando os pontos e as vidas da campanha."""
        self.stage_index = index
        self.maze = Maze(STAGES[index])
        self.fox = Fox(self.maze.start)
        self.hunters = [Hunter(p, i) for i, p in enumerate(self.maze.spawns)]
        self.crocs = self.maze.floor - self.maze.fruits - {self.maze.start}
        self.total_crocs = len(self.crocs)
        self.fruits = self.maze.fruits.copy()
        self.power = 0.0
        self.invulnerable = 2.0
        self.dash = 0.0
        self.dash_cooldown = 0.0
        self.chain = 0
        self.recovered_lives = 0
        self.stage_elapsed = 0.0
        self.status = "playing"
        self.events.clear()
        self._fields = {}

    @property
    def power_duration(self):
        """Mantém a duração da fruta igual nas três fases de cada modo."""
        return self.rules.power_seconds * STAGES[self.stage_index].power_factor

    def distance_field(self, target):
        """Reutiliza distâncias entre decisões da IA, limitando o cache."""
        if target not in self._fields:
            if len(self._fields) >= 32:
                self._fields.clear()
            self._fields[target] = self.maze.distances(target)
        return self._fields[target]

    def request_dash(self):
        """Ativa impulso de velocidade; não concede proteção contra dano."""
        if self.status == "playing" and self.dash_cooldown <= 0:
            self.dash = 0.55
            self.dash_cooldown = 3.5
            self.events.append(("dash", self.fox.position, 0))

    def update(self, dt):
        """Avança a simulação com subpassos para não pular colisões."""
        if self.status != "playing" or dt <= 0:
            return
        # A interface limita dt; o limite aqui também protege chamadas externas.
        dt = min(dt, 0.1)
        steps = max(1, ceil(dt * 120))
        for _ in range(steps):
            if self.status != "playing":
                break
            self._step(dt / steps)

    def _step(self, dt):
        """Executa movimento e regras em um pequeno intervalo de tempo."""
        self.elapsed += dt
        self.stage_elapsed += dt
        self.power = max(0.0, self.power - dt)
        self.invulnerable = max(0.0, self.invulnerable - dt)
        self.dash = max(0.0, self.dash - dt)
        self.dash_cooldown = max(0.0, self.dash_cooldown - dt)
        speed = 9.5 if self.dash > 0 else 5.6
        reached = self.fox.advance(speed * dt, self.maze,
                                   lambda actor: self.fox.choose(self.maze))
        for cell in reached:
            self.collect(cell)
        fox_x, fox_y = self.fox.position
        for hunter in self.hunters:
            if hunter.sleep > 0:
                hunter.sleep = max(0.0, hunter.sleep - dt)
                continue
            speed = STAGES[self.stage_index].speed * self.rules.enemy_factor
            if self.power > 0:
                speed *= 0.65
            hunter.advance(speed * dt, self.maze, lambda actor: actor.choose(self))
            hunter_x, hunter_y = hunter.position
            if hypot(hunter_x - fox_x, hunter_y - fox_y) < 0.68:
                if self.power > 0:
                    self.chain += 1
                    points = min(4, self.chain) * 200
                    self.score += points
                    self.hunters_defeated += 1
                    self.events.append(("hunter", hunter.position, points))
                    hunter.reset()
                    hunter.sleep = 4.0
                elif self.invulnerable <= 0:
                    self.hit()
                    return
        if not self.crocs and self.status == "playing":
            bonus = 500 + self.lives * 100
            self.score += bonus
            self.status = "won" if self.stage_index == len(STAGES) - 1 else "level_clear"
            if self.status == "level_clear":
                # Uma recuperação limitada torna a campanha longa mais justa.
                previous_lives = self.lives
                self.lives = min(self.rules.lives, self.lives + 1)
                self.recovered_lives = self.lives - previous_lives
            self.events.append(("clear", self.fox.position, bonus))

    def collect(self, cell):
        """Consome jacarés pequenos e frutas ao chegar ao centro da célula."""
        if cell in self.crocs:
            self.crocs.remove(cell)
            self.score += 10
            self.eaten += 1
            self.events.append(("eat", cell, 10))
        if cell in self.fruits:
            self.fruits.remove(cell)
            self.power = self.power_duration
            self.chain = 0
            self.score += 50
            self.events.append(("power", cell, 50))

    def hit(self):
        """Desconta uma vida e reposiciona personagens, mantendo a coleta."""
        self.lives -= 1
        self.events.append(("hit", self.fox.position, 0))
        if self.lives <= 0:
            self.status = "game_over"
            return
        self.fox.reset()
        self.fox.queued = (0, 0)
        self.power = self.dash = 0.0
        self.invulnerable = 2.5
        for hunter in self.hunters:
            hunter.reset()
            hunter.sleep = 2.5 + hunter.index * 0.5

    def next_stage(self):
        """Abre a próxima fase somente depois da tela de conclusão."""
        if self.status == "level_clear":
            self.load_stage(self.stage_index + 1)

"""Trilha e efeitos sintetizados localmente, sem downloads ou arquivos externos."""
from array import array
from math import sin, pi
import pygame

RATE = 22050


def tone(notes, beat=0.12, volume=0.3):
    """Cria PCM mono de 16 bits a partir de frequências e durações."""
    samples = array("h")
    for frequency, length in notes:
        count = max(1, int(RATE * beat * length))
        for i in range(count):
            t = i / RATE
            envelope = min(1.0, i / 160) * min(1.0, (count - i) / 650)
            value = sin(2 * pi * frequency * t)
            value += 0.22 * sin(4 * pi * frequency * t)
            samples.append(int(22000 * volume * envelope * value))
    return samples.tobytes()


class Audio:
    """Gerencia um canal de música e efeitos; funciona sem dispositivo de áudio."""

    def __init__(self, muted=False, music_muted=False):
        """Sintetiza efeitos e trilha uma única vez, se houver áudio disponível."""
        self.muted = muted
        self.music_muted = music_muted
        self.available = False
        self.sounds = {}
        try:
            if not pygame.mixer.get_init():
                pygame.mixer.init(RATE, -16, 1, 512)
            pygame.mixer.set_num_channels(12)
            pygame.mixer.set_reserved(1)
            sequences = {
                "eat": [(740, 0.25), (988, 0.25)],
                "power": [(392, 1), (523, 1), (659, 1), (784, 2)],
                "hunter": [(523, 0.6), (659, 0.6), (1047, 1.8)],
                "hit": [(294, 1), (220, 1), (147, 2)],
                "dash": [(330, 0.3), (440, 0.3), (660, 0.4)],
                "clear": [(523, 1), (659, 1), (784, 1), (1047, 3)],
                "click": [(660, 0.35), (880, 0.35)],
            }
            self.sounds = {name: pygame.mixer.Sound(buffer=tone(notes))
                           for name, notes in sequences.items()}
            melody = [392, 0, 494, 587, 659, 587, 494, 440,
                      392, 0, 330, 392, 494, 440, 330, 0,
                      349, 0, 440, 523, 587, 523, 440, 392,
                      330, 392, 494, 587, 494, 392, 294, 0]
            self.theme = pygame.mixer.Sound(buffer=tone([(f, 1) for f in melody],
                                                        beat=0.18, volume=0.18))
            self.music_channel = pygame.mixer.Channel(0)
            self.music_channel.play(self.theme, loops=-1, fade_ms=900)
            self.available = True
            self.set_muted(muted)
            self.set_music_muted(music_muted)
        except pygame.error:
            self.available = False

    def set_muted(self, muted):
        """Liga ou desliga somente os efeitos, preservando a música."""
        self.muted = muted
        if self.available and muted:
            for index in range(1, pygame.mixer.get_num_channels()):
                pygame.mixer.Channel(index).stop()

    def set_music_muted(self, muted):
        """Controla a trilha sem silenciar os efeitos nem reiniciá-la."""
        self.music_muted = muted
        if self.available:
            self.music_channel.set_volume(0.0 if muted else 0.48)

    def play(self, name):
        """Toca um efeito se houver áudio disponível e o som estiver ativo."""
        if self.available and not self.muted and name in self.sounds:
            self.sounds[name].play()

"""Interface, cenário e telas; não altera as regras da simulação."""
import math
import pygame
from pygame import draw
from .art import Art
from .config import (WIDTH, HEIGHT, TILE, BOARD_X, BOARD_Y,
                     BG, PANEL, TEXT, MUTED, MINT, GOLD, PINK,
                     DIFFICULTIES)
from .levels import STAGES
from .scenery import Scenery

CONTROLS = "SETAS / WASD  mover     ESPAÇO  impulso     P / ESC  pausa     N  música     M  efeitos"


def board_point(position, maze=None):
    """Converte uma posição da grade para o centro correspondente na tela."""
    x, y = maze.origin if maze is not None else (BOARD_X, BOARD_Y)
    return (int(x + (position[0] + 0.5) * TILE),
            int(y + (position[1] + 0.5) * TILE))


class Renderer:
    """Renderiza o jogo em uma resolução lógica estável e escalável."""

    def __init__(self, surface):
        """Associa a superfície lógica e inicializa os caches visuais."""
        self.screen = surface
        self.art = Art()
        self.fonts = {}
        self.text_cache = {}
        self.buttons = []
        self.board = None
        self.board_key = None
        self.scenery = None

    def text(self, message, pos, size=24, color=TEXT, center=False):
        """Reutiliza fontes e até 256 textos já renderizados, sem mudar pixels."""
        if size not in self.fonts:
            self.fonts[size] = pygame.font.Font(None, size)
        key = str(message), size, tuple(color)
        if key not in self.text_cache:
            if len(self.text_cache) >= 256:
                self.text_cache.clear()
            self.text_cache[key] = self.fonts[size].render(key[0], True, color)
        image = self.text_cache[key]
        rect = image.get_rect(center=pos) if center else image.get_rect(topleft=pos)
        self.screen.blit(image, rect)
        return rect

    def labels(self, entries):
        """Desenha uma lista de textos na ordem informada."""
        for entry in entries:
            self.text(*entry)

    def sprite_at(self, kind, size, point, frame=0, direction=(1, 0), variant=0):
        """Centraliza um sprite, compartilhando o desenho usado em todas as telas."""
        image = self.art.sprite(kind, size, frame, direction, variant)
        self.screen.blit(image, image.get_rect(center=point))

    def panel(self, rect, color=PANEL, border=(36, 61, 67), radius=18):
        """Desenha um cartão com contorno discreto."""
        draw.rect(self.screen, color, rect, border_radius=radius)
        if border:
            draw.rect(self.screen, border, rect, width=1, border_radius=radius)

    def button(self, app, rect, label, action, primary=False):
        """Registra um botão para mouse e navegação por teclado."""
        rect = pygame.Rect(rect)
        focus = len(self.buttons) == app.focus or rect.collidepoint(app.mouse)
        fill = MINT if primary else (31, 56, 62)
        if focus:
            fill = (149, 251, 205) if primary else (44, 76, 79)
        draw.rect(self.screen, fill, rect, border_radius=12)
        if focus:
            draw.rect(self.screen, GOLD if not primary else TEXT,
                             rect.inflate(6, 6), 2, border_radius=15)
        self.text(label, rect.center, 25, BG if primary else TEXT, center=True)
        self.buttons.append((rect, action))

    def bar(self, rect, fraction, color):
        """Desenha uma barra normalizada, incluindo o valor zero."""
        rect = pygame.Rect(rect)
        draw.rect(self.screen, (30, 52, 58), rect, border_radius=5)
        width = int(rect.width * max(0.0, min(1.0, fraction)))
        if width:
            draw.rect(self.screen, color, (rect.x, rect.y, width, rect.height),
                             border_radius=5)

    def draw(self, app):
        """Escolhe a tela atual e atualiza a lista de botões disponíveis."""
        self.buttons = []
        if app.screen_name not in ("menu", "instructions", "credits") and app.world:
            if self.board_key != app.world.stage_index:
                self.prepare_board(app.world)
            self.scenery.backdrop(self.screen, app.time)
        else:
            self.art.backdrop(self.screen, app.time)
        if app.screen_name == "menu":
            self.menu(app)
        elif app.screen_name in ("instructions", "credits"):
            self.info(app)
        else:
            self.game(app)
            if app.screen_name == "pause":
                self.overlay(app, "TEMPO PARA RESPIRAR", "Pausa no pântano",
                             "A partida fica congelada até você continuar.",
                             [("Continuar", "resume"), ("Voltar ao menu", "menu")])
            elif app.world.status == "level_clear":
                message = ("Bônus somado e uma vida recuperada. Prepare-se!"
                           if app.world.recovered_lives else
                           "Bônus da fase somado. O próximo pântano espera.")
                self.overlay(app, f"FASE {app.world.stage_index + 1:02d} / {len(STAGES):02d} CONCLUÍDA",
                             "Banquete concluído!", message,
                             [("Próxima fase", "next"), ("Voltar ao menu", "menu")])
            elif app.world.status in ("game_over", "won"):
                victory = app.world.status == "won"
                self.overlay(app, "TODOS OS PÂNTANOS SÃO SEUS" if victory else "FIM DE PARTIDA",
                             "A raposa virou lenda!" if victory else "Até a próxima mordida.",
                             f"{app.world.score:06d} pontos   ·   {app.world.eaten} jacarés   ·   "
                             f"{int(app.world.elapsed) // 60:02d}:{int(app.world.elapsed) % 60:02d}",
                             [("Jogar novamente", "restart"), ("Voltar ao menu", "menu")])

        if app.world and app.screen_name not in ("menu", "instructions", "credits"):
            self.button(app, (610, 43, 200, 39),
                        "Música OFF" if app.audio.music_muted else "Música ON", "music")
            self.button(app, (824, 43, 200, 39),
                        "Efeitos OFF" if app.audio.muted else "Efeitos ON", "effects")

    def brand(self):
        """Apresenta a marca e uma moldura discreta comum às telas."""
        self.text("FOX / FEAST", (48, 32), 29, MINT)
        self.text("UMA RAPOSA. UM PÂNTANO. MUITA FOME.", (48, 65), 16, MUTED)
        draw.line(self.screen, (35, 58, 64), (48, 100), (1152, 100))

    def menu(self, app):
        """Desenha a abertura, seleção de dificuldade e arte de apresentação."""
        self.brand()
        self.labels([
            ("UMA AVENTURA EM 3 FASES", (64, 145), 20, GOLD),
            ("FOX", (58, 183), 108, TEXT), ("FEAST", (58, 270), 108, MINT),
            ("Banquete no Pântano", (66, 369), 31, GOLD),
            ("Coma jacarés. Engane os caçadores.", (66, 414), 24, MUTED),
            ("Pegue frutas douradas e vire o jogo.", (66, 445), 24, MUTED),
        ])
        difficulty = DIFFICULTIES[app.difficulty].name
        for rect, label, action, primary in (
            ((66, 501, 334, 58), "Jogar agora   >", "start", True),
            ((66, 574, 334, 49), "Como jogar", "instructions", False),
            ((66, 638, 334, 49), f"Dificuldade: {difficulty}", "difficulty", False),
            ((66, 702, 159, 43), "Créditos", "credits", False),
            ((241, 702, 159, 43), "Sair", "quit", False),
        ):
            self.button(app, rect, label, action, primary)
        # Diorama vetorial de um trecho do pântano.
        self.panel((493, 143, 659, 603), (16, 37, 44), (36, 71, 73), 30)
        draw.circle(self.screen, (24, 53, 54), (827, 393), 210)
        draw.circle(self.screen, (29, 67, 62), (827, 393), 166, 2)
        draw.circle(self.screen, (37, 84, 71), (827, 393), 194, 1)
        self.text("O BANQUETE VAI COMEÇAR", (823, 191), 25, GOLD, True)
        path = [(557, 556), (650, 556), (650, 481), (1004, 481),
                (1004, 595), (1090, 595)]
        draw.lines(self.screen, (30, 71, 70), False, path, 53)
        draw.lines(self.screen, (43, 92, 80), False, path, 2)
        for i, x in enumerate((699, 764, 829, 894, 959)):
            self.sprite_at("croc", 42, (x, 482), int(app.time * 6 + i) % 4)
        self.sprite_at("fox", 237, (807, 346), int(app.time * 6) % 4)
        self.sprite_at("fruit", 65, (1004, 564), int(app.time * 5) % 4)
        self.sprite_at("hunter", 87, (573, 540), int(app.time * 6) % 4, (-1, 0), 1)
        self.labels([
            (f"{len(STAGES):02d} FASES", (570, 660), 23, MINT),
            ("02 MODOS", (764, 660), 23, MINT), ("01 BANQUETE", (953, 660), 23, MINT),
            ("RECORDE " + difficulty.upper(), (510, 781), 18, MUTED),
            (f"{app.save.records[app.difficulty]:06d}", (730, 773), 32, GOLD),
            ("N: música  ·  M: efeitos  ·  Enter: selecionar", (48, 805), 18, MUTED),
            ("2 / 4 / 14 CAÇADORES", (946, 805), 18, MINT),
        ])

        self.button(app, (526, 697, 270, 36),
                    "Música: OFF" if app.audio.music_muted else "Música: ON", "music")
        self.button(app, (816, 697, 302, 36),
                    "Efeitos: OFF" if app.audio.muted else "Efeitos: ON", "effects")

    def info(self, app):
        """Mostra regras completas, controles ou créditos da criação."""
        self.brand()
        instructions = app.screen_name == "instructions"
        self.text("Manual do banquete" if instructions else "Por trás do pântano",
                  (60, 133), 56)
        if instructions:
            cards = [
                ("01", "COMA OS PEQUENOS", ["Os jacarés verdes pequenos valem 10 pontos.",
                   "Coma todos: são 3 fases com cenários diferentes.",
                   "Ao passar, recupere uma vida até o limite do modo."], "croc", 0),
                ("02", "VIRE O JOGO", ["Fruta dourada: 50 pontos e poder temporário.",
                   "Com o banquete ativo, derrote os caçadores azuis.",
                   "A sequência vale 200 / 400 / 600 / 800 pontos."], "fruit", 0),
                ("03", "ESCOLHA SEU CAMINHO", ["Caçadores perseguem sem parar e tentam cercar você.",
                   "Encostar neles sem poder custa uma vida.",
                   "Fácil: 2. Média: 4. Difícil: 14 caçadores."], "hunter", 1),
            ]
            for i, (number, title, lines, kind, variant) in enumerate(cards):
                y = 217 + i * 144
                self.panel((60, y, 1080, 128))
                sprite = self.art.sprite(kind, 76, int(app.time * 5), variant=variant)
                self.screen.blit(sprite, (82, y + 22))
                self.text(number + "  /  " + title, (184, y + 18), 25, MINT)
                for j, line in enumerate(lines):
                    self.text(line, (184, y + 48 + j * 23), 22, TEXT if j == 0 else MUTED)
            self.text(CONTROLS, (66, 677), 24, GOLD)
            self.text("Antecipe a curva: aperte a direção antes de chegar ao cruzamento.",
                      (66, 713), 22, MUTED)
        else:
            self.panel((60, 222, 1080, 458))
            lines = [
                ("FOX FEAST — BANQUETE NO PÂNTANO", MINT, 30),
                ("Projeto de Design de Software · Python + Pygame", TEXT, 26),
                ("Responsáveis pelo projeto:", TEXT, 25),
                ("Henrique Campos de Paula Ribeiro", TEXT, 25),
                ("Artur Belem Marchetti Moraes", TEXT, 25),
                ("Arte vetorial, animações e sons gerados pelo próprio código.", MUTED, 24),
                ("Inspiração na mecânica de labirinto de Pac-Man, da Namco.", MUTED, 24),
                ("Sem reutilizar imagens, músicas ou personagens do jogo original.", MUTED, 23),
            ]
            for i, (line, color, size) in enumerate(lines):
                self.text(line, (87, 250 + i * 44), size, color)
        self.button(app, (60, 759, 232, 48), "Voltar ao menu", "back", True)

    def prepare_board(self, world):
        """Prepara o ambiente visual da fase, preservando a geometria do mapa."""
        self.board_key = world.stage_index
        self.scenery = Scenery(world.maze, world.stage_index)
        self.board = self.scenery.board

    def game(self, app):
        """Desenha HUD, mapa, objetos animados, personagens e efeitos."""
        world = app.world
        self.brand()
        self.text("PONTOS", (48, 116), 17, MUTED)
        self.text(f"{world.score:06d}", (47, 136), 33, GOLD)
        self.text("RECORDE", (253, 116), 17, MUTED)
        record = max(app.save.records[world.difficulty_index], world.score)
        self.text(f"{record:06d}", (252, 136), 33)
        self.text("VIDAS", (464, 116), 17, MUTED)
        for i in range(world.lives):
            s = self.art.sprite("fox", 28)
            self.screen.blit(s, (459 + i * 29, 134))
        self.text(f"{int(world.elapsed) // 60:02d}:{int(world.elapsed) % 60:02d}",
                  (671, 135), 30, MUTED)
        self.panel((40, 166, 716, 604), (8, 23, 29), (47, 79, 78), 12)
        if self.board_key != world.stage_index:
            self.prepare_board(world)
        self.screen.blit(self.board, world.maze.origin)
        self.scenery.ambient(self.screen, app.time)
        # Cada quadro do jacaré é obtido uma vez por tela, em vez de por item.
        croc_frames = [self.art.sprite("croc", 21, frame) for frame in range(4)]
        for x, y in sorted(world.crocs):
            frame = int(app.time * 5 + x * 0.5 + y) % 4
            sprite = croc_frames[frame]
            point = board_point((x, y), world.maze)
            self.screen.blit(sprite, sprite.get_rect(center=point))
        for cell in sorted(world.fruits):
            point = board_point(cell, world.maze)
            radius = 12 + int(math.sin(app.time * 5) * 2)
            draw.circle(self.screen, (87, 76, 44), point, radius, 1)
            self.sprite_at("fruit", 29, point, int(app.time * 6))
        for hunter in world.hunters:
            point = board_point(hunter.position, world.maze)
            if hunter.sleep > 0:
                draw.circle(self.screen, (53, 76, 78), point, 10, 1)
                self.text(f"{math.ceil(hunter.sleep)}", point, 17, MUTED, True)
                continue
            vulnerable = world.power > 0
            flash = world.power < 2 and int(app.time * 9) % 2 == 0
            variant = 6 if vulnerable and not flash else 1 + hunter.index % 5
            self.sprite_at("hunter", 38, point, int(app.time * 9), hunter.direction, variant)
            if vulnerable:
                self.text("!", (point[0], point[1] - 18), 17, GOLD, True)
        point = board_point(world.fox.position, world.maze)
        if world.power > 0:
            draw.circle(self.screen, GOLD, point, 19, 1)
            draw.circle(self.screen, (74, 93, 61), point, 22, 1)
        if world.dash > 0:
            dx, dy = world.fox.direction
            for i in range(1, 4):
                draw.circle(self.screen, (47 + i * 12, 112, 105),
                                   (point[0] - dx * i * 8, point[1] - dy * i * 8), 6 - i)
        if world.invulnerable <= 0 or int(app.time * 12) % 2 == 0:
            frame = int(app.time * 12) % 4 if world.fox.moving else 0
            self.sprite_at("fox", 37, point, frame, world.fox.direction)
        app.particles.draw(self.screen, self.text)
        self.sidebar(app)
        self.text(CONTROLS, (48, 794), 21, MUTED)
        if app.screen_name == "game" and world.status == "playing":
            self.button(app, (1050, 43, 102, 39), "Pausa", "pause")

    def sidebar(self, app):
        """Mostra objetivos, recarga, poder e dificuldade ao lado do mapa."""
        world = app.world
        self.panel((784, 174, 368, 588))
        level_name = ("FÁCIL", "MÉDIA", "DIFÍCIL")[world.stage_index]
        self.text(f"FASE {world.stage_index + 1} / {len(STAGES)}  ·  {level_name}", (808, 199), 20, MINT)
        title = STAGES[world.stage_index].title
        words = title.rsplit(" ", 1)
        self.text(words[0], (808, 234), 32)
        self.text(words[1], (808, 268), 32)
        self.text(self.scenery.theme.name, (808, 301), 16, self.scenery.theme.accent)
        draw.line(self.screen, (39, 65, 69), (808, 324), (1128, 324))
        self.text("JACARÉS NO CAMINHO", (808, 337), 19, MUTED)
        self.text(f"{len(world.crocs):03d}", (808, 365), 51, TEXT)
        self.text("restantes", (897, 389), 23, MUTED)
        self.bar((808, 425, 320, 9), 1 - len(world.crocs) / world.total_crocs, MINT)
        self.text("BANQUETE", (808, 463), 20, GOLD)
        if world.power > 0:
            self.text(f"ATIVO  ·  {world.power:.1f}s", (808, 491), 27, GOLD)
        else:
            self.text("Encontre a fruta dourada", (808, 491), 24, MUTED)
        self.bar((808, 527, 320, 7), world.power / world.power_duration, GOLD)
        self.text("IMPULSO  /  ESPAÇO", (808, 566), 20, MINT)
        ready = world.dash_cooldown <= 0
        self.text("Pronto para disparar" if ready else f"Recarregando  ·  {world.dash_cooldown:.1f}s",
                  (808, 594), 25, TEXT if ready else MUTED)
        self.bar((808, 628, 320, 7), 1 - world.dash_cooldown / 3.5, MINT)
        self.text(DIFFICULTIES[world.difficulty_index].name.upper(), (808, 674), 20, MINT)
        self.text(f"{len(world.hunters)} caçadores  ·  poder {world.power_duration:.1f}s",
                  (808, 701), 20, MUTED)
        status = "SEM DISPOSITIVO DE ÁUDIO" if not app.audio.available else (
            f"Música: {'OFF' if app.audio.music_muted else 'ON'} · "
            f"Efeitos: {'OFF' if app.audio.muted else 'ON'}")
        self.text(status, (808, 730), 17, MUTED)
        if not app.save.writable:
            self.text("Recorde temporário nesta sessão", (808, 746), 15, PINK)

    def overlay(self, app, tag, title, subtitle, buttons):
        """Desenha modal de pausa, transição de fase, vitória ou derrota."""
        self.buttons = []
        veil = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        veil.fill((4, 12, 22, 210))
        self.screen.blit(veil, (0, 0))
        self.panel((220, 231, 760, 379), (18, 38, 47), (71, 126, 110), 28)
        self.text(tag, (600, 275), 21, MINT, True)
        self.text(title, (600, 336), 47, TEXT, True)
        self.text(subtitle, (600, 393), 23, MUTED, True)
        self.text(f"PONTUAÇÃO  {app.world.score:06d}", (600, 443), 28, GOLD, True)
        for i, (label, action) in enumerate(buttons):
            self.button(app, (284 + i * 326, 510, 306, 54), label, action, i == 0)
