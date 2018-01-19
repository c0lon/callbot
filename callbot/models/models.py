from datetime import datetime
import time

import discord
from sqlalchemy import (
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    Text,
    func,
    or_,
    text,
    )
from sqlalchemy.orm import relationship


from .meta import CallbotBase
from ..utils import (
    GetLoggerMixin,
    fetch_url,
    get_arrow,
    get_user,
    percent_change,
    )


COINMARKETCAP_URL_BASE = 'https://coinmarketcap.com'
COINMARKETCAP_COIN_URL_FMT = COINMARKETCAP_URL_BASE + '/currencies/{cmc_id}'
COINMARKETCAP_COIN_MARKETS_URL_FMT = COINMARKETCAP_COIN_URL_FMT + '/#markets'
COINMARKETCAP_COIN_IMG_URL_FMT = 'https://files.coinmarketcap.com/static/img/coins/32x32/{cmc_id}.png'

COINMARKETCAP_API_URL_BASE = 'https://api.coinmarketcap.com/v1'
COINMARKETCAP_API_TICKER_URL = COINMARKETCAP_API_URL_BASE + '/ticker'
COINMARKETCAP_API_COIN_URL_FMT = COINMARKETCAP_API_TICKER_URL + '/{cmc_id}'

TIMESTAMP_FMT = '%Y-%m-%d %H:%M UTC'


