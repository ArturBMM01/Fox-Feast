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
