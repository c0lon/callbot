from collections import namedtuple
from datetime import datetime
from queue import Queue
import threading as tr

import discord
from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    Table,
    Text,
    func,
    or_,
    text,
    )
from sqlalchemy.orm import relationship


from .meta import CallBase
from ..utils import (
    GetLoggerMixin,
    fetch_url,
    get_percent_change,
    pp,
    )

COINMARKETCAP_URL_BASE = 'https://coinmarketcap.com'
COINMARKETCAP_COIN_URL_FMT = COINMARKETCAP_URL_BASE + '/currencies/{cmc_id}'
COINMARKETCAP_COIN_MARKETS_URL_FMT = COINMARKETCAP_COIN_URL_FMT + '/#markets'
COINMARKETCAP_COIN_IMG_URL_FMT = 'https://files.coinmarketcap.com/static/img/coins/32x32/{cmc_id}.png'

COINMARKETCAP_API_URL_BASE = 'https://api.coinmarketcap.com/v1'
COINMARKETCAP_API_TICKER_URL = COINMARKETCAP_API_URL_BASE + '/ticker'
COINMARKETCAP_API_COIN_URL_FMT = COINMARKETCAP_API_TICKER_URL + '/{cmc_id}'


class Call(CallBase, GetLoggerMixin):
    """ Model of a call made on a coin.
    """

    __tablename__ = 'calls'
    __loggername__ = f'{__name__}.Call'

    id = Column(Integer, primary_key=True)
    coin_id = Column(Integer, ForeignKey('coins.id'))
    channel_id = Column(Text, index=True)
    author_id = Column(Text, index=True)
    start_price_btc = Column(Float)
    final_price_btc = Column(Float)
    total_percent_change_btc = Column(Float)
    closed = Column(Integer, server_default=text("'0'"), index=True)
    timestamp_made = Column(DateTime, default=datetime.utcnow)
    timestamp_closed = Column(DateTime)

    coin = relationship('Coin', foreign_keys=[coin_id], lazy='joined')

    def get_percent_change_btc(self):
        return get_percent_change(self.start_price_btc, self.coin.current_price_btc)
    percent_change_btc = property(get_percent_change_btc)

    @classmethod
    def get_no_open_calls_embed(cls, coin=None):
        if coin:
            embed = discord.Embed(title=f'No open calls on {coin.name}', url=self.coin.cmc_url)
            embed.set_thumbnail(url=coin.cmc_image_url)
        else:
            embed = discord.Embed(title='No open calls')

        return embed

    @classmethod
    def make(cls, session, coin, message):
        logger = cls._logger('make_quick_call')
        logger.debug(coin.name)

        call = cls(
            start_price_btc=coin.current_price_btc,
            channel_id=message.channel.id,
            author_id=message.author.id
        )
        call.coin = coin
        session.add(call)
        session.flush()

        return call

    @classmethod
    def get_all_open(cls, session):
        return session.query(cls) \
                .filter(cls.closed == 0) \
                .all()

    @classmethod
    def get_all_open_embed(cls, session):
        calls = cls.get_all_open(session)
        if calls:
            embed = discord.Embed(title='All open calls')
            for call in calls:
                embed.add_field(name=call.coin.name,
                        value=f'{call.start_price_btc:8.8f} BTC')
        else:
            embed = cls.get_no_open_calls_embed()

        return embed

    @classmethod
    def get_by_coin(cls, session, coin):
        return session.query(cls) \
                .filter(cls.coin_id == coin.id) \
                .filter(cls.closed == 0) \
                .first()

    @classmethod
    def get_last(cls, session):
        return session.query(cls) \
                .filter(cls.closed == 0) \
                .order_by(cls.timestamp_made.desc()) \
                .first()

    @classmethod
    def get_last_embed(cls, session):
        call = cls.get_last(session)
        if call:
            response = call.get_embed()
        else:
            response = cls.get_no_open_calls_embed()

        return response

    @classmethod
    def get_by_coin_embed(cls, session, coin):
        call = cls.get_by_coin(session, coin)
        if call:
            embed = call.get_embed()
        else:
            embed = cls.get_no_open_calls_embed(coin=coin)

        return embed

    def get_embed(self, made=False):
        embed = discord.Embed()
        embed.set_thumbnail(url=self.coin.cmc_image_url)

        if made:
            embed.title=f'Call made on {self.coin.name} ({self.coin.symbol})'
            embed.url=self.coin.cmc_url
            embed.add_field(name='Price (BTC)',
                    value=f'{self.start_price_btc:8.8f} BTC', inline=False)
        else:
            embed.title=f'Call on {self.coin.name} ({self.coin.symbol})'
            embed.url=self.coin.cmc_url
            embed.add_field(name='Call Price (BTC)',
                    value=f'{self.start_price_btc:8.8f} BTC')

            # show current prices and percent change
            embed.add_field(name='Current Price (BTC)',
                    value=f'{self.coin.current_price_btc:8.8f} BTC', inline=False)
            embed.add_field(name='Percent change',
                    value=f'{self.percent_change_btc:.2f} %', inline=False)
            embed.add_field(name='Call Made',
                    value=self.timestamp_made.strftime('%Y-%m-%d %H:%M UTC'), inline=False)

        return embed

    def close(self, session):
        self.closed = 1
        self.final_price_btc = self.coin.current_price_btc
        self.total_percent_change_btc = self.percent_change_btc

    def close_embed(self, session):
        self.close(session)

        embed = discord.Embed(title=f'Call closed on {self.coin.name} ({self.coin.symbol})',
                url=self.coin.cmc_url)
        embed.set_thumbnail(url=self.coin.cmc_image_url)
        embed.add_field(name='Call price (BTC)',
                value=f'{self.start_price_btc:8.8f}')
        embed.add_field(name='Final price (BTC)',
                value=f'{self.final_price_btc:8.8f}', inline=False)
        embed.add_field(name='Total percent change (BTC)',
                value=f'{self.percent_change_btc:.2f} %', inline=False)

        return embed

    @classmethod
    def close_by_coin_embed(cls, session, message, coin):
        call = cls.get_by_coin(session, coin)
        if not call:
            embed = cls.get_no_open_calls_embed(coin=coin)
        elif call.author_id != message.author.id:
            embed = self.get_close_not_allowed_embed(message)
        else:
            embed = call.close_embed(session)

        return embed

    def get_closed_not_allowed_embed(self, message):
        caller = discord.utils.find(message.server.members, id=self.author_id)
        title = f'Call on {self.coin.name} can only be closed by {caller.name}'
        embed = discord.Embed(title=title, url=self.coin.cmc_url)
        embed.set_thumbnail(url=self.coin.cmc_image_url)

        return embed


