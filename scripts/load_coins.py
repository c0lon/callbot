from callbot import (
    configure_app,
    get_default_arg_parser,
    )
from callbot.models.meta import (
    CallDBSession,
    transaction,
    )
from callbot.models.call_models import Coin


def main():
    arg_parser = get_default_arg_parser()
    arg_parser.add_argument('-c', '--count', type=int,
            help='Load first COUNT coins.')
    settings, config = configure_app(arg_parser=arg_parser)

    with transaction(CallDBSession) as session:
        Coin.load_all_coins(session, count=config['args'].get('count'))
