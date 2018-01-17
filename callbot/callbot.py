import discord
from discord.ext import commands

from .models.meta import (
    CallDBSession,
    transaction,
    )
from .models.call_models import (
    Call,
    Coin,
    )
from .utils import GetLoggerMixin


class Callbot(GetLoggerMixin):
    NAME = 'Callbot'
    __loggername__ = f'{__name__}.{NAME}'

    def __init__(self, **config):
        self.bot = commands.Bot(command_prefix=config['command_prefix'])
        self.bot_token = config['token']
        self.debug = config.get('debug', False)

    async def make_call(self, ctx, coin_string, **kwargs):
        logger = self._logger('make_call')
        logger.debug(coin_string)

        with transaction(CallDBSession) as session:
            coin = Coin.find_one_by_string(session, coin_string)
            if isinstance(coin, Coin):
                call = Call.get_by_coin_and_caller(session, coin, ctx.message.author.id)
                if call:
                    msg = f'{ctx.message.author.mention} You already have an open call on {coin.name}.'
                    await self.respond(ctx.message.channel, msg)
                    response = call.get_embed(session, ctx)
                else:
                    response = Call.make_embed(session, ctx, coin)
            else:
                response = coin

            await self.respond(ctx.message.channel, response)

    async def show_call(self, ctx, coin_string, prices_in='btc', caller_id=None, **kwargs):
        logger = self._logger('show_call')
        logger.debug(coin_string)

        with transaction(CallDBSession) as session:
            coin = Coin.find_one_by_string(session, coin_string)
            if isinstance(coin, Coin):
                response = coin.get_calls_embed(session, ctx, prices_in=prices_in, caller_id=caller_id)
            else:
                response = coin

            await self.respond(ctx.message.channel, response)

    async def show_last_call(self, ctx, caller_id=None, **kwargs):
        logger = self._logger('show_last_call')

        with transaction(CallDBSession) as session:
            response = Call.get_last_embed(session, ctx, caller_id=caller_id)
            await self.respond(ctx.message.channel, response)

    async def list_all_calls(self, ctx, prices_in='btc', caller_id=None, **kwargs):
        with transaction(CallDBSession) as session:
            response = Call.get_all_open_embed(session, ctx, prices_in=prices_in, caller_id=caller_id)
            await self.respond(ctx.message.channel, response)

    async def close_call(self, ctx, coin_string, **kwargs):
        with transaction(CallDBSession) as session:
            coin = Coin.find_one_by_string(session, coin_string)
            if isinstance(coin, Coin):
                response = coin.close_call_by_caller(session, ctx)
            else:
                response = coin

            await self.respond(ctx.message.channel, response)

    async def show_best(self, ctx, **kwargs):
        with transaction(CallDBSession) as session:
            response = Call.get_best_embed(session, ctx, **kwargs)
            await self.respond(ctx.message.channel, response)

    async def respond(self, target, content):
        logger = self._logger('respond')

        if isinstance(content, discord.Embed):
            logger.info(content.title)
            await self.bot.send_message(target, embed=content)
        else:
            logger.info(content)
            await self.bot.send_message(target, content)

    def run(self):
        self.bot.run(self.bot_token)

    @classmethod
    def get_kwargs_from_args(cls, ctx, *args, **overrides):
        kwargs = {
            'prices_in' : 'btc',
            'caller_id' : ctx.message.author.id,
            'closed' : False
        }
        kwargs.update(overrides)

        for arg in args:
            if arg.lower() in ['btc', 'usd']:
                kwargs['prices_in'] = arg.lower()
                continue

            if arg.lower() == 'open':
                kwargs['closed'] = False
                continue
            elif arg.lower() == 'closed':
                kwargs['closed'] = True
                continue

            kwargs['caller_id'] = Call.get_caller_id_from_string(ctx, arg)
            if kwargs['caller_id']: continue

            # catch all
            kwargs[arg] = arg

        return kwargs

    @classmethod
    def watch_calls(cls, **config):
        callbot = cls(**config['bot'])
        logger = cls._logger('watch_calls')

        @callbot.bot.event
        async def on_ready():
            logger.debug('start')

        @callbot.bot.event
        async def on_message(message):
            """ Do any preprocessing here.

            Restrict to certain channels?
            """
            await callbot.bot.process_commands(message)

        @callbot.bot.command(pass_context=True)
        async def make(ctx, coin : str):
            """ Make a call.
            The current price listed on Coinmarketcap will be recorded.

            Arguments:
                [Required] coin: The coin to make a call on
            """
            await callbot.make_call(ctx, coin)

        @callbot.bot.command(pass_context=True)
        async def show(ctx, coin : str, *args):
            """ Show the status of an open call. The current price is compared to
            the price recorded when the call was made.

            Arguments:
                [Required] coin: The coin to check the call status of
                caller:
                   show the open call on the given coin by the given caller
                   defaults to you

            Options:
                all: show all open calls on the given coin
                btc: show prices in BTC (default)
                usd: show prices in USD
            """
            kwargs = cls.get_kwargs_from_args(ctx, *args)
            await callbot.show_call(ctx, coin, **kwargs)

        @callbot.bot.command(pass_context=True)
        async def showlast(ctx, caller=None):
            """ Show the last call made.

            Arguments:
                caller: show the last call made by the given caller
            """
            caller_id = Call.get_caller_id_from_string(ctx, caller)
            await callbot.show_last_call(ctx, caller_id=caller_id)

        @callbot.bot.command(pass_context=True)
        async def list(ctx, *args):
            """ List open calls. If no options are given, lists your open calls.

            Arguments:
                caller: show calls made by the given caller

            Options:
                all: show all open calls
                btc: show prices in BTC (default)
                usd: show prices in USD
            """
            kwargs = cls.get_kwargs_from_args(ctx, *args)
            await callbot.list_all_calls(ctx, **kwargs)

        @callbot.bot.command(pass_context=True)
        async def close(ctx, coin : str):
            """ Close an open call.

            Parameters:
                [Required] coin: the coin to close the call on
            """
            await callbot.close_call(ctx, coin)

        @callbot.bot.command(pass_context=True)
        async def best(ctx, *args):
            """ Show the best closed calls.

            Arguments:
                caller:
                    show calls made by the given caller
                    defaults to you

            Options:
                closed: show best closed calls
                open: show best open calls
            """
            kwargs = cls.get_kwargs_from_args(ctx, *args)
            await callbot.show_best(ctx, **kwargs)

        callbot.run()
