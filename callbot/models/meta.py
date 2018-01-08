from contextlib import contextmanager
import logging
from uuid import uuid4

from sqlalchemy import MetaData
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker


NAMING_CONVENTION = {
    "ix": 'ix_%(column_0_label)s',
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s"
}


metadata = MetaData(naming_convention=NAMING_CONVENTION)
CallBase = declarative_base(metadata=metadata)
CallDBSession = sessionmaker()


@contextmanager
def transaction(session_factory, commit=True):
    logger = logging.getLogger(f'{__name__}.transaction')

    try:
        session = session_factory()
    except:
        logger.error('error opening database session', exc_info=True)
        raise

    transaction_id = str(uuid4())
    schema = session.bind.url.database
    extra = {'transaction_id' : transaction_id, 'schema' : schema}
    logger.debug('open', extra=extra)

    try:
        yield session
    except:
        logger.error('error', exc_info=True, extra=extra)
        session.rollback()
        raise
    else:
        if commit:
            logger.debug('commit', extra=extra)
            session.commit()
    finally:
        logger.debug('close', extra=extra)
        session.close()


def initialize_database():
    CallBase.metadata.drop_all()
    CallBase.metadata.create_all()
