import json
import logging
from pprint import pprint

import aiohttp
from bs4 import BeautifulSoup
import discord


COINMARKETCAP_URL_BASE = 'https://coinmarketcap.com'
COINMARKETCAP_COIN_URL_FMT = COINMARKETCAP_URL_BASE + '/currencies/{cmc_id}'
COINMARKETCAP_COIN_MARKETS_URL_FMT = COINMARKETCAP_COIN_URL_FMT + '/#markets'
COINMARKETCAP_COIN_IMG_URL_FMT = 'https://files.coinmarketcap.com/static/img/coins/32x32/{cmc_id}.png'

COINMARKETCAP_API_URL_BASE = 'https://api.coinmarketcap.com/v1'
COINMARKETCAP_API_TICKER_URL = COINMARKETCAP_API_URL_BASE + '/ticker'
COINMARKETCAP_API_COIN_URL_FMT = COINMARKETCAP_API_TICKER_URL + '/{cmc_id}'

TIMESTAMP_FMT = '%Y-%m-%d %H:%M UTC'

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


async def fetch_url(url, params=None):
    logger = logging.getLogger(f'{__name__}.fetch_url')
    logger.debug(url, extra=params)

    params = params or {}
    try:
        response = await aiohttp.get(url, params=params)
    except Exception as e:
        logger.error(f'error fetching url ({url}): {e}', exc_info=True)
        return False

    if response.status != 200:
        logger.error(f'non 200 response for url ({url}): {response}')
        return False

    return response


async def get_cmc_global_ticker():
    response = await fetch_url(COINMARKETCAP_API_TICKER_URL,
            params={'limit' : 0})
    if not response: return {}
    return await response.json()


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
