from callbot import configure_app
from callbot.models.meta import initialize_database


def main():
    configure_app()
    initialize_database()
