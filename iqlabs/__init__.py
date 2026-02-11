from . import contract
from .sdk import reader
from .sdk import writer
from .sdk import utils
from .sdk import constants
from .sdk.utils import wallet
from .sdk.utils.connection_helper import set_rpc_url, set_rpc_provider, get_rpc_url, get_rpc_provider


class IQLabs:
    contract = contract
    reader = reader
    writer = writer
    utils = utils
    wallet = wallet
    constants = constants
    set_rpc_url = staticmethod(set_rpc_url)
    set_rpc_provider = staticmethod(set_rpc_provider)
    get_rpc_url = staticmethod(get_rpc_url)
    get_rpc_provider = staticmethod(get_rpc_provider)


iqlabs = IQLabs()

__all__ = [
    "contract",
    "reader",
    "writer",
    "constants",
    "wallet",
    "utils",
    "set_rpc_url",
    "set_rpc_provider",
    "get_rpc_url",
    "get_rpc_provider",
    "iqlabs",
]
