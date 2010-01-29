#!/usr/bin/python
import random

import pygame


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

    def get_conversation(self, length):
        if self.tenants:
            return [random.choice(self.tenants).get_phrase()
                    for n in range(length)]
        else:
            return []


class Console(object): # aka listening station

    def __init__(self, household):
        self.household = household
        self.listening = False


class Level(object):

    n_consoles = 16
    range_n_persons_per_household = 2, 3

    def __init__(self, n_terrorists):
        self.n_terrorists = n_terrorists

    def get_n_persons_per_household(self):
        return random.randint(*self.range_n_persons_per_household)


class Game(object):

    def __init__(self, voices, level=None):
        self.voices = voices
        self.consoles = []
        self.score = 0
        if level:
            self.reset(level)

    def reset(self, level):
        self.consoles = []
        self.score = 0
        n_terrorists = level.n_terrorists
        for n in range(level.n_consoles):
            if n_terrorists > 0:
                person_maker = Terrorist
                n_terrorists -= 1
            else:
                person_maker = Citizen
            n_persons = level.get_n_persons_per_household()
            household = Household([person_maker(random.choice(self.voices))
                                   for m in range(n_persons)])
            self.consoles.append(Console(household))
        random.shuffle(self.consoles)


### prototype #1

def prototype1():
    v = Voice()
    v.benign_phrases = ["Hi!", "Nice weather out there.", "What's up?"]
    v.suspicious_phrases = ["The bomb plans are due tomorrow.",
                            "What if big brother is watching us?"]
    voices = [v]

    granny1 = Citizen(v)
    granny2 = Citizen(v)
    house1 = Household([granny1, granny2])

    crook1 = Terrorist(v)
    crook2 = Terrorist(v)
    house2 = Household([crook1, crook2])

    print '\n'.join(house1.get_conversation(5))
    print
    print '\n'.join(house2.get_conversation(5))


def prototype2():
    v1 = Voice()
    v1.benign_phrases = ["Hi!", "Nice weather out there.", "What's up?"]
    v1.suspicious_phrases = ["The bomb plans are due tomorrow.",
                             "What if big brother is watching us?"]
    v2 = Voice()
    v2.benign_phrases = ["Hello!", "The weather is particularly fine today."]
    v2.suspicious_phrases = ["I have some liquid explosives in my bag."]
    voices = [v1, v2]
    level1 = Level(3)
    game = Game(voices, level1)

    for c in game.consoles:
        print "\n".join(c.household.get_conversation(3))
        print


if __name__ == '__main__':
    prototype2()