class Call(CallbotBase, GetLoggerMixin):
    """ Model of a call made on a coin. """

    __tablename__ = 'calls'
    __loggername__ = f'{__name__}.Call'

    id = Column(Integer, primary_key=True)
    coin_id = Column(Integer, ForeignKey('coins.id'))
    channel_id = Column(Text, index=True)
    caller_id = Column(Text, index=True)
    start_price_btc = Column(Float)
    start_price_usd = Column(Float)
    final_price_btc = Column(Float)
    final_price_btc = Column(Float)
    total_percent_change_btc = Column(Float)
    total_percent_change_usd = Column(Float)
    closed = Column(Integer, server_default=text("'0'"), index=True)
    timestamp_made = Column(DateTime, default=datetime.utcnow)
    timestamp_closed = Column(DateTime)

    coin = relationship('Coin', foreign_keys=[coin_id], lazy='joined')

    def get_caller(self, ctx):
        return get_user(ctx, self.caller_id)

    @classmethod
    def get_caller_id_from_string(cls, ctx, string):
        if not string:
            return ctx.message.author.id

        string = string.lower()
        if string == 'all':
            return None
        elif string == 'mine':
            return ctx.message.author.id
        
        for member in ctx.message.server.members:
            if string == member.name.lower():
                return member.id
            if member.nick and string == member.nick.lower():
                return member.id

        return ctx.message.author.id

    def get_percent_change_btc(self):
        return percent_change(self.start_price_btc, self.coin.current_price_btc)
    percent_change_btc = property(get_percent_change_btc)

    def get_percent_change_usd(self):
        return percent_change(self.start_price_usd, self.coin.current_price_usd)
    percent_change_usd = property(get_percent_change_usd)

    def get_percent_change(self):
        return self.percent_change_btc, self.percent_change_usd
    percent_change = property(get_percent_change)

    @classmethod
    def get_no_calls_embed(cls, session, ctx, caller_id=None, coin=None, closed=False):
        embed = discord.Embed()
        if closed:
            embed.title = 'No Closed Calls'
        else:
            embed.title = 'No Open Calls'
        if caller_id:
            caller = get_user(ctx, caller_id)
            embed.title += f' by {caller.name}'
        if coin:
            embed.title += f' on {coin.name}'
            embed.url = coin.cmc_url
            embed.set_thumbnail(url=coin.cmc_image_url)

        return embed

    @classmethod
    def make(cls, session, ctx, coin):
        logger = cls._logger('make_quick_call')
        logger.debug(coin.name)

        current_price_btc, current_price_usd = coin.current_price
        call = cls(
            start_price_btc=current_price_btc,
            start_price_usd=current_price_usd,
            channel_id=ctx.message.channel.id,
            caller_id=ctx.message.author.id
        )
        call.coin = coin
        session.add(call)
        session.flush()

        return call

    @classmethod
    def make_embed(cls, session, ctx, coin):
        call = cls.make(session, ctx, coin)
        embed = discord.Embed(title=f'Call made on {call.coin.name} ({call.coin.symbol})', url=call.coin.cmc_url)
        embed.add_field(name='Price (BTC)',
                value=f'{call.start_price_btc:.8f} BTC')
        embed.add_field(name='Price (USD)',
                value=f'$ {call.start_price_usd:.2f}')

        return embed

    @classmethod
    def get_all_open(cls, session, caller_id=None):
        calls = session.query(cls).filter(cls.closed == 0)
        if caller_id:
            calls = calls.filter(cls.caller_id == caller_id)

        return calls.all()

    @classmethod
    def get_all_open_embed(cls, session, ctx, prices_in='btc', caller_id=None):
        calls = cls.get_all_open(session, caller_id=caller_id)
        if calls:
            embed = discord.Embed(title=f'All Open Calls')
            if caller_id:
                caller = get_user(ctx, caller_id)
                embed.title += f' made by {caller.name}'

            for call in calls:
                if prices_in == 'btc':
                    arrow = get_arrow(call.percent_change_btc)
                    name = f'{call.coin.name} ({call.coin.symbol}) {arrow} {abs(call.percent_change_btc):.2f} %'
                    value = f'{call.start_price_btc:.8f} BTC -> {call.coin.current_price_btc:.8f} BTC'
                    if not caller_id:
                        caller = call.get_caller(ctx)
                        name = f'[{caller.name}] {name}'
                elif prices_in == 'usd':
                    arrow = get_arrow(call.percent_change_usd)
                    name = f'{call.coin.name}{arrow} {abs(call.percent_change_usd):.2f} %'
                    value = f'$ {call.start_price_usd:.2f} -> $ {call.coin.current_price_usd:.2f}'
                embed.add_field(name=name, value=value, inline=False)
        else:
            embed = cls.get_no_calls_embed(session, ctx, caller_id=caller_id)

        return embed

    @classmethod
    def get_by_coin(cls, session, coin):
        return session.query(cls) \
                .filter(cls.coin_id == coin.id) \
                .filter(cls.closed == 0) \
                .all()

    @classmethod
    def get_by_coin_and_caller(cls, session, coin, caller_id):
        return session.query(cls) \
                .filter(cls.coin_id == coin.id) \
                .filter(cls.caller_id == caller_id) \
                .filter(cls.closed == 0) \
                .first()

    @classmethod
    def get_by_coin_and_caller_embed(cls, session, ctx, coin, caller_id):
        call = cls.get_by_coin_and_caller(session, coin, caller_id)
        if not call:
            return cls.get_no_calls_embed(session, ctx, coin=coin, caller_id=caller_id)

        return call.get_embed(session, ctx)

    @classmethod
    def get_last(cls, session, coin=None, caller_id=None):
        last_call = session.query(cls) \
                .filter(cls.closed == 0) \
                .order_by(cls.timestamp_made.desc())
        if coin:
            last_call = last_call.filter(cls.coin_id == coin.id)
        if caller_id:
            last_call = last_call.filter(cls.caller_id == caller_id)

        return last_call.first()

    @classmethod
    def get_last_embed(cls, session, ctx, coin=None, caller_id=None):
        call = cls.get_last(session, coin=coin, caller_id=caller_id)
        if call:
            embed = call.get_embed(session, ctx)
        else:
            embed = cls.get_no_calls_embed(session, ctx, coin=coin, caller_id=caller_id)

        return embed

    @classmethod
    def get_best(cls, session, caller_id=None, closed=True, count=5):
        best_calls = session.query(cls)

        if closed:
            return cls.get_best_closed(session, caller_id=caller_id, count=count)
        else:
            return cls.get_best_open(session, caller_id=caller_id, count=count)

    @classmethod
    def get(cls, session, caller_id=None, offset=None, closed=None, count=None, order_by=None):
        calls = session.query(cls)
        if closed is not None:
            closed = 1 if closed else 0
            calls = calls.filter(cls.closed == closed)
        if order_by:
            calls = calls.order_by(order_by())
        if caller_id:
            calls = calls.filter(cls.caller_id == caller_id)
        if offset:
            calls = calls.offset(offset)
        if count:
            calls = calls.limit(count)

        return calls.all()

    @classmethod
    def get_best_open(cls, session, caller_id=None, count=5):
        all_open_calls = cls.get(session, caller_id=caller_id, closed=False)
        sorted_calls = sorted(all_open_calls, key=lambda c: c.percent_change_btc, reverse=True)

        return sorted_calls[:count]

    @classmethod
    def get_best_closed(cls, session, caller_id=None, count=5):
        return cls.get(session, caller_id=caller_id, count=count,
                closed=True, order_by=cls.total_percent_change_btc.desc)

    @classmethod
    def get_best_embed(cls, session, ctx, caller_id=None, count=5, closed=True, **kwargs):
        best_calls = cls.get_best(session, caller_id=caller_id, closed=closed, count=count)
        if not best_calls:
            return cls.get_no_calls_embed(session, ctx, caller_id=caller_id, closed=closed)

        open_or_closed = 'Closed' if closed else 'Open'
        if len(best_calls) == 1:
            title = f'Top {open_or_closed} Call'
        else:
            title = f'Top {len(best_calls)} {open_or_closed} Calls'
        if caller_id:
            caller = get_user(ctx, caller_id)
            title += f' made by {caller.name}'

        embed = discord.Embed(title=title)
        for call in best_calls:
            if closed:
                end_price_btc = call.final_price_btc
                percent_change_btc = call.total_percent_change_btc
            else:
                end_price_btc = call.coin.current_price_btc
                percent_change_btc = call.percent_change_btc

            arrow = get_arrow(call.percent_change_btc)
            name = f'{call.coin.name} ({call.coin.symbol}) {arrow} {abs(percent_change_btc):.2f} %'
            if not caller_id:
                caller = call.get_caller(ctx)
                name = f'[{caller.name}] {name}'
            value = f'{call.start_price_btc:.8f} BTC -> {end_price_btc:.8f} BTC'
            embed.add_field(name=name, value=value, inline=False)

        return embed

    @classmethod
    def get_by_coin_embed(cls, session, ctx, coin, caller_id=None):
        call = cls.get_by_coin(session, coin)
        if call:
            embed = call.get_embed(session, ctx)
        else:
            embed = cls.get_no_calls_embed(session, ctx, coin=coin)

        return embed

    def get_embed(self, session, ctx):
        caller = get_user(ctx, self.caller_id)
        embed = discord.Embed(title=f'[{caller.name}] Call on {self.coin.name} ({self.coin.symbol})',
                url=self.coin.cmc_url)
        embed.set_thumbnail(url=self.coin.cmc_image_url)

        # show percent changes
        btc_arrow = get_arrow(self.percent_change_btc)
        embed.add_field(name='Percent change (BTC)',
                value=f'{btc_arrow}{abs(self.percent_change_btc):.2f} %')
        usd_arrow = get_arrow(percent_change_usd)
        embed.add_field(name='Percent Change (USD)',
                value=f'{usd_arrow}{abs(self.percent_change_usd):.2f} %')

        # show current prices
        embed.add_field(name='Current Price (BTC)',
                value=f'{self.current_price_btc:.8f} BTC')
        embed.add_field(name='Current Price (USD)',
                value=f'$ {self.current_price_usd:.2f}')

        # show call prices
        embed.add_field(name='Call Price (BTC)',
                value=f'{self.start_price_btc:.8f} BTC')
        embed.add_field(name='Call Price (USD)',
                value=f'$ {self.start_price_usd:.2f}')

        embed.add_field(name='Call Made',
                value=self.timestamp_made.strftime(TIMESTAMP_FMT))

        return embed

    def close(self, session):
        self.closed = 1
        self.final_price_btc = self.coin.current_price_btc
        self.final_price_usd = self.coin.current_price_usd
        self.total_percent_change_btc = self.percent_change_btc
        self.total_percent_change_usd = self.percent_change_usd

    def close_embed(self, session, ctx):
        self.close(session)

        embed = discord.Embed(title=f'Call closed on {self.coin.name} ({self.coin.symbol})',
                url=self.coin.cmc_url)
        embed.set_thumbnail(url=self.coin.cmc_image_url)

        # show percent changes
        btc_arrow = get_arrow(self.total_percent_change_btc)
        embed.add_field(name='Total Percent Change (BTC)',
                value=f'{btc_arrow}{abs(self.total_percent_change_btc):.2f} %')
        usd_arrow = get_arrow(self.total_percent_change_usd)
        embed.add_field(name='Total Percent Change (USD)',
                value=f'{usd_arrow}{abs(self.total_percent_change_usd):.2f} %')

        # show final prices
        embed.add_field(name='Final Price (BTC)',
                value=f'{self.final_price_btc:.8f}')
        embed.add_field(name='Final Price (USD)',
                value=f'$ {self.final_price_usd:.2f}')

        # show call prices
        embed.add_field(name='Call Price (BTC)',
                value=f'{self.start_price_btc:.8f}')
        embed.add_field(name='Call Price (USD)',
                value=f'$ {self.start_price_usd:.2f}')

        # show call date
        embed.add_field(name='Call Made',
                value=self.timestamp_made.strftime(TIMESTAMP_FMT), inline=False)

        return embed


