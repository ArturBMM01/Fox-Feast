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
