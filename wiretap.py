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

    disabled = False

    def __init__(self):
        self.listening = False
        self.active = False
        self.swat_pending = 0
        self.swat_arrived = False
        self.swat_active = False
        self.swat_done = False
        self.personality = NOBODY

    @property
    def speaking(self):
        return self.active or self.swat_active

    @property
    def swat_engaged(self):
        return self.swat_pending or self.swat_active or self.swat_arrived or self.swat_done

    def get_next_phrase(self):
        if self.personality:
            return self.personality.get_next_phrase(self.voice)

    def send_swat(self, delay=3):
        self.listening = True
        if not self.swat_engaged:
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


class Nobody(object):

    next_level_on_capture = False

    score = -5

    def get_next_phrase(self, voice):
        return None


NOBODY = Nobody()
BAD_GUY = BadGuy()
GOOD_GUY = GoodGuy()


class ScoreEffect(object):

    def __init__(self, console, score):
        self.console = console
        self.score = score


class Game(object):

    def __init__(self, voices):
        self.voices = voices
        self.consoles = []
        self.score = 0
        self.time_limit = 300
        self.level = 0
        self.n_consoles = 16
        self.good_guys = []
        self.effects = []
        self.paused = False

        for n in range(self.n_consoles):
            self.consoles.append(Console())
        self.consoles[11].disabled = True
        self.consoles[13].disabled = True

        self.start()

    def start(self):
        self.level = 1
        self.add_bad_guy()

    @property
    def running(self):
        return not self.paused and self.time_limit >= 0

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
                c.listening = False
                self.kill_guy(c)

    def get_empty_consoles(self):
        return [c for c in self.consoles if not c.active and not c.disabled]

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
        console.listening = False
        self.add_good_guy()

    def kill_guy(self, console):
        self.effects.append(ScoreEffect(console, console.personality.score))
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


class ScoreBubble(object):

    def __init__(self, x, y, text, color, font, time=3, dx=0, dy=-10, shadow=None):
        self.x = x
        self.y = y
        self.dx = dx
        self.dy = dy
        self.text = text
        self.color = color
        self.font = font
        self.surface = font.render(text, True, color)
        self.shadow = shadow
        if shadow:
            self.shadow_surface = font.render(text, True, shadow)
        else:
            self.shadow_surface = None
        self.x -= self.surface.get_width() / 2
        self.y -= self.surface.get_height() / 2
        self.time_left = time

    def tick(self, delta_t):
        self.time_left -= delta_t
        if self.time_left < 0:
            self.time_left = 0
            return False
        self.x += self.dx * delta_t
        self.y += self.dy * delta_t
        return True

    def set_alpha(self, alpha):
        r, g, b = self.color
        r, g, b = r * alpha, g * alpha, b * alpha
        self.surface = self.font.render(self.text, True, (r, g, b))

        if self.shadow:
            r, g, b = self.shadow
            r, g, b = r * alpha, g * alpha, b * alpha
            self.shadow_surface = self.font.render(self.text, True, (r, g, b))

    def draw(self, screen):
        if self.time_left > 0:
            if self.time_left < 1:
                self.set_alpha(self.time_left)
            if self.shadow_surface:
                screen.blit(self.shadow_surface, (int(self.x) + 1, int(self.y) + 1))
            screen.blit(self.surface, (int(self.x), int(self.y)))


