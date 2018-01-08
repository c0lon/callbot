from collections import defaultdict
import math
import random
import string

import yaml

import callbot


CONFIG_URI = 'development.yaml'
SETTINGS, GLOBAL_CONFIG = callbot.configure_app(config_uri=CONFIG_URI)


def random_boolean():
    return random.choice([True, False])


def random_string(min_length=8, max_length=16, cant_be=None):
    length = random.randint(min_length, max_length)
    s = ''.join([random.choice(string.hexdigits) for _ in range(length)])
    while s == cant_be:
        s = ''.join([random.choice(string.hexdigits) for _ in range(length)])
    return s


def random_number(min_=0, max_=1000000000, type_=int, cant_be=None):
    n = min_ + random.random() * (max_ - min_)
    while type(n) == cant_be:
        n = min_ + random.random() * (max_ - min_)
    return type_(n)

