import hupper

from callbot import (
    Callbot,
    configure_app,
    get_default_arg_parser,
    )


def main():
    arg_parser = get_default_arg_parser()
    arg_parser.add_argument('--reload', action='store_true',
        help='reload the application on a code change.')
    settings, config = configure_app(arg_parser=arg_parser)

    if config['args'].get('reload'):
        reloader = hupper.start_reloader(f'{__name__}.main')
        reloader.watch_files([config['args']['config_uri']])

    Callbot.watch_calls(**settings)