class Layout(object):

    size = (1024, 768)

    background_src = "graphics/Background.png"

    grid_pos = (20, 20)
    grid_rows = 4
    grid_cols = 4
    grid_cell_size = (251, 145)

    speaking_pos = 195, 50
    speaking_inactive_src = "graphics/Lamp_inactive.png"
    speaking_active_src = "graphics/Lamp_active.png"
    speaking_red_src = "graphics/Lamp_done.png"

    listening_pos = 80, 40
    listening_size = 128, 64
    listening_off_src = "graphics/Off.png"
    listening_on_src = "graphics/On.png"

    swat_pos = 80, 100
    swat_size = 128, 64
    swat_off_src = "graphics/Send_swat.png"
    swat_on_src = "graphics/Send_swat_pressed.png"

    score_pos = 155, 90
    score_positive_color = (20, 200, 20)
    score_positive_shadow = (0, 20, 0)
    score_negative_color = (200, 20, 20)
    score_negative_shadow = (20, 0, 0)

    coffee_break_pos = 132, 651
    coffee_break_size = 128, 64
    coffee_break_off_src = "graphics/Break.png"
    coffee_break_on_src = "graphics/Break_pressed.png"

    quit_pos = 888, 651
    quit_size = 128, 64
    quit_off_src = "graphics/Quit.png"
    quit_on_src = "graphics/Quit_pressed.png"

    bye_pos = 512, 340
    bye_color = (254, 232, 123)
    bye_text = 'Bye!'

    game_over_pos = 512, 310
    game_over_color = (254, 232, 123)
    game_over_text = 'Game Over'

    def __init__(self, screen):
        self.screen = screen
        self.x = (screen.get_width() - self.size[0]) / 2
        self.y = (screen.get_height() - self.size[1]) / 2
        self.pos = (self.x, self.y)
        self.background = pygame.image.load(self.background_src)
        self.speaking_inactive = pygame.image.load(self.speaking_inactive_src)
        self.speaking_active = pygame.image.load(self.speaking_active_src)
        self.speaking_red = pygame.image.load(self.speaking_red_src)
        self.listening_on = pygame.image.load(self.listening_on_src)
        self.listening_off = pygame.image.load(self.listening_off_src)
        self.swat_on = pygame.image.load(self.swat_on_src)
        self.swat_off = pygame.image.load(self.swat_off_src)
        self.coffee_break_on = pygame.image.load(self.coffee_break_on_src)
        self.coffee_break_off = pygame.image.load(self.coffee_break_off_src)
        self.quit_on = pygame.image.load(self.quit_on_src)
        self.quit_off = pygame.image.load(self.quit_off_src)
        self.font = pygame.font.Font(None, 24)

    def console_pos(self, n):
        row, col = divmod(n, self.grid_cols)
        x = self.grid_pos[0] + col * self.grid_cell_size[0]
        y = self.grid_pos[1] + row * self.grid_cell_size[1]
        return (self.x + x, self.y + y)

    def console_idx(self, x, y):
        col = (x - self.x - self.grid_pos[0]) // self.grid_cell_size[0]
        row = (y - self.y - self.grid_pos[1]) // self.grid_cell_size[1]
        if 0 <= row < self.grid_rows and 0 <= col < self.grid_cols:
            return row * self.grid_cols + col

    def draw(self, game):
        screen = self.screen
        # XXX maybe fill areas outside background, if any
        screen.blit(self.background, (self.x, self.y))
        for n, c in enumerate(game.consoles):
            if c.disabled:
                continue

            pos = self.console_pos(n)

            if c.swat_engaged:
                img = self.speaking_red
            elif c.speaking:
                img = self.speaking_active
            else:
                img = self.speaking_inactive
            self.center_img(img, pos, self.speaking_pos)

            if c.listening:
                img = self.listening_on
            else:
                img = self.listening_off
            self.center_img(img, pos, self.listening_pos)

            if c.swat_engaged:
                img = self.swat_on
            else:
                img = self.swat_off
            self.center_img(img, pos, self.swat_pos)

        if game.paused:
            img = self.coffee_break_on
        else:
            img = self.coffee_break_off
        self.center_img(img, self.pos, self.coffee_break_pos)

        img = self.quit_off
        self.center_img(img, self.pos, self.quit_pos)

        font = self.font
        t = font.render('Level: %d' % game.level, True, (255, 255, 255))
        self.center_img(t, (self.x + 512, self.y + 620))
        t = font.render('Score: %d' % game.score, True, (255, 255, 255))
        self.center_img(t, (self.x + 512, self.y + 650))
        t = font.render('Time left: %d:%02d' % divmod(game.time_limit, 60), True, (255, 255, 255))
        self.center_img(t, (self.x + 512, self.y + 680))

        if game.time_limit <= 0:
            t = self.font.render(self.game_over_text, True, self.game_over_color)
            self.center_img(t, self.pos, self.game_over_pos)

    def click(self, game, (x, y)):
        if self.in_button(x, y, self.quit_pos, self.quit_size, self.pos):
            pygame.event.post(pygame.event.Event(QUIT))
        if self.in_button(x, y, self.coffee_break_pos, self.coffee_break_size, self.pos):
            game.paused = not game.paused
        n = self.console_idx(x, y)
        if n is None or not game.running:
            return
        c = game.consoles[n]
        if c.disabled:
            return
        pos = self.console_pos(n)
        if self.in_button(x, y, self.listening_pos, self.listening_size, pos):
            c.listening = not c.listening
        if self.in_button(x, y, self.swat_pos, self.swat_size, pos):
            c.send_swat()

    def bye(self):
        t = self.font.render(self.bye_text, True, self.bye_color)
        self.center_img(t, (self.x, self.y), self.bye_pos)
        img = self.quit_on
        self.center_img(img, self.pos, self.quit_pos)

    def in_button(self, x, y, pos, size, delta=(0, 0)):
        return (abs(x - pos[0] - delta[0]) <= size[0] and
                abs(y - pos[1] - delta[1]) <= size[1])

    def center_img(self, img, pos, delta=(0, 0)):
        self.screen.blit(img, (pos[0] + delta[0] - img.get_width() / 2,
                               pos[1] + delta[1] - img.get_height() / 2))

    def effect(self, game, ef):
        effect = getattr(self, 'effect_' + ef.__class__.__name__, None)
        if effect is not None:
            return effect(game, ef)

    def effect_ScoreEffect(self, game, ef):
        if ef.score > 0:
           color = self.score_positive_color
           shadow = self.score_positive_shadow
        else:
           color = self.score_negative_color
           shadow = self.score_negative_shadow
        n = game.consoles.index(ef.console)
        x, y = self.console_pos(n)
        return ScoreBubble(self.x + x + self.score_pos[0],
                           self.y + y + self.score_pos[1],
                           '%+d' % ef.score, color, self.font,
                           shadow=shadow)


