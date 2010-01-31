#!/usr/bin/python
# -*- coding: utf-8 -*-
import random
import time
import glob
import sys
import math

import pygame
from pygame.locals import (FULLSCREEN, QUIT, KEYDOWN, MOUSEBUTTONUP,
                           K_ESCAPE, K_RETURN, K_KP_ENTER, K_PAUSE, KMOD_ALT)

# tell py2exe what we use
import pygame.mixer
import pygame.font
import pygame.image
import pygame.mouse
import pygame.event
import pygame.display


DEV_MODE = False
SHOW_FPS = False


class Voice(object):

    male = True

    def __init__(self):
        self.benign_phrases = []
        self.suspicious_phrases = []

    @property
    def all_phrases(self):
        return self.benign_phrases + self.suspicious_phrases


class IntroVoice(object):

    def __init__(self):
        self.first_phrase = None
        self.loop_phrases = []


class SwatVoice(object):

    def __init__(self):
        self.storm_phrases = []
        self.apology_phrases_male = []
        self.apology_phrases_female = []
        self.gloat_phrases = []


class Console(object): # aka listening station

    disabled = False
    resting = False

    def __init__(self):
        self.listening = False
        self.active = False
        self.swat_engaged = False
        self.personality = NOBODY
        self.first_phrase = True

    @property
    def speaking(self):
        return self.active or self.swat_engaged

    def get_next_phrase(self):
        if self.first_phrase:
            self.first_phrase = False
            return self.personality.get_first_phrase(self.voice)
        else:
            return self.personality.get_next_phrase(self.voice)

    def move_out(self):
        self.listening = False
        self.active = False
        self.swat_engaged = False
        self.personality = NOBODY
        self.first_phrase = True

    def toggle_listening(self):
        self.listening = not self.listening


class Personality(object):

    next_level_on_capture = False
    score = 0
    good_guys_detained = 0
    bad_guys_caught = 0
    apologize = False
    gloat = False

    def pick_voice(self, voices, intro_voice):
        return random.choice(voices)

    def get_next_phrase(self, voice):
        return None

    def get_first_phrase(self, voice):
        return self.get_next_phrase(voice)


class BadGuy(Personality):

    next_level_on_capture = True

    score = 1
    bad_guys_caught = 1
    gloat = True

    def get_next_phrase(self, voice):
        return random.choice(voice.all_phrases)


class IntroGuy(BadGuy):

    def pick_voice(self, voices, intro_voice):
        return intro_voice

    def get_next_phrase(self, voice):
        return random.choice(voice.loop_phrases)

    def get_first_phrase(self, voice):
        return voice.first_phrase


class GoodGuy(Personality):

    score = -1
    good_guys_detained = 1
    apologize = True

    def get_next_phrase(self, voice):
        return random.choice(voice.benign_phrases)


class Nobody(Personality):
    pass


NOBODY = Nobody()
BAD_GUY = BadGuy()
GOOD_GUY = GoodGuy()
INTRO_GUY = IntroGuy()


class GameStartedEffect(object):
    pass


class ScoreEffect(object):

    def __init__(self, console, score):
        self.console = console
        self.score = score


class CountdownEffect(object):

    def __init__(self, console, time_left):
        self.console = console
        self.time_left = time_left


class LevelEffect(object):

    def __init__(self, level):
        self.level = level


class PieceOfLogic(object):
    next = None


class Pause(PieceOfLogic):

    def __init__(self, time_left):
        self.time_left = time_left

    def tick(self, delta_t):
        self.time_left -= delta_t
        if self.time_left < 0:
            self.time_left = 0
            return False
        return True


class Countdown(Pause):

    def __init__(self, game, console, time_left):
        self.game = game
        self.console = console
        self.time_left = time_left
        self.first_time = True

    def tick(self, delta_t):
        if self.first_time:
            self.game.effects.append(CountdownEffect(self.console, self.time_left))
            self.first_time = False
        return Pause.tick(self, delta_t)


class PlaySound(PieceOfLogic):

    def __init__(self, chan, console, sound):
        self.chan = chan
        self.console = console
        self.sound = sound
        self.playing = False

    def tick(self, delta_t):
        channel = pygame.mixer.Channel(self.chan)
        if not self.playing:
            self.console.active = False
            channel.play(self.sound)
            self.playing = True
            return True
        elif channel.get_busy():
            return True
        else:
            return False


