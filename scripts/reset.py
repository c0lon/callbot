from callbot import configure_app
from callbot.models.meta import (
    CallBase,
    CallDBSession,
    transaction,
    )
from callbot.models.call_models import Coin


def main():
    configure_app()

    CallBase.metadata.drop_all()
    CallBase.metadata.create_all()

    with transaction(CallDBSession) as session:
        Coin.load_all_coins(session)
