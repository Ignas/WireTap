#!/usr/bin/python
import random
import time
import glob

import pygame
from pygame.locals import *


class Voice(object):

    male = True

    def __init__(self):
        self.benign_phrases = []
        self.suspicious_phrases = []

    @property
    def all_phrases(self):
        return self.benign_phrases + self.suspicious_phrases


class Console(object): # aka listening station

    def __init__(self):
        self.listening = False
        self.active = False
        self.swat_pending = 0
        self.swat_arrived = False
        self.swat_active = False
        self.swat_done = False
        self.personality = None

    @property
    def speaking(self):
        return self.active or self.swat_active

    def get_next_phrase(self):
        if self.personality:
            return self.personality.get_next_phrase(self.voice)

    def send_swat(self, delay=3):
        self.swat_pending = delay

    def kill(self):
        self.active = False
        self.swat_arrived = True


class BadGuy(object):

    next_level_on_capture = True

    score = 10

    def get_next_phrase(self, voice):
        return random.choice(voice.all_phrases)


class GoodGuy(object):

    next_level_on_capture = False

    score = -10

    def get_next_phrase(self, voice):
        return random.choice(voice.benign_phrases)


BAD_GUY = BadGuy()
GOOD_GUY = GoodGuy()


class Game(object):

    def __init__(self, voices):
        self.voices = voices
        self.consoles = []
        self.score = 0
        self.time_limit = 300
        self.level = 0
        self.n_consoles = 16
        self.good_guys = []

        for n in range(self.n_consoles):
            self.consoles.append(Console())

        self.start()

    def start(self):
        self.level = 1
        self.add_bad_guy()

    def tick(self, delta_t):
        self.time_limit -= delta_t
        if self.time_limit < 0:
            self.time_limit = 0
            return # end of level

        for c in self.consoles:
            if c.swat_pending:
                c.swat_pending -= delta_t
                if c.swat_pending < 1:
                    c.swat_pending = False
                    c.kill()
            if c.swat_done:
                c.swat_done = False
                self.kill_guy(c)

    def get_empty_consoles(self):
        return [c for c in self.consoles if not c.active]

    def add_guy(self, personality):
        empty_consoles = self.get_empty_consoles()
        if not empty_consoles:
            return
        console = random.choice(empty_consoles)
        console.personality = personality
        console.active = True
        console.voice = random.choice(self.voices)
        return console

    def add_bad_guy(self):
        return self.add_guy(BAD_GUY)

    def add_good_guy(self):
        return self.good_guys.append(self.add_guy(GOOD_GUY))

    def move_good_guy(self):
        console = self.good_guys.pop(0)
        console.active = False
        self.add_good_guy()

    def kill_guy(self, console):
        self.score += console.personality.score
        if console.personality.next_level_on_capture:
            self.next_level()

    def next_level(self):
        db = self.level in (4, 7, 12) and 2 or 1

        mg = 0
        if self.level >= 3:
            mg = 1
        elif self.level >= 8:
            mg = 2

        dg = 2 - db
        self.level += 1

        for n in range(dg):
            self.add_good_guy()

        for n in range(db):
            self.add_bad_guy()

        for n in range(mg):
            self.move_good_guy()


