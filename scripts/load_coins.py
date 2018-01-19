from callbot import configure_app
from callbot.models.meta import (
    CallbotDBSession,
    transaction,
    )
from callbot.models import Coin


def main():
    configure_app(arg_parser=arg_parser)
    with transaction(CallDBSession) as session:
        Coin.load_all_coins(session)
