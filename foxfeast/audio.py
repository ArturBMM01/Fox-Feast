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
