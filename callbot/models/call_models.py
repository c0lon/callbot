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
    )
from sqlalchemy.orm import relationship


from .meta import CallBase
from ..utils import (
    GetLoggerMixin,
    fetch_url,
    get_soup,
    pp,
    )


COINMARKETCAP_URL_BASE = 'https://coinmarketcap.com'
COINMARKETCAP_COIN_URL_FMT = COINMARKETCAP_URL_BASE + '/currencies/{coin}'

COINMARKETCAP_API_URL_BASE = 'https://api.coinmarketcap.com/v1'
COINMARKETCAP_API_TICKER_URL = COINMARKETCAP_API_URL_BASE + '/ticker'
COINMARKETCAP_API_COIN_URL_FMT = COINMARKETCAP_API_TICKER_URL + '/{coin}'


class CallPrompt:
    def __init__(self, name, prompt, required=False):
        self.name = name
        self.prompt = prompt
        self.required = required

        if self.required:
            self.prompt = f'[Required] {self.prompt}'

    def prompt_for_answer(self):
        value = input(self.prompt).strip()
        while self.required and value == '':
            print('This field is required.')
            value = input(self.prompt).strip()

        return value


class Call(CallBase, GetLoggerMixin):
    __tablename__ = 'calls'
    __loggername__ = f'{__name__}.Call'

    id = Column(Integer, primary_key=True)
    coin_id = Column(Integer, ForeignKey('coins.id'))
    price_at_call_btc = Column(Float)
    price_at_call_usd = Column(Float)
    buy_target = Column(Float)
    sell_target = Column(Float)
    hold_time = Column(Text)
    risk = Column(Text)
    reward = Column(Text)
    stack_percentage = Column(Float)
    writeup_url = Column(Text)
    closed = Column('open', Boolean, default=False)
    timestamp = Column(DateTime, default=datetime.utcnow)

    coin = relationship('Coin', foreign_keys=[coin_id], lazy='joined')

    PROMPTS = [
        CallPrompt('name', 'Coin name: ', required=True),
        CallPrompt('risk', 'Risk: '),
        CallPrompt('reward', 'Reward: '),
    ]

    @classmethod
    def make_quick_call(cls, session, coin):
        logger = cls._logger('make_quick_call')
        logger.debug(coin.name)

        call = cls(
            coin_id=coin.id,
            price_at_call_btc=coin.cmc_price_btc,
            price_at_call_usd=coin.cmc_price_usd
        )
        session.add(call)

        return call

    @classmethod
    def get_all_open_calls(cls, session):
        return session.query(cls) \
                .filter(cls.closed is False) \
                .all()

    def get_embed(self):
        embed = discord.Embed(title=f'Call on {self.name} ({self.symbol})')
        embed.add_field(name='Call price (BTC)', value=self.price_at_call_btc)
        embed.add_field(name='Call price (USD)', value=self.price_at_call_usd)

        return embed


coin_markets = Table('coin_markets', CallBase.metadata,
    Column('coin_id', Integer, ForeignKey('coins.id'), primary_key=True),
    Column('market_id', Integer, ForeignKey('markets.id'), primary_key=True)
)


