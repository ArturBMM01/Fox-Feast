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
