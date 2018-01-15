import json
import logging
from pprint import pprint

import aiohttp
from bs4 import BeautifulSoup
import discord
import requests


GREEN_ARROW_UP = '<:arup:361777443343958017>'
RED_ARROW_DOWN = '<:ardn:361785982921736192>'


def get_arrow(percentage):
    if percentage > 0.0:
        return GREEN_ARROW_UP
    elif percentage == 0.0:
        return ''
    else:
        return RED_ARROW_DOWN


def get_user(ctx, id_):
    return discord.utils.get(ctx.message.server.members, id=id_)


def fetch_url(url, params=None):
    logger = logging.getLogger(f'{__name__}.fetch_url')

    params = params or {}
    try:
        response = requests.get(url, params=params)
    except Exception as e:
        logger.error(f'error fetching url ({url}): {e}', exc_info=True)
        return False

    if response.status_code != 200:
        logger.error(f'non 200 response for url ({url}): {response}')
        return False

    return response


def percent_change(start_value, end_value):
    return ((end_value - start_value) / start_value) * 100


class GetLoggerMixin:
    ''' Adds a `_get_logger()` classmethod that returns the correctly
    named logger. The child class must have a `__loggername__` class variable.
    '''

    @classmethod
    def _logger(cls, name=''):
        logger_name = cls.__loggername__
        if name:
            logger_name += f'.{name}'

        return logging.getLogger(logger_name)


def pp(o):
    try:
        print(json.dumps(o, indent=2, sort_keys=True))
    except:
        pprint(o)