class ScoreLogic(PieceOfLogic):

    def __init__(self, game, console):
        self.game = game
        self.console = console

    def tick(self, delta_t):
        game, console = self.game, self.console
        game.effects.append(ScoreEffect(console, console.personality.score))
        game.score += console.personality.score
        game.good_guys_detained += console.personality.good_guys_detained
        game.bad_guys_caught += console.personality.bad_guys_caught
        return False


class NextLevel(PieceOfLogic):

    def __init__(self, game):
        self.game = game

    def tick(self, delta_t):
        self.game.next_level()
        self.game.effects.append(LevelEffect(self.game.level))
        return False


class ClearConsole(PieceOfLogic):

    def __init__(self, console):
        self.console = console

    def tick(self, delta_t):
        self.console.move_out()
        self.console.resting = True
        return False


class EmptyConsole(PieceOfLogic):

    def __init__(self, console):
        self.console = console

    def tick(self, delta_t):
        self.console.move_out()
        self.console.resting = False
        return False


class Game(object):

    time_limit = 300
    n_consoles = 16
    initially_disabled = [11, 13]

    def __init__(self, voices, swat_voices, intro_voice):
        self.voices = voices
        self.swat_voices = swat_voices
        self.intro_voice = intro_voice
        self.score = 0
        self.level = 0
        self.bad_guys_caught = 0
        self.good_guys_detained = 0
        self.good_guys = []
        self.effects = [GameStartedEffect()]
        self.logic = []
        self.paused = False
        self.quitting = False
        self.consoles = [Console() for n in range(self.n_consoles)]
        for n in self.initially_disabled:
            self.consoles[n].disabled = True

        self.start()

    def start(self):
        self.level = 1
        self.add_guy(INTRO_GUY).listening = True

    def quit(self):
        self.quitting = True

    def toggle_paused(self):
        self.paused = not self.paused

    @property
    def over(self):
        return self.time_limit <= 0

    @property
    def running(self):
        return not self.paused and not self.over and not self.quitting

    @property
    def swat_voices_with_male_apologies(self):
        return ([v for v in self.swat_voices if v.apology_phrases_male]
                or self.swat_voices)

    @property
    def swat_voices_with_female_apologies(self):
        return ([v for v in self.swat_voices if v.apology_phrases_female]
                or self.swat_voices)

    def tick(self, delta_t):
        self.time_limit -= delta_t
        if self.time_limit <= 0:
            self.time_limit = 0
            return # end of level

        next_logic = []
        for piece in self.logic:
            if piece.tick(delta_t):
                next_logic.append(piece)
            elif piece.next:
                next_logic.append(piece.next)
        self.logic = next_logic

    def chain_logic(self, pieces):
        for n, piece in enumerate(pieces[1:]):
            pieces[n].next = piece
        self.logic += pieces[:1]

    def get_empty_consoles(self):
        return [c for c in self.consoles if not c.speaking and not c.disabled and not c.resting]

    def add_guy(self, personality):
        empty_consoles = self.get_empty_consoles()
        if not empty_consoles:
            return
        console = random.choice(empty_consoles)
        console.personality = personality
        console.active = True
        console.voice = personality.pick_voice(self.voices, self.intro_voice)
        return console

    def add_bad_guy(self):
        self.add_guy(BAD_GUY)

    def add_good_guy(self):
        self.good_guys.append(self.add_guy(GOOD_GUY))

    def move_good_guy(self):
        console = self.good_guys.pop(0)
        if console.swat_engaged:
            return
        console.move_out()
        self.add_good_guy()

    def send_swat(self, console):
        if not console.active:
            return
        console.listening = True
        if not console.swat_engaged:
            console.swat_engaged = True
            if console.personality.gloat:
                voice = random.choice(self.swat_voices)
                outcome_phrases = voice.gloat_phrases
            elif console.personality.apologize:
                if console.voice.male:
                    voice = random.choice(self.swat_voices_with_male_apologies)
                    outcome_phrases = voice.apology_phrases_male
                else:
                    voice = random.choice(self.swat_voices_with_female_apologies)
                    outcome_phrases = voice.apology_phrases_female
            else:
                voice = random.choice(self.swat_voices)
                outcome_phrases = []
            n = self.consoles.index(console)
            logic = [
                Countdown(self, console, 3),
                PlaySound(n, console, random.choice(voice.storm_phrases)),
                Pause(1.0),
                ScoreLogic(self, console),
            ]
            if outcome_phrases:
                logic.append(
                    PlaySound(n, console, random.choice(outcome_phrases)))
            logic += [
                ClearConsole(console),
            ]
            if console.personality.next_level_on_capture:
                logic.append(NextLevel(self))
            logic += [
                Pause(3.0),
                EmptyConsole(console),
            ]
            self.chain_logic(logic)

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

    def __init__(self, x, y, text, color, font, time=3, dx=0, dy=-10, shadow=None, shadow_offset=1):
        self.x = x
        self.y = y
        self.dx = dx
        self.dy = dy
        self.text = text
        self.color = color
        self.font = font
        self.surface = font.render(text, True, color)
        self.shadow = shadow
        self.shadow_offset = shadow_offset
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
                screen.blit(self.shadow_surface,
                            (int(self.x) + self.shadow_offset,
                             int(self.y) + self.shadow_offset))
            screen.blit(self.surface, (int(self.x), int(self.y)))


