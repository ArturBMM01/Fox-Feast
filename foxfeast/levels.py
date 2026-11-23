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
