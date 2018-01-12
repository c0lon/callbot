from callbot import configure_app
from callbot.models.meta import (
    CallDBSession,
    transaction,
    )
from callbot.models.call_models import Call


def main():
    configure_app()

    with transaction(CallDBSession) as session:
        Call.make_call(session)