class CountdownBubble(ScoreBubble):

    def __init__(self, x, y, color, font, time=3, dx=0, dy=0, shadow=None):
        ScoreBubble.__init__(self, x, y, "", color, font, time, dx, dy, shadow)

    def draw(self, screen):
        if self.time_left <= 0:
            return
        text = "%d..." % math.ceil(self.time_left)
        if text != self.text:
            self.text = text
            self.set_alpha(1.0) # re-render
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
    swat_inactive_src = "graphics/Send_swat_inactive.png"

    score_pos = 155, 90
    score_positive_color = (20, 200, 20)
    score_positive_shadow = (0, 20, 0)
    score_negative_color = (200, 20, 20)
    score_negative_shadow = (20, 0, 0)

    countdown_pos = score_pos
    countdown_color = (200, 200, 200)
    countdown_shadow = (0, 0, 0)

    coffee_break_pos = 132, 651
    coffee_break_size = 128, 64
    coffee_break_off_src = "graphics/Break.png"
    coffee_break_on_src = "graphics/Break_pressed.png"

    quit_pos = 888, 651
    quit_size = 128, 64
    quit_off_src = "graphics/Quit.png"
    quit_on_src = "graphics/Quit_pressed.png"

    game_over_pos = 512, 250
    game_over_color = (254, 232, 123)
    game_over_text = 'Game Over'

    bye_pos = 512, 340
    bye_color = (254, 232, 123)
    bye_text = 'Bye!'

    paused_pos = 512, 430
    paused_color = (254, 232, 123)
    paused_text = 'Enjoy your coffee!'

    level_pos = 512, 200
    level_color = (20, 200, 20)
    level_shadow = (0, 0, 0)

    cursor_normal_src = "graphics/Cursor.png"
    cursor_normal_hotspot = (9, 2)
    cursor_button_src = "graphics/Cursor_hot.png"
    cursor_button_hotspot = (9, 2)

    font_src = 'fonts/Sniglet.ttf'
    font_size = 24
    big_font_src = 'fonts/Sniglet.ttf'
    big_font_size = 80

    time_left_pos = 420, 666
    time_left_color = (255, 255, 255)

    bad_guys_pos = 733, 658
    bad_guys_color = (25, 255, 25)

    victims_pos = 733, 701
    victims_color = (255, 25, 25)

    use_custom_cursor = False
    fullscreen = True
    mode = size

    def __init__(self):
        self.sceeen = None
        self.background = pygame.image.load(self.background_src)
        self.speaking_inactive = pygame.image.load(self.speaking_inactive_src)
        self.speaking_active = pygame.image.load(self.speaking_active_src)
        self.speaking_red = pygame.image.load(self.speaking_red_src)
        self.listening_on = pygame.image.load(self.listening_on_src)
        self.listening_off = pygame.image.load(self.listening_off_src)
        self.swat_on = pygame.image.load(self.swat_on_src)
        self.swat_off = pygame.image.load(self.swat_off_src)
        self.swat_inactive = pygame.image.load(self.swat_inactive_src)
        self.coffee_break_on = pygame.image.load(self.coffee_break_on_src)
        self.coffee_break_off = pygame.image.load(self.coffee_break_off_src)
        self.quit_on = pygame.image.load(self.quit_on_src)
        self.quit_off = pygame.image.load(self.quit_off_src)
        self.font = pygame.font.Font(self.font_src, self.font_size)
        self.big_font = pygame.font.Font(self. big_font_src, self.big_font_size)
        self.cursor_normal = (pygame.image.load(self.cursor_normal_src),) + self.cursor_normal_hotspot
        self.cursor_button = (pygame.image.load(self.cursor_button_src),) + self.cursor_button_hotspot
        self.cursor = self.cursor_normal
        self.last_mouse_pos = pygame.mouse.get_pos()

    def set_mode(self):
        if self.fullscreen:
            self.screen = pygame.display.set_mode(self.mode, FULLSCREEN)
        else:
            self.screen = pygame.display.set_mode(self.mode, 0)
        self.x = (self.screen.get_width() - self.size[0]) / 2
        self.y = (self.screen.get_height() - self.size[1]) / 2
        self.pos = (self.x, self.y)

    def toggle_fullscreen(self):
        self.fullscreen = not self.fullscreen
        self.set_mode()

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

    def draw(self, game, effects):
        screen = self.screen
        if self.mode != self.size:
            screen.fill((0, 0, 0))
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
            elif c.active:
                img = self.swat_off
            else:
                img = self.swat_inactive
            self.center_img(img, pos, self.swat_pos)

        if not game.paused or game.quitting:
            self.center_img(self.coffee_break_off, self.pos,
                            self.coffee_break_pos)

        self.score_text(game.bad_guys_caught, self.bad_guys_color,
                        self.pos, self.bad_guys_pos)
        self.score_text(game.good_guys_detained, self.victims_color,
                        self.pos, self.victims_pos)
        self.score_text('%d:%02d' % divmod(game.time_limit, 60),
                        self.time_left_color,
                        self.pos, self.time_left_pos)

        for e in effects:
            e.draw(self.screen)

        if not game.running:
            self.fadeout((0, 0), self.size)

        if game.over:
            self.center_text(self.game_over_text, self.game_over_color,
                             self.pos, self.game_over_pos)
        if game.paused:
            self.center_text(self.paused_text, self.paused_color,
                             self.pos, self.paused_pos)
            if not game.quitting:
                self.center_img(self.coffee_break_on, self.pos,
                                self.coffee_break_pos)

        if game.quitting:
            self.center_text(self.bye_text, self.bye_color, self.pos, self.bye_pos)
            self.center_img(self.quit_on, self.pos, self.quit_pos)
        else:
            self.center_img(self.quit_off, self.pos, self.quit_pos)

        if self.use_custom_cursor:
            pygame.mouse.set_visible(False)
            self.last_mouse_pos = pygame.mouse.get_pos()
            self.draw_cursor()

    def bye(self):
        self.center_text(self.bye_text, self.bye_color, self.pos, self.bye_pos)
        self.center_img(self.quit_on, self.pos, self.quit_pos)

        if self.use_custom_cursor:
            self.draw_cursor()

    def fadeout(self, pos, size):
        surf = pygame.Surface(size).convert_alpha()
        surf.fill((0, 0, 0, 127))
        self.screen.blit(surf, pos)

    def draw_cursor(self):
        x, y = self.last_mouse_pos
        self.screen.blit(self.cursor[0], (x - self.cursor[1], y - self.cursor[2]))

    def action(self, game, (x, y)):
        if self.in_button(x, y, self.quit_pos, self.quit_size, self.pos, self.quit_off):
            return lambda: pygame.event.post(pygame.event.Event(QUIT))
        if game.over or game.quitting:
            return
        if self.in_button(x, y, self.coffee_break_pos, self.coffee_break_size, self.pos, self.coffee_break_off):
            return game.toggle_paused
        n = self.console_idx(x, y)
        if n is None or not game.running:
            return
        c = game.consoles[n]
        if c.disabled:
            return
        pos = self.console_pos(n)
        if self.in_button(x, y, self.listening_pos, self.listening_size, pos, self.listening_off):
            return lambda: c.toggle_listening()
        if self.in_button(x, y, self.swat_pos, self.swat_size, pos, self.swat_off):
            return lambda: game.send_swat(c)

    def click(self, game, (x, y)):
        action = self.action(game, (x, y))
        if action:
            action()

    def hover(self, game, (x, y)):
        action = self.action(game, (x, y))
        if action:
            self.cursor = self.cursor_button
        else:
            self.cursor = self.cursor_normal

    def in_button(self, x, y, pos, size, delta=(0, 0), button=None):
        if (abs(x - pos[0] - delta[0]) < size[0] / 2 and
            abs(y - pos[1] - delta[1]) < size[1] / 2):
            dx = x - pos[0] - delta[0] + size[0] / 2
            dy = y - pos[1] - delta[1] + size[1] / 2
            if button:
                color = button.get_at((dx, dy))
                if len(color) > 3 and color[3] < 128:
                    return False # alpha-transparent
            return True
        else:
            return False

    def center_img(self, img, pos, delta=(0, 0)):
        self.screen.blit(img, (pos[0] + delta[0] - img.get_width() / 2,
                               pos[1] + delta[1] - img.get_height() / 2))

    def center_text(self, text, color, pos, delta=(0, 0), shadow=(0, 0, 0)):
        text = unicode(text)
        if shadow:
            img = self.big_font.render(text, True, shadow)
            self.center_img(img, (pos[0] + 3, pos[1] + 3), delta)
        img = self.big_font.render(text, True, color)
        self.center_img(img, pos, delta)

    def score_text(self, text, color, pos, delta=(0, 0)):
        img = self.font.render(unicode(text), True, color)
        self.screen.blit(img, (pos[0] + delta[0] - img.get_width(),
                               pos[1] + delta[1] - img.get_height()))

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

    def effect_CountdownEffect(self, game, ef):
        color = self.countdown_color
        shadow = self.countdown_shadow
        n = game.consoles.index(ef.console)
        x, y = self.console_pos(n)
        return CountdownBubble(self.x + x + self.countdown_pos[0],
                               self.y + y + self.countdown_pos[1],
                               color, self.font, time=ef.time_left,
                               shadow=shadow)

    def effect_LevelEffect(self, game, ef):
        color = self.level_color
        shadow = self.level_shadow
        x, y = self.level_pos
        return ScoreBubble(self.x + x,
                           self.y + y,
                           'Level %d' % ef.level, color, self.big_font,
                           shadow=shadow, shadow_offset=3)

    def effect_GameStartedEffect(self, game, ef):
        color = self.level_color
        shadow = self.level_shadow
        x, y = self.level_pos
        return ScoreBubble(self.x + x,
                           self.y + y,
                           'Wiretap', color, self.big_font,
                           shadow=shadow, shadow_offset=3)