def prototype5():
    # XXX attempting to use 44100 Hz causes 100% CPU
    pygame.mixer.pre_init(22050, -16, 2, 2048)
    pygame.init()
    pygame.display.set_caption('Wiretap')
    pygame.mixer.set_num_channels(32)
    screen = pygame.display.set_mode((1024, 700), 0)

    voices = []
    n = 1
    while True:
        v = Voice()
        v.benign_phrases = map(pygame.mixer.Sound,
                               glob.glob('sounds/p%d_good*.wav' % n))
        v.suspicious_phrases = map(pygame.mixer.Sound,
                                   glob.glob('sounds/p%d_bad*.wav' % n))
        if not v.benign_phrases or not v.suspicious_phrases:
            break
        v.male = bool(glob.glob('sounds/p%d_*_m.wav'))
        n += 1
        voices.append(v)
    game = Game(voices)

    swat_sound = pygame.mixer.Sound('swat.wav')

    font = pygame.font.Font(None, 24)

    while True:
        # interact
        for event in pygame.event.get():
            if event.type == QUIT or event.type == KEYDOWN and (
                event.key == K_ESCAPE or event.unicode in ('q', 'Q')):
                t = font.render('Bye!', True, (254, 232, 123))
                screen.blit(t, ((1024 - t.get_width()) / 2,
                                (680 - t.get_height()) / 2))
                pygame.display.update()
                return
            if event.type == MOUSEBUTTONUP:
                if (abs(event.pos[0] % (1024/4) - 140) <= 11
                    and abs(event.pos[1] % (700/4) - 40) <= 11):
                    row = event.pos[1] / (700/4)
                    col = event.pos[0] / (1024/4)
                    if 0 <= row < 4 and 0 <= col < 4:
                        n = row * 4 + col
                        c = game.consoles[n]
                        c.listening = not c.listening
                if (abs(event.pos[0] % (1024/4) - 100) <= 70
                    and abs(event.pos[1] % (700/4) - 70) <= 15):
                    row = event.pos[1] / (700/4)
                    col = event.pos[0] / (1024/4)
                    if 0 <= row < 4 and 0 <= col < 4:
                        n = row * 4 + col
                        c = game.consoles[n]
                        c.send_swat()

        # render audio
        active_channels = sum(c.listening and c.speaking for c in game.consoles) or 1
        active_channels = (active_channels + 1.0) / 2 # slower attenuation
        for n, c in enumerate(game.consoles):
            channel = pygame.mixer.Channel(n)
            if c.listening:
                channel.set_volume(1.0 / active_channels)
            else:
                channel.set_volume(0.0)

            if c.active and channel.get_queue() is None:
                channel.queue(c.get_next_phrase())
            elif c.swat_arrived:
                c.swat_arrived = False
                c.swat_active = True
                channel.play(swat_sound)
            elif c.swat_active and not channel.get_busy():
                c.swat_active = False
                c.swat_done = True

        # draw
        screen.fill((0, 0, 0))
        for n, c in enumerate(game.consoles):
            row, col = divmod(n, 4)
            x, y = col * 1024/4, row * 700/4
            if c.speaking:
                color = (100, 200, 0)
                r = 15
            else:
                color = (0, 100, 0)
                r = 10
            pygame.draw.circle(screen, color, (x + 40, y + 40), r)
            if c.listening:
                color = (200, 150, 10)
            else:
                color = (100, 50, 0)
            pygame.draw.circle(screen, color, (x + 140, y + 40), 10)
            if c.swat_pending:
                color = (255, 23, 34)
                s = 'SEND SWAT: %d' % c.swat_pending
            elif c.swat_active:
                color = (255, 23, 34)
                s = 'SEND SWAT: !'
            else:
                color = (175, 23, 34)
                s = 'SEND SWAT'
            t = font.render(s, True, color)
            screen.blit(t, (x + 100 - t.get_width() / 2, y + 70))

        t = font.render('Level: %d' % game.level, True, (255, 255, 255))
        screen.blit(t, (10, 620))
        t = font.render('Score: %d' % game.score, True, (255, 255, 255))
        screen.blit(t, (10, 650))
        t = font.render('Time left: %d:%02d' % divmod(game.time_limit, 60), True, (255, 255, 255))
        screen.blit(t, (10, 680))

        if game.time_limit <= 0:
            t = font.render('Game over', True, (254, 232, 123))
            screen.blit(t, ((1024 - t.get_width()) / 2,
                            (680 - t.get_height()) / 2 - 30))

        pygame.display.flip()
        # wait
        time.sleep(0.1)
        game.tick(0.1)


if __name__ == '__main__':
    prototype5()
    print "Quitting!"
    t0 = time.time()
    pygame.quit()
    print "WTF did pygame.quit() do during the last %.1f seconds?" % (time.time() - t0)

