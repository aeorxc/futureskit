"""Tests for TradingView vendor symbol notation.

TradingView is the third contract-year convention futureskit carries: a full
four-digit year, against two digits on CME Group RICs and one on ICE. It also
qualifies a symbol differently per surface — ``FEED:SYMBOL`` on a chart,
``FEED-SYMBOL`` in an overview path. These tests pin both.
"""

from futureskit.vendors.tradingview import (
    tradingview_chart_symbol,
    tradingview_continuous_symbol,
    tradingview_contract_symbol,
    tradingview_overview_symbol,
)


def test_tradingview_contract_symbol_uses_full_year():
    assert tradingview_contract_symbol("BRN", 2026, "H") == "BRNH2026"


def test_tradingview_continuous_symbol_uses_depth_and_bang():
    assert tradingview_continuous_symbol("BRN", 3) == "BRN3!"


def test_qualified_tv_code_wins_over_separate_exchange():
    symbol = tradingview_continuous_symbol(
        "ICEEUR:BRN",
        depth=1,
        tv_exchange="NYMEX",
    )

    assert symbol == "ICEEUR:BRN1!"


def test_existing_continuous_code_is_preserved():
    assert tradingview_continuous_symbol("ICEEUR:BRN1!", 3) == "ICEEUR:BRN1!"


def test_overview_spelling_hyphenates_where_the_chart_spelling_colons():
    assert tradingview_overview_symbol("ICEEUR:BRN1!") == "ICEEUR-BRN1!"
    assert tradingview_chart_symbol("ICEEUR:BRN1!") == "ICEEUR:BRN1!"


def test_an_unqualified_code_carries_no_separator():
    """Neither spelling invents a prefix when there is no feed to qualify."""
    assert tradingview_overview_symbol("BRN1!") == "BRN1!"
    assert tradingview_chart_symbol("BRN1!") == "BRN1!"


def test_both_spellings_take_a_separate_exchange():
    assert tradingview_chart_symbol("BRN1!", "ICEEUR") == "ICEEUR:BRN1!"
    assert tradingview_overview_symbol("BRN1!", "ICEEUR") == "ICEEUR-BRN1!"


def test_an_embedded_feed_beats_a_separate_exchange_in_both_spellings():
    """The precedence rule the URL builders rely on, pinned on both surfaces."""
    assert tradingview_chart_symbol("ICEEUR:BRN1!", "NYMEX") == "ICEEUR:BRN1!"
    assert tradingview_overview_symbol("ICEEUR:BRN1!", "NYMEX") == "ICEEUR-BRN1!"