def main():
    # XXX attempting to use 44100 Hz causes 100% CPU
    pygame.mixer.pre_init(22050, -16, 2, 2048)
    pygame.init()
    pygame.display.set_caption('Wiretap')
    pygame.mixer.set_num_channels(32)

    layout = Layout()
    if '-w' in sys.argv:
        layout.fullscreen = False
    if '-d' in sys.argv:
        global DEV_MODE
        DEV_MODE = True
    if '-f' in sys.argv:
        global SHOW_FPS
        SHOW_FPS = True

    layout.set_mode()

    voices = []
    n = 1
    while True:
        v = Voice()
        good = glob.glob('sounds/voices/p%d_good*.ogg' % n)
        bad = glob.glob('sounds/voices/p%d_bad*.ogg' % n)
        if not good or not bad:
            break
        v.benign_phrases = map(pygame.mixer.Sound, good)
        v.suspicious_phrases = map(pygame.mixer.Sound, bad)
        v.male = good[0].endswith('_m.ogg')
        for fn in good + bad:
            if fn.endswith('_f.ogg'):
                if v.male:
                  print "INCONSISTENT VOICE: %s and %s" % (good[0], fn)
            elif fn.endswith('_m.ogg'):
                if not v.male:
                  print "INCONSISTENT VOICE: %s and %s" % (good[0], fn)
            else:
              print "UNKNOWN GENDER: %s" % fn
        n += 1
        voices.append(v)

    swat_voices = []
    n = 1
    while True:
        v = SwatVoice()
        storm = glob.glob('sounds/swat/c%d_gogogo*.ogg' % n)
        gloat = glob.glob('sounds/swat/c%d_terror*.ogg' % n)
        apologize_to_male = glob.glob('sounds/swat/c%d_msorry*.ogg' % n)
        apologize_to_female = glob.glob('sounds/swat/c%d_wsorry*.ogg' % n)
        if not storm:
            break
        v.storm_phrases = map(pygame.mixer.Sound, storm)
        v.gloat_phrases = map(pygame.mixer.Sound, gloat)
        v.apology_phrases_male = map(pygame.mixer.Sound, apologize_to_male)
        v.apology_phrases_female = map(pygame.mixer.Sound, apologize_to_female)
        n += 1
        swat_voices.append(v)

    intro_voice = IntroVoice()
    intro_voice.first_phrase = pygame.mixer.Sound('sounds/tutorial.ogg')
    intro_voice.loop_phrases = [pygame.mixer.Sound('sounds/reminder.ogg')]

    nice_coffee = pygame.mixer.Sound('sounds/actions/nice_coffee.ogg')
    back_to_work = pygame.mixer.Sound('sounds/actions/back_to_work.ogg')
    going_home = pygame.mixer.Sound('sounds/actions/I_ll_go_home.ogg')

    game = Game(voices, swat_voices, intro_voice)

    coffee_break_channel = pygame.mixer.Channel(len(game.consoles))
    sfx_channel = pygame.mixer.Channel(len(game.consoles) + 1)

    effects = []

    layout.draw(game, effects)
    pygame.display.flip()

    if layout.use_custom_cursor:
        delta_t = 1.0 / 60 # fps; aim high!
    else:
        delta_t = 1.0 / 10 # fps; we don't need much

    last_t = time.time()
    last_paused = game.paused
    last_quitting = False

    while True:
        # interact
        for event in pygame.event.get():
            if event.type == QUIT or event.type == KEYDOWN and (
                event.key == K_ESCAPE or event.unicode in ('q', 'Q')):
                if game.quitting:
                    return
                else:
                    game.quit()
            if event.type == KEYDOWN and (event.unicode in ('p', 'P') or
                event.key == K_PAUSE):
                if not game.over and not game.quitting:
                    game.toggle_paused()
            if event.type == KEYDOWN and (event.unicode in ('f', 'F') or
                event.key in (K_RETURN, K_KP_ENTER) and event.mod & KMOD_ALT):
                layout.toggle_fullscreen()
            if event.type == MOUSEBUTTONUP:
                layout.click(game, event.pos)
            if DEV_MODE:
                if event.type == KEYDOWN and event.unicode in ('d', 'D'):
                    if layout.fullscreen:
                        layout.toggle_fullscreen()
                    import pdb; pdb.set_trace()
                if event.type == KEYDOWN and event.unicode in ('g', 'G'):
                    game.add_good_guy()
                if event.type == KEYDOWN and event.unicode in ('b', 'B'):
                    game.add_bad_guy()
                if event.type == KEYDOWN and event.unicode in ('t', 'T'):
                    game.time_limit = 5
        layout.hover(game, pygame.mouse.get_pos())

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

        if last_paused != game.paused:
            last_paused = game.paused
            if game.paused:
                coffee_break_channel.play(nice_coffee)
            else:
                coffee_break_channel.play(back_to_work)

        if last_quitting != game.quitting:
            last_quitting = game.quitting
            if game.quitting:
                coffee_break_channel.play(going_home)

        if game.quitting and not coffee_break_channel.get_busy():
            return # going_home finished playing

        # draw
        layout.draw(game, effects)
        pygame.display.flip()

        # wait for next frame
        next_t = last_t + delta_t
        dt = max(0.01, next_t - time.time())
        time.sleep(dt)

        # game logic
        if not game.running:
            last_t = time.time()
            continue
        dt = time.time() - last_t
        if SHOW_FPS:
            print round(dt, 3), '\t', round(1.0 / dt, 1), 'fps'
        game.tick(dt)
        effects = [e for e in effects if e.tick(dt)]
        while game.effects:
            effect = layout.effect(game, game.effects.pop())
            if effect:
                effects.append(effect)
        last_t = time.time()


if __name__ == '__main__':
    main()
    t0 = time.time()
    pygame.quit()
    if DEV_MODE:
        print "WTF did pygame.quit() do during the last %.1f seconds?" % (time.time() - t0)

