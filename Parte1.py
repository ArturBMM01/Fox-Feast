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

