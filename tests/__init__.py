from collections import defaultdict
import math
import random
import string

import yaml

import callbot


CONFIG_URI = 'development.yaml'
SETTINGS, GLOBAL_CONFIG = callbot.configure_app(config_uri=CONFIG_URI)
