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