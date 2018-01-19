from sqlalchemy import create_engine
from sqlalchemy.orm import configure_mappers

from .meta import (
    CallbotBase,
    CallbotDBSession,
    )
from .models import (
    Call,
    Coin,
    )


configure_mappers()


def configure_database_connection(base, session_factory, **cnx_settings):
    engine = create_engine(cnx_settings.pop('url'), **cnx_settings)
    base.metadata.bind = engine
    session_factory.configure(bind=engine)


def configure(**settings):
    configure_database_connection(CallbotBase, CallbotDBSession, **settings['callbot'])
