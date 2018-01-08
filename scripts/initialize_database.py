from callbot import configure_app

''' Import Base objects here.

    >>> from callbot.models.meta import Base
'''


def main():
    configure_app()

    ''' Drop + create schemas here.

    >>> Base.metadata.drop_all()
    >>> Base.metadata.create_all()
    '''
