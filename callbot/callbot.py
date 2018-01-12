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

    async def make_call(self, message, *args):
        logger = self._logger('make_call')
        logger.debug(args)

        if len(args) == 1:
            response = await self.make_quick_call(message, args[0])

        if isinstance(response, discord.Embed):
            logger.info(response.title)
            await self.bot.send_message(message.channel, embed=response)
        else:
            logger.info(response)
            await self.bot.send_message(message.channel, response)

    async def make_quick_call(self, message, coin_string):
        self._logger('make_quick_call').debug(coin_string)

        with transaction(CallDBSession) as session:
            coin_matches = Coin.find_by_string(session, coin_string)
            if not coin_matches:
                response = f'{message.author.mention} no matches for "{coin_string}".'
            elif len(coin_matches) == 1:
                coin = coin_matches[0]
                coin.update(session)
                call = Call.make_quick_call(session, coin)

                response = discord.Embed(title=f'Call made on {coin.name} ({coin.symbol})')
                response.add_field(name='CMC Price (BTC)', value=coin.cmc_price_btc, inline=False)
                response.add_field(name='CMC Price (USD)', value=coin.cmc_price_usd, inline=False)

                #markets_string = '\n'.join([m.name for m in coin.markets])
                #response.add_field(name='Markets', value=markets_string, inline=False)
            else:
                response = f'{message.author.mention} multiple matches for "{coin_string}":'
                response += '\n{}'.format('\n'.join([cm.name for cm in coin_matches]))

        return response

    async def list_calls(self, message, *args):
        logger = self._logger('list_calls')
        logger.debug(args)

        if len(args) == 0:
            response = await self.list_all_calls()
        elif len(args) == 1:
            response = await self.list_call(args[0])

        if isinstance(response, discord.Embed):
            logger.info(response.title)
            await self.bot.send_message(message.channel, embed=response)
        else:
            logger.info(response)
            await self.bot.send_message(message.channel, response)

    async def list_all_calls(self):
        with transaction(CallDBSession) as session:
            for call in Call.get_all_open_calls(session):
                embed = calll.get_embed()
                await self.bot.send_message

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
        async def make(ctx, *args):
            await callbot.make_call(ctx.message, *args)

        @callbot.bot.command(pass_context=True)
        async def list(ctx, *args):
            await callbot.list_calls(ctx.message, *args)

        callbot.run()
