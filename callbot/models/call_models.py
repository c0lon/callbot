from datetime import datetime

from sqlalchemy import (
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    Table,
    Text,
    )
from sqlalchemy.orm import relationship


from .meta import CallBase
from ..utils import (
    GetLoggerMixin,
    fetch_url,
    get_soup,
    )


COINMARKETCAP_URL_FMT = 'https://coinmarketcap.com/currencies/{coin}'
COINMARKETCAP_API_URL_FMT = 'https://api.coinmarketcap.com/v1/ticker/{coin}'


class Call(CallBase, GetLoggerMixin):
    __tablename__ = 'calls'
    __loggername__ = f'{__name__}.Call'

    id = Column(Integer, primary_key=True)
    coin_id = Column(Integer, ForeignKey('coins.id'))
    buy_target = Column(Float)
    sell_target = Column(Float)
    hold_time = Column(Text)
    risk = Column(Text)
    reward = Column(Text)
    stack_percentage = Column(Float)
    writeup_url = Column(Text)
    timestamp = Column(DateTime, default=datetime.utcnow)

    coin = relationship('Coin', foreign_keys=[coin_id], lazy='joined')


coin_markets = Table('coin_markets', CallBase.metadata,
    Column('coin_id', Integer, ForeignKey('coins.id'), primary_key=True),
    Column('market_id', Integer, ForeignKey('markets.id'), primary_key=True)
)


class Coin(CallBase, GetLoggerMixin):
    __tablename__ = 'coins'
    __loggername__ = f'{__name__}.Coin'

    id = Column(Integer, primary_key=True)
    name = Column(Text)
    symbol = Column(Text)
    cmc_id = Column(Text)

    markets = relationship('Market', secondary=coin_markets, back_populates='coins')

    @classmethod
    def get_by_name(cls, session, coin_name):
        return session.query(cls) \
                .filter(cls.name == coin_name) \
                .first()

    @classmethod
    def add_from_name(cls, session, coin_name):
        cmc_api_url = COINMARKETCAP_API_URL_FMT.format(coin=coin_name)
        api_response = fetch_url(cmc_api_url)
        if not api_response:
            return

        api_response = api_response.json()
        if not api_response:
            return

        ticker = api_response[0]
        cmc_name = ticker['name']
        cmc_symbol = ticker['symbol']
        cmc_id = ticker['id']

        coin = cls(
            name=cmc_name,
            symbol=cmc_symbol,
            cmc_id=cmc_id,
        )
        coin.load_markets(session)

        session.add(coin)
        session.flush()

        return coin

    @classmethod
    def get_or_add(cls, session, coin_name):
        coin = cls.get_by_name(session, coin_name)
        if not coin:
            coin = cls.add_from_name(session, coin_name)

        return coin

    def load_markets(self, session):
        cmc_url = COINMARKETCAP_URL_FMT.format(coin=self.cmc_id)
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
            market_name = market_cells[1].text
            market = Market.get_or_add(session, market_name)
            self.markets.append(market)


class Market(CallBase, GetLoggerMixin):
    __tablename__ = 'markets'
    __loggername__ = f'{__name__}.Market'

    id = Column(Integer, primary_key=True)
    name = Column(Text)

    coins = relationship('Coin', secondary=coin_markets, back_populates='markets')

    @classmethod
    def get_or_add(cls, session, market_name):
        market = session.query(cls) \
                .filter(cls.name == market_name) \
                .first()
        if not market:
            market = cls(name=market_name)
            session.add(market)
            session.flush()

        return market
