"""Deprecated compatibility imports for persisted trade-thesis terminology.

The canonical implementation is :mod:`decisioning.trade_setup`. Keep this
module available so old source imports and checkpoint class paths continue to
resolve while they are migrated deliberately.
"""

from decisioning.trade_setup import *  # noqa: F403
