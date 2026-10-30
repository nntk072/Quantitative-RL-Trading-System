"""Compatibility entrypoint for multi-symbol MT5 rule-based trading.

The application implementation lives in
``integrations.mt5.cli.multi_symbol_trading``. This module preserves the
historical import and ``python live_trading.py`` command surfaces.
"""

from importlib import reload

from integrations.mt5.cli import multi_symbol_trading as _application

_application = reload(_application)

TERMINAL_PATH = _application.TERMINAL_PATH
LOGIN = _application.LOGIN
PASSWORD = _application.PASSWORD
SERVER = _application.SERVER
TRADING_INTERVAL_MINUTES = _application.TRADING_INTERVAL_MINUTES
MAX_SYMBOLS = _application.MAX_SYMBOLS
STRATEGY_TYPE = _application.STRATEGY_TYPE
PAPER_TRADING = _application.PAPER_TRADING
TradingSystem = _application.TradingSystem
create_strategy = _application.create_strategy
get_symbol_candidates = _application.get_symbol_candidates
initialize_trading_system = _application.initialize_trading_system
load_config = _application.load_config
main = _application.main
select_volatile_symbols = _application.select_volatile_symbols


if __name__ == "__main__":
    main()
