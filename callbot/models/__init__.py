from sqlalchemy import create_engine
from sqlalchemy.orm import configure_mappers

''' Import Base and sessionmaker objects here.

    >>> from .meta import (
    >>>     Base,
    >>>     Session,
    >>>     )
'''

''' Import all model classes here.

    >>> from .models import Model
'''


configure_mappers()


def configure_database_connection(base, session_factory, **cnx_settings):
    engine = create_engine(cnx_settings.pop('url'), **cnx_settings)
    base.metadata.bind = engine
    session_factory.configure(bind=engine)


def configure(**settings):
    ''' Configure schema objects here.

        >>> configure_database_connection(Base, Session, **settings['schema'])
    '''