class Coin(CallbotBase, GetLoggerMixin):
    """ Model of a Coin on Coinmarketcap. """

    """ Coinmarketcap attributes """
    __loggername__ = f'{__name__}.Coin'

    TICKER = {}
    TICKER_TTL = 10
    TICKER_LAST_UPDATE = 0

    @classmethod
    def get_global_ticker(cls):
        """ Fetch the ticker for all coins.
        If the ticker is empty or stale, fetch it from coinmarketcap.
        """
        if not cls.TICKER or time.time() - cls.TICKER_LAST_UPDATE > cls.TICKER_TTL:
            cls.update_global_ticker()
            cls.TICKER_LAST_UPDATE = time.time()

        return cls.TICKER

    @classmethod
    def update_global_ticker(cls):
        """ Fetch the global ticker from coinmarketcap. """
        api_response = fetch_url(COINMARKETCAP_API_TICKER_URL, params={'limit' : 0})
        if not api_response:
            return {} if to_dict else None

        ticker = api_response.json()
        ticker_dict = {}
        for coin_ticker in ticker:
            ticker_dict[coin_ticker['id']] = coin_ticker
        cls.TICKER = ticker_dict

        return cls.TICKER

    def get_cmc_url(self):
        return COINMARKETCAP_COIN_MARKETS_URL_FMT.format(cmc_id=self.cmc_id)
    cmc_url = property(get_cmc_url)

    def get_cmc_api_url(self):
        return COINMARKETCAP_API_COIN_URL_FMT.format(cmc_id=self.cmc_id)
    cmc_api_url = property(get_cmc_api_url)

    def get_cmc_image_url(self):
        return COINMARKETCAP_COIN_IMG_URL_FMT.format(cmc_id=self.cmc_id)
    cmc_image_url = property(get_cmc_image_url)

    def get_current_price_btc(self):
        coin_ticker = Coin.get_global_ticker().get(self.cmc_id)
        if not coin_ticker:
            # TODO
            return 0.0
        return float(coin_ticker['price_btc'])
    current_price_btc = property(get_current_price_btc)

    def get_current_price_usd(self):
        ticker = Coin.get_global_ticker()
        coin_ticker = ticker.get(self.cmc_id)
        if not coin_ticker:
            # TODO
            return 0.0
        return float(coin_ticker['price_usd'])
    current_price_usd = property(get_current_price_usd)

    def get_current_price(self):
        return self.current_price_btc, self.current_price_usd
    current_price = property(get_current_price)

    """ SQLAlchemy attributes """
    __tablename__ = 'coins'

    id = Column(Integer, primary_key=True)
    name = Column(Text, index=True)
    symbol = Column(Text, index=True)
    cmc_id = Column(Text)

    calls = relationship('Call', back_populates='coin')

    def get_open_calls(self):
        return [c for c in self.calls if not c.closed]
    open_calls = property(get_open_calls)

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
    def get_by_cmc_id(cls, session, coin_cmc_id):
        return session.query(cls) \
                .filter(cls.cmc_id == coin_cmc_id) \
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

    def get_calls_embed(self, session, ctx, prices_in='btc', caller_id=None):
        if caller_id:
            return Call.get_by_coin_and_caller_embed(session, ctx, self, caller_id)

        if not self.open_calls:
            return Call.get_no_calls_embed(session, ctx, coin=self)

        embed = discord.Embed(title=f'All Open Calls on {self.name}', url=self.cmc_url)
        for call in self.open_calls:
            caller = call.get_caller(ctx)
            if prices_in == 'btc':
                arrow = get_arrow(percent_change_btc)
                name = f'[{caller.name}] {self.name}{arrow} {abs(call.percent_change_btc):.2f} %'
                value = f'{call.start_price_btc:.8f} BTC -> {call.coin.current_price_btc:.8f} BTC'
            elif prices_in == 'usd':
                arrow = get_arrow(percent_change_usd)
                name = f'[{caller.name}] {self.name}{arrow} {abs(call.percent_change_usd):.2f} %'
                value = f'$ {call.start_price_usd:.2f} -> $ {call.coin.current_price_usd:.2f}'

            embed.add_field(name=name, value=value, inline=False)

        return embed

    def close_call_by_caller(self, session, ctx):
        caller_id = ctx.message.author.id
        call = Call.get_by_coin_and_caller(session, self, caller_id)
        if not call:
            return Call.get_no_calls_embed(session, ctx, coin=self, caller_id=caller_id)

        return call.close_embed(session, ctx)

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
    def load_all_coins(cls, session):
        for coin_cmc_id, coin_ticker in cls.get_global_ticker().items():
            if not cls.get_by_cmc_id(session, coin_cmc_id):
                coin = cls.add_from_ticker(session, coin_ticker)