def prototype5():
    # XXX attempting to use 44100 Hz causes 100% CPU
    pygame.mixer.pre_init(22050, -16, 2, 2048)
    pygame.init()
    pygame.display.set_caption('Wiretap')
    pygame.mixer.set_num_channels(32)

    MODE = (1024, 768)
    fullscreen = True
    screen = pygame.display.set_mode((1024, 768), FULLSCREEN)
    screen.fill((0, 0, 0))

    layout = Layout(screen)
    del screen

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

    effects = []

    font = pygame.font.Font(None, 24)

    delta_t = 0.1
    while True:
        # interact
        for event in pygame.event.get():
            if event.type == QUIT or event.type == KEYDOWN and (
                event.key == K_ESCAPE or event.unicode in ('q', 'Q')):
                layout.bye()
                pygame.display.update()
                return
            if event.type == KEYDOWN and (event.unicode in ('f', 'F') or
                event.key in (K_RETURN, K_KP_ENTER) and event.mod & KMOD_ALT):
                fullscreen = not fullscreen
                if fullscreen:
                    layout.screen = pygame.display.set_mode(MODE, FULLSCREEN)
                else:
                    layout.screen = pygame.display.set_mode(MODE, 0)
            if event.type == MOUSEBUTTONUP:
                layout.click(game, event.pos)

        # render audio
        active_channels = sum(c.listening and c.speaking for c in game.consoles) or 1
        active_channels = (active_channels + 1.0) / 2 # slower attenuation
        for n, c in enumerate(game.consoles):
            channel = pygame.mixer.Channel(n)
            if not game.running:
                channel.pause()
                continue
            channel.unpause()

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
        layout.draw(game)
        for e in effects:
            e.draw(layout.screen)
        pygame.display.flip()

        # wait for next frame
        time.sleep(delta_t)

        # game logic
        if game.paused:
            continue
        game.tick(delta_t)
        effects = [e for e in effects if e.tick(delta_t)]
        while game.effects:
            effect = layout.effect(game, game.effects.pop())
            if effect:
                effects.append(effect)


if __name__ == '__main__':
    prototype5()
    print "Quitting!"
    t0 = time.time()
    pygame.quit()
    print "WTF did pygame.quit() do during the last %.1f seconds?" % (time.time() - t0)

