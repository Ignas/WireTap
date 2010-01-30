#!/usr/bin/python
import random
import time

import pygame
from pygame.locals import *


class Voice(object):

    def __init__(self):
        self.benign_phrases = []
        self.suspicious_phrases = []

    @property
    def all_phrases(self):
        return self.benign_phrases + self.suspicious_phrases


class Person(object):

    score = None

    def __init__(self, voice):
        self.voice = voice

    def get_phrase(self):
        pass


class Citizen(Person): # aka obedient citizen

    score = -10

    def get_phrase(self):
        return random.choice(self.voice.benign_phrases)


class Terrorist(Person):

    score = 10

    def get_phrase(self):
        return random.choice(self.voice.all_phrases)


class Household(object):

    def __init__(self, tenants=()):
        self.tenants = list(tenants)
        self.pending_conversation = []
        self.current_phrase = None

    def get_conversation(self, length):
        if self.tenants:
            return [random.choice(self.tenants).get_phrase()
                    for n in range(length)]
        else:
            return []

    def initiate_conversation(self, length):
        self.pending_conversation = self.get_conversation(length)

    def stop_conversation(self):
        self.pending_conversation = []
        self.current_phrase = None


class Console(object): # aka listening station

    def __init__(self, household):
        self.household = household
        self.listening = False
        self.swat_pending = 0

    @property
    def speaking(self):
        return self.household.current_phrase is not None

    def send_swat(self, delay=5):
        self.swat_pending = delay


class Level(object):

    n_consoles = 16
    range_n_persons_per_household = 2, 3
    range_conversation_length = 3, 7
    time_limit = 300 # seconds
    expected_pause_length = 5
    chance_of_terrorism = 0.1

    def __init__(self, n_terrorists, max_simultaneous_conversations=8):
        self.n_terrorists = n_terrorists
        self.max_simultaneous_conversations = max_simultaneous_conversations
        self.passing_score = Terrorist.score * n_terrorists / 2

    def pick_n_persons_per_household(self):
        return random.randint(*self.range_n_persons_per_household)

    def pick_conversation_length(self):
        return random.randint(*self.range_conversation_length)


class Game(object):

    def __init__(self, voices, level=None):
        self.voices = voices
        self.consoles = []
        self.score = 0
        self.time_limit = 0
        self.level = None
        if level:
            self.reset(level)

    def reset(self, level):
        self.consoles = []
        self.score = 0
        self.level = level
        self.time_limit = level.time_limit
        n_terrorists = level.n_terrorists
        for n in range(level.n_consoles):
            if n_terrorists > 0:
                person_maker = Terrorist
                n_terrorists -= 1
            else:
                person_maker = Citizen
            household = self.make_new_household(person_maker)
            self.consoles.append(Console(household))
        random.shuffle(self.consoles)
        self.start_new_conversation()

    def pick_replacement_person(self):
        if random.random() < self.level.chance_of_terrorism:
            return Terrorist
        else:
            return Citizen

    def make_new_household(self, person_maker):
        n_persons = self.level.pick_n_persons_per_household()
        household = Household([person_maker(random.choice(self.voices))
                               for m in range(n_persons)])
        return household

    def count_active_conversations(self):
        return sum(c.speaking for c in self.consoles)

    def should_start_new_conversation(self, delta_t):
        n = self.count_active_conversations()
        m = self.level.max_simultaneous_conversations
        available_slots = m - n
        chance = float(delta_t) / self.level.expected_pause_length
        chance = chance * available_slots / m
        return random.random() <= chance

    def get_silent_households(self):
        return [c.household for c in self.consoles if not c.speaking]

    def tick(self, delta_t):
        self.time_limit -= delta_t
        if self.time_limit < 0:
            self.time_limit = 0
            return # end of level
        if self.should_start_new_conversation(delta_t):
            self.start_new_conversation()
        for c in self.consoles:
            if c.swat_pending:
                c.swat_pending -= delta_t
                if c.swat_pending <= 0:
                    c.swat_pending = False
                    c.household.stop_conversation()
                    for p in c.household.tenants:
                        self.score += p.score
                    c.household = self.make_new_household(self.pick_replacement_person())

    def start_new_conversation(self):
        silent_households = self.get_silent_households()
        if not silent_households:
            return
        household = random.choice(silent_households)
        length = self.level.pick_conversation_length()
        household.initiate_conversation(length)



def prototype5():
    # XXX attempting to use 44100 Hz causes weeeird problems and 100% CPU
    pygame.mixer.pre_init(44100, -16, 2, 2048)
    pygame.init()
    pygame.display.set_caption('Wiretap')
    pygame.mixer.set_num_channels(32)
    screen = pygame.display.set_mode((1024, 700), 0)

    v1 = Voice()
    v1.benign_phrases = map(pygame.mixer.Sound,
                            ['1_1.wav', '1_2.wav', '1_3.wav'])
    v1.suspicious_phrases = map(pygame.mixer.Sound,
                                ['1_deception.wav', '1_fire.wav',
                                 '1_wire.wav', '1_wire.wav'])
    voices = [v1]
    level1 = Level(3)
    game = Game(voices, level1)

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

        # audio
        active_channels = sum(c.listening and c.speaking for c in game.consoles) or 1
        for n, c in enumerate(game.consoles):
            channel = pygame.mixer.Channel(n)
            if c.listening:
                channel.set_volume(1.0 / active_channels)
            else:
                channel.set_volume(0.0)
            h = c.household
            if h.pending_conversation and channel.get_queue() is None:
                h.current_phrase = h.pending_conversation.pop(0)
                channel.queue(h.current_phrase)
            elif h.current_phrase is not None and not channel.get_busy():
                h.current_phrase = None
            elif h.current_phrase is None and channel.get_busy():
                channel.stop()
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
            else:
                color = (175, 23, 34)
                s = 'SEND SWAT'
            t = font.render(s, True, color)
            screen.blit(t, (x + 100 - t.get_width() / 2, y + 70))

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

