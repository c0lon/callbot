from callbot import configure_app
from callbot.models.meta import (
    CallbotBase,
    CallbotDBSession,
    initialize_database,
    transaction,
    )
from callbot.models import Coin


def main():
    configure_app()

    initialize_database()
    with transaction(CallbotDBSession) as session:
        Coin.load_all_coins(session)
