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


COINMARKETCAP_API_URL_BASE = 'https://api.coinmarketcap.com/v1'
COINMARKETCAP_API_TICKER_URL = COINMARKETCAP_API_URL_BASE + '/ticker'
COINMARKETCAP_API_COIN_URL_FMT = COINMARKETCAP_API_TICKER_URL + '/{coin}'


class Call(CallBase, GetLoggerMixin):
    __tablename__ = 'calls'
    __loggername__ = f'{__name__}.Call'

    id = Column(Integer, primary_key=True)
    coin_id = Column(Integer, ForeignKey('coins.id'))
    channel_id = Column(Text, index=True)
    author_id = Column(Text, index=True)
    start_price_btc = Column(Float)
    start_price_usd = Column(Float)
    final_price_btc = Column(Float)
    final_price_usd = Column(Float)
    percent_change_btc = Column(Float)
    percent_change_usd = Column(Float)
    closed = Column(Integer, server_default=text("'0'"), index=True)
    timestamp_made = Column(DateTime, default=datetime.utcnow)
    timestamp_closed = Column(DateTime)

    coin = relationship('Coin', foreign_keys=[coin_id], lazy='joined')

    @classmethod
    def make(cls, session, coin):
        logger = cls._logger('make_quick_call')
        logger.debug(coin.name)

        price_btc, price_usd = coin.get_cmc_price()
        call = cls(
            start_price_btc=price_btc,
            start_price_usd=price_usd
        )
        call.coin = coin
        session.add(call)

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
            embed = discord.Embed(title='No open calls')

        return embed

    @classmethod
    def get_by_coin(cls, session, coin):
        return session.query(cls) \
                .filter(cls.coin_id == coin.id) \
                .filter(cls.closed == 0) \
                .first()

    def get_embed(self, made=False):
        if made:
            embed = discord.Embed(title=f'Call made on {self.coin.name} ({self.coin.symbol})')
            embed.add_field(name='Price (BTC)',
                    value=f'{self.start_price_btc:8.8f} BTC')
            #embed.add_field(name='Price (USD)',
                    #value=f'{self.start_price_usd} USD')
        else:
            embed = discord.Embed(title=f'Call on {self.coin.name} ({self.coin.symbol})')
            embed.add_field(name='Call price (BTC)',
                    value=f'{self.start_price_btc:8.8f} BTC')
            #embed.add_field(name='Call price (USD)',
                    #value=f'{self.start_price_usd} USD')

            # show current prices and percent change
            current_price_btc, current_price_usd = self.coin.get_cmc_price()
            percent_change_btc = get_percent_change(self.start_price_btc, current_price_btc)
            percent_change_usd = get_percent_change(self.start_price_usd, current_price_usd)
            embed.add_field(name='Current price (BTC)',
                    value=f'{current_price_btc:8.8f} BTC')
            embed.add_field(name='Percent change', value=f'{percent_change_btc:.2f} %')
            #embed.add_field(name='Current price (USD)',
                    #value=f'{current_price_usd} USD', inline=True)

        return embed

    def close(self, session):
        self.closed = 1

        self.final_price_btc, self.final_price_usd = self.coin.get_cmc_price()
        self.percent_change_btc = get_percent_change(self.start_price_btc, self.final_price_btc)
        self.percent_change_usd = get_percent_change(self.start_price_usd, self.final_price_usd)

    def get_close_embed(self, session):
        self.close(session)

        embed = discord.Embed(title=f'Call closed on {self.coin.name} ({self.coin.symbol})')
        embed.add_field(name='Call price (BTC)', value=f'{self.start_price_btc:8.8f}')
        embed.add_field(name='Final price (BTC)', value=f'{self.final_price_btc:8.8f}')
        embed.add_field(name='Total percent change (BTC)', value=f'{self.percent_change_btc:.2f} %')

        return embed


class Coin(CallBase, GetLoggerMixin):
    __tablename__ = 'coins'
    __loggername__ = f'{__name__}.Coin'

    id = Column(Integer, primary_key=True)
    name = Column(Text, index=True)
    symbol = Column(Text, index=True)
    cmc_id = Column(Text)

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
        cmc_api_url = COINMARKETCAP_API_COIN_URL_FMT.format(coin=coin_name)
        api_response = fetch_url(cmc_api_url)
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

    def get_cmc_price(self):
        logger = self._logger('get_prices')
        logger.debug(self.name)

        cmc_url = COINMARKETCAP_API_COIN_URL_FMT.format(coin=self.cmc_id)
        api_response = fetch_url(cmc_url)
        if not api_response:
            return
        ticker = api_response.json()[0]

        # warn if the price is set to NULL
        try:
            price_btc = float(ticker['price_btc'])
        except:
            logger.warning(f'{self.name} BTC price is NULL')
            price_btc = None
        try:
            price_usd = float(ticker['price_usd'])
        except:
            logger.warning(f'{self.name} USD price is NULL')
            price_usd = None

        return price_btc, price_usd

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
    def find_one_by_string(self, session, coin_string):
        coin_matches = Coin.find_by_string(session, coin_string)
        if not coin_matches:
            response = f'No coin matches for "{coin_string}".'
        elif len(coin_matches) > 1:
            response = f'Multiple matches for "{coin_string}".'
            response += '\n{}'.format('\n'.join([cm.name for cm in coin_matches]))
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
