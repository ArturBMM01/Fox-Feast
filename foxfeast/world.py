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
