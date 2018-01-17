""" TODO
* add open/closed options to all commands

"""


from argparse import ArgumentParser
import logging.config
import os
import sys

import yaml

from . import models

from .callbot import Callbot


here = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
with open(os.path.join(here, 'VERSION')) as f:
    __version__ = f.read().strip()
__author__ = 'c0lon'
__email__ = ''


def get_default_arg_parser():
    arg_parser = ArgumentParser()
    arg_parser.add_argument('config_uri', type=str,
            help='the config file to use.')
    arg_parser.add_argument('--log-level', type=str,
            choices=['DEBUG', 'INFO', 'WARN', 'ERROR', 'CRITICAL'])
    arg_parser.add_argument('--version', action='store_true',
            help='Show the package version and exit.')
    arg_parser.add_argument('--debug', action='store_true')

    return arg_parser


def configure_app(config_uri='', arg_parser=None):
    """ Configure the application.
    """

    args = {'config_uri' : config_uri}
    if not args['config_uri']:
        arg_parser = arg_parser or get_default_arg_parser()
        args = vars(arg_parser.parse_args())

    if args.pop('version', None):
        print(__version__)
        sys.exit(0)

    try:
        with open(args['config_uri']) as f:
            config = yaml.load(f)
    except:
        print('invalid config file: {}'.format(args['config_uri']))
        sys.exit(1)
    else:
        config['args'] = args

    if args.get('log_level'):
        config['logging']['root']['level'] = args.pop('log_level')
    logging.config.dictConfig(config['logging'])

    config['main'] = config.get('main', {})
    config['main']['debug'] = args.get('debug', False)

    models.configure(**config.get('models', {}))

    return config['main'], config