class Coin(CallBase, GetLoggerMixin):
    __tablename__ = 'coins'
    __loggername__ = f'{__name__}.Coin'

    id = Column(Integer, primary_key=True)
    name = Column(Text, index=True)
    symbol = Column(Text, index=True)
    cmc_id = Column(Text)
    cmc_price_btc = Column(Float)
    cmc_price_usd = Column(Float)

    markets = relationship('Market', secondary=coin_markets, back_populates='coins')
    market_prices = relationship('MarketPrice', primaryjoin='Coin.id == MarketPrice.coin_id')

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
        logger = cls._logger('add_from_ticker')

        try:
            price_btc = float(ticker['price_btc'])
        except:
            logger.warning(f"{ticker['name']}: NULL BTC price")
            price_btc = None
        try:
            price_usd = float(ticker['price_usd'])
        except:
            logger.warning(f"{ticker['name']}: NULL USD price")
            price_usd = None

        coin = cls(
            name=ticker['name'],
            symbol=ticker['symbol'],
            cmc_id=ticker['id'],
            cmc_price_btc=price_btc,
            cmc_price_usd=price_usd
        )

        message = f'{coin.name} ({coin.symbol})'
        if isinstance(price_btc, float):
            message += f': {coin.cmc_price_btc:8.8f} BTC'
        logger.info(message)

        session.add(coin)
        session.flush()

        return coin

    @classmethod
    def get_or_add(cls, session, coin_name):
        coin = cls.get_by_name(session, coin_name)
        if not coin:
            coin = cls.add_from_name(session, coin_name)

        return coin

    def update(self, session, ticker=None):
        logger = self._logger('update')
        logger.debug(self.name)

        if not ticker:
            cmc_url = COINMARKETCAP_API_COIN_URL_FMT.format(coin=self.cmc_id)
            api_response = fetch_url(cmc_url)
            if not api_response:
                return

            ticker = api_response.json()[0]

        # warn if the price is set to NULL
        try:
            price_btc = float(ticker['price_btc'])
        except:
            if self.cmc_price_btc is not None:
                logger.warning(f'{self.name} BTC price set to NULL')
            price_btc = None
        try:
            price_usd = float(ticker['price_usd'])
        except:
            if self.cmc_price_usd is not None:
                logger.warning(f'{self.name} USD price set to NULL')
            price_usd = None

        self.cmc_price_btc = price_btc
        self.cmc_price_usd = price_usd

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
    def load_all_coins(cls, session, count=None):
        api_response = fetch_url(COINMARKETCAP_API_TICKER_URL, params={'limit' : 0})
        if not api_response:
            return
        coin_tickers = api_response.json()
        tickers_by_symbol = {t['symbol']: t for t in coin_tickers}
        if count:
            coin_tickers = coin_tickers[:count]

        for coin_ticker in coin_tickers:
            coin = cls.get_by_name(session, coin_ticker['name'])
            if coin:
                coin.update(session, coin_ticker)
            else:
                coin = cls.add_from_ticker(session, coin_ticker)
            coin.load_markets(session, tickers=tickers_by_symbol)

    def load_markets(self, session, tickers):
        logger = self._logger('load_markets')
        logger.debug(self.name)

        cmc_url = COINMARKETCAP_COIN_URL_FMT.format(coin=self.cmc_id)
        url_response = fetch_url(cmc_url)
        if not url_response:
            return

        soup = get_soup(url_response.text)
        markets_table = soup.find('table', id='markets-table')
        if not markets_table:
            return
        markets_table = markets_table.find('tbody')

        for market_row in markets_table('tr'):
            market_cells = market_row('td')

            market_name_link = market_cells[1].find('a')
            market_name = market_name_link.text
            market_url = market_name_link.href
            market = Market.get_or_add(session, market_name, market_url)
            if market not in self.markets:
                self.markets.append(market)

            '''
            finding coins by symbol is fucked because a lot of them have
            multiple symbols listed on cmc

            market_pair_cell = market_cells[2]
            market_pair = market_pair_cell.text
            coin_symbol_a, coin_symbol_b = market_pair.split('/')
            if coin_symbol_a == self.symbol:
                base_coin_symbol = coin_symbol_b
            elif coin_symbol_b == self.symbol:
                base_coin_symbol = coin_symbol_a
            else:
                import pdb; pdb.set_trace()

            base_coin = Coin.get_by_symbol(session, base_coin_symbol)
            if not base_coin:
                try:
                    base_coin_ticker = tickers[base_coin_symbol]
                    base_coin = Coin.add_from_ticker(session, base_coin_ticker)
                except:
                    base_coin = Coin(symbol=base_coin_symbol)
                    session.add(base_coin)

            market_pair_url = market_pair_cell.find('a').href

            market_price_cell = market_cells[4]
            market_price_span = market_price_cell.find('span')
            try:
                market_price_value = float(market_price_span['data-native'])
            except:
                logger.warning(f'{self.name}: NULL {base_coin_name} price')
                market_price_value = None

            market_price = MarketPrice.get(session, self.id, base_coin.id, market.id)
            if not market_price:
                market_price = MarketPrice(
                    coin_id=self.id,
                    base_coin_id=base_coin.id,
                    market_id=market.id,
                    market_pair_url=market_pair_url,
                    price=market_price_value
                )
            else:
                market_price.price = market_price_value
            if market_price not in self.market_prices:
                self.market_prices.append(market_price)
            '''
            


class Market(CallBase, GetLoggerMixin):
    __tablename__ = 'markets'
    __loggername__ = f'{__name__}.Market'

    id = Column(Integer, primary_key=True)
    name = Column(Text, index=True)
    url = Column(Text)

    coins = relationship('Coin', secondary=coin_markets, back_populates='markets')

    @classmethod
    def get_or_add(cls, session, market_name, market_url):
        market = session.query(cls) \
                .filter(cls.name == market_name) \
                .first()
        if not market:
            market = cls(name=market_name, url=market_url)
            session.add(market)
            session.flush()

        return market


class MarketPrice(CallBase, GetLoggerMixin):
    __tablename__ = 'market_prices'
    __loggername__ = f'{__name__}.MarketPrice'

    coin_id = Column(Integer, ForeignKey('coins.id'), primary_key=True)
    base_coin_id = Column(Integer, ForeignKey('coins.id'), primary_key=True)
    market_id = Column(Integer, ForeignKey('markets.id'), primary_key=True)
    market_pair_url = Column(Text)
    price = Column(Float)

    coin = relationship('Coin', back_populates='market_prices', foreign_keys=[coin_id])
    base_coin = relationship('Coin', foreign_keys=[base_coin_id])
    market = relationship('Market', foreign_keys=[market_id])

    @classmethod
    def get(cls, session, coin_id, base_coin_id, market_id):
        return session.query(cls).get((coin_id, base_coin_id, market_id))
