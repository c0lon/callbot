from collections import namedtuple
import pytest

from . import *

from callbot.models.meta import (
    CallDBSession,
    transaction,
    )
from callbot.models.call_models import Coin


MockCoin = namedtuple('MockCoin', ('id', 'name', 'symbol'))
COINS = [
    MockCoin('vechain', 'VeChain', 'VEN')
]


def assert_coin(mock_coin, coin_model):
    assert coin_model.name == mock_coin.name
    assert coin_model.symbol == mock_coin.symbol
    assert coin_model.cmc_id == mock_coin.id


#@pytest.mark.skip
def test_add_coin():
    mock_coin = random.choice(COINS)

    with transaction(CallDBSession) as session:
        coin_model = Coin.add_from_name(session, mock_coin.id)
        assert_coin(mock_coin, coin_model)

    with transaction(CallDBSession) as session:
        coin_model = Coin.get_by_name(session, mock_coin.name)
        assert_coin(mock_coin, coin_model)
        session.delete(coin_model)
