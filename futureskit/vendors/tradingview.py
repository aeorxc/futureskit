"""TradingView contract notation.

Vendor spelling, not contract grammar: see :mod:`futureskit.vendors`.
"""

from typing import Optional

# Vendor TradingView notation
#
# TradingView spells a dated contract with the FULL FOUR-DIGIT year: March 2026
# Brent is 'BRNH2026'. That is a third contract-year width beside the two RIC
# conventions in futureskit.vendors.lseg (two digits on CME Group venues, one
# on ICE), and unlike
# those it does not vary by exchange. Truncating it to a RIC width produces a
# well-formed symbol that TradingView simply does not carry, so the failure
# reads as a missing instrument rather than a formatting bug.
#
# TradingView also qualifies the same symbol two ways depending on the surface:
# 'FEED:SYMBOL' on a chart and 'FEED-SYMBOL' in an overview path. Both spellings
# are public, since a consumer assembling either URL family needs the one that
# matches its surface and neither is derivable from the other by string edit -
# an unqualified code carries no separator at all.


def _tradingview_fields(
    tv_code: str,
    tv_exchange: Optional[str] = None,
) -> tuple[str, str]:
    """Return ``(feed, symbol)`` with embedded qualification taking precedence."""
    if ":" in tv_code:
        embedded_exchange, symbol = tv_code.split(":", 1)
        return embedded_exchange, symbol
    return tv_exchange or "", tv_code


def _chart_symbol(feed: str, symbol: str) -> str:
    """Return TradingView's ``FEED:SYMBOL`` chart spelling."""
    return f"{feed}:{symbol}" if feed else symbol


def _overview_symbol(feed: str, symbol: str) -> str:
    """Return TradingView's ``FEED-SYMBOL`` overview-path spelling."""
    return f"{feed}-{symbol}" if feed else symbol


def tradingview_chart_symbol(
    tv_code: str,
    tv_exchange: Optional[str] = None,
) -> str:
    """Return TradingView's ``FEED:SYMBOL`` chart spelling for a code.

    This is the qualification a chart URL takes. An embedded feed in
    ``tv_code`` wins over ``tv_exchange``, and an unqualified code is returned
    unchanged rather than gaining an empty prefix.
    """
    return _chart_symbol(*_tradingview_fields(tv_code, tv_exchange))


def tradingview_overview_symbol(
    tv_code: str,
    tv_exchange: Optional[str] = None,
) -> str:
    """Return TradingView's ``FEED-SYMBOL`` overview-path spelling for a code.

    Same inputs as :func:`tradingview_chart_symbol`, different separator:
    TradingView's overview paths hyphenate where its charts use a colon.
    """
    return _overview_symbol(*_tradingview_fields(tv_code, tv_exchange))


def tradingview_contract_symbol(
    tv_code: str,
    year: int,
    month_code: str,
    tv_exchange: Optional[str] = None,
) -> str:
    """Return a dated TradingView symbol using its full four-digit year."""
    feed, root = _tradingview_fields(tv_code, tv_exchange)
    return _chart_symbol(feed, f"{root}{month_code}{year}")


def tradingview_continuous_symbol(
    tv_code: str,
    depth: int,
    tv_exchange: Optional[str] = None,
) -> str:
    """Return a TradingView continuous symbol such as ``ICEEUR:BRN1!``."""
    feed, symbol = _tradingview_fields(tv_code, tv_exchange)
    continuous_symbol = symbol if symbol.endswith("!") else f"{symbol}{depth}!"
    return _chart_symbol(feed, continuous_symbol)