class Coin(CallBase, GetLoggerMixin):
    """ Model of a Coin on Coinmarketcap.
    """

    __tablename__ = 'coins'
    __loggername__ = f'{__name__}.Coin'

    id = Column(Integer, primary_key=True)
    name = Column(Text, index=True)
    symbol = Column(Text, index=True)
    cmc_id = Column(Text)

    def get_cmc_url(self):
        return COINMARKETCAP_COIN_MARKETS_URL_FMT.format(cmc_id=self.cmc_id)
    cmc_url = property(get_cmc_url)

    def get_cmc_api_url(self):
        return COINMARKETCAP_API_COIN_URL_FMT.format(cmc_id=self.cmc_id)
    cmc_api_url = property(get_cmc_api_url)

    def get_cmc_image_url(self):
        return COINMARKETCAP_COIN_IMG_URL_FMT.format(cmc_id=self.cmc_id)
    cmc_image_url = property(get_cmc_image_url)

    @classmethod
    def get_by_name(cls, session, coin_name):
        return session.query(cls) \
                .filter(cls.name == coin_name) \
                .first()

    @classmethod
    def get_by_symbol(cls, session, coin_symbol):
        return session.query(cls) \
                .filter(cls.symbol == coin_symbol) \
                .first()

    @classmethod
    def add_from_name(cls, session, coin_name):
        api_response = fetch_url(self.cmc_api_url)
        if not api_response:
            return

        api_response = api_response.json()
        if not api_response:
            return

        ticker = api_response[0]
        coin = cls.add_from_ticker(session, ticker)

        return coin

    @classmethod
    def add_from_ticker(cls, session, ticker):
        coin = cls(
            name=ticker['name'],
            symbol=ticker['symbol'],
            cmc_id=ticker['id'],
        )
        cls._logger('add_from_ticker').info(f'{coin.name} ({coin.symbol})')

        session.add(coin)
        session.flush()

        return coin

    @classmethod
    def get_or_add(cls, session, coin_name):
        coin = cls.get_by_name(session, coin_name)
        if not coin:
            coin = cls.add_from_name(session, coin_name)

        return coin

    def get_current_price_btc(self):
        logger = self._logger('get_prices')
        logger.debug(self.name)

        api_response = fetch_url(self.cmc_api_url)
        if not api_response:
            return
        ticker = api_response.json()[0]

        # warn if the price is set to NULL
        try:
            price_btc = float(ticker['price_btc'])
        except:
            logger.warning(f'{self.name} BTC price is NULL')
            price_btc = None

        return price_btc

    current_price_btc = property(get_current_price_btc)

    @classmethod
    def find_by_string(cls, session, coin_string):
        """ Search for coins given a string.

        Symbols are used more often, so search by symbol first. If there are no
        symbol matches, search by name and coinmarketcap ID.
        """
        logger = cls._logger('find_by_string')
        logger.debug(coin_string)

        # search for exact symbol matches first
        coin_symbol_matches = session.query(cls) \
                .filter(func.lower(cls.symbol) == func.lower(coin_string)) \
                .all()
        if coin_symbol_matches:
            return coin_symbol_matches

        # search for symbol with trailing wildcard
        coin_symbol_matches = session.query(cls) \
                .filter(cls.symbol.ilike(f'{coin_string}%')) \
                .all()
        if coin_symbol_matches:
            return coin_symbol_matches

        # default to searching by name and coinmarketcap ID
        return session.query(cls).filter(or_(
            cls.name.ilike(f'%{coin_string}%'),
            cls.cmc_id.ilike(f'%{coin_string}%')
        )).all()

    @classmethod
    def get_not_found_embed(cls, coin_string):
        return discord.Embed(title=f'No coins found for "{coin_string}".')

    @classmethod
    def get_multiple_matches_embed(cls, coin_string, coin_matches):
        embed = discord.Embed(title=f'Multiple coins found for "{coin_string}".')
        coin_matches_string = '\n'.join([f'{cm.name} ({cm.symbol})' for cm in coin_matches])
        embed.add_field(name='Coins', value=coin_matches_string)

        return embed

    @classmethod
    def find_one_by_string(self, session, coin_string):
        coin_matches = Coin.find_by_string(session, coin_string)
        if not coin_matches:
            response = Coin.get_not_found_embed(coin_string)
        elif len(coin_matches) > 1:
            response = Coin.get_multiple_matches_embed(coin_string, coin_matches)
        else:
            response = coin_matches[0]

        return response

    @classmethod
    def load_all_coins(cls, session, count=None):
        api_response = fetch_url(COINMARKETCAP_API_TICKER_URL, params={'limit' : 0})
        if not api_response:
            return
        coin_tickers = api_response.json()
        tickers_by_symbol = {t['symbol']: t for t in coin_tickers}
        if count:
            coin_tickers = coin_tickers[:count]

        for coin_ticker in coin_tickers:
            if not cls.get_by_name(session, coin_ticker['name']):
                coin = cls.add_from_ticker(session, coin_ticker)
