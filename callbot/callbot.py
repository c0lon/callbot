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

    async def make_call(self, message, coin_string):
        logger = self._logger('make_call')
        logger.debug(coin_string)

        with transaction(CallDBSession) as session:
            coin = Coin.find_one_by_string(session, coin_string)
            if isinstance(coin, Coin):
                call = Call.get_by_coin(session, coin)
                if call:
                    response = f'{message.author.mention} There is already an open call on {coin.name}.'
                else:
                    call = Call.make(session, coin)
                    response = call.get_embed(made=True)
            else:
                response = f'{message.author.mention} {coin}'

            await self.respond(message.channel, response)

    async def show_call(self, message, coin_string):
        logger = self._logger('show_call')
        logger.debug(coin_string)

        with transaction(CallDBSession) as session:
            coin = Coin.find_one_by_string(session, coin_string)
            if isinstance(coin, Coin):
                call = Call.get_by_coin(session, coin)
                if call:
                    response = call.get_embed()
                else:
                    response = f'{message.author.mention} No open call on {coin.name}.'
            else:
                response = f'{message.author.mention} {coin}'

            await self.respond(message.channel, response)

    async def list_all_calls(self, message):
        with transaction(CallDBSession) as session:
            response = Call.get_all_open_embed(session)
            await self.respond(message.channel, response)

    async def close_call(self, message, coin_string):
        with transaction(CallDBSession) as session:
            coin = Coin.find_one_by_string(session, coin_string)
            if isinstance(coin, Coin):
                call = Call.get_by_coin(session, coin)
                if not call:
                    response = f'{message.author.mention} No open call on {coin.name}.'
                else:
                    response = call.get_close_embed(session)
            else:
                response = f'{message.author.mention} {coin}'

            await self.respond(message.channel, response)

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
    def watch_calls(cls, **config):
        callbot = cls(**config['bot'])
        logger = cls._logger('watch_calls')

        @callbot.bot.event
        async def on_ready():
            logger.debug('start')

        @callbot.bot.command(pass_context=True)
        async def make(ctx, coin):
            await callbot.make_call(ctx.message, coin)

        @callbot.bot.command(pass_context=True)
        async def show(ctx, coin):
            await callbot.show_call(ctx.message, coin)

        @callbot.bot.command(pass_context=True)
        async def list(ctx):
            await callbot.list_all_calls(ctx.message)

        @callbot.bot.command(pass_context=True)
        async def close(ctx, coin_string):
            await callbot.close_call(ctx.message, coin_string)

        callbot.run()
