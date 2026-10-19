"""Vendor symbol spelling.

`futureskit.notation` holds contract grammar: what a contract reference means,
which is identically true at any firm using any data vendor. This subpackage
holds the other thing — how a particular vendor happens to spell that contract.
Those spellings are pure functions with no I/O, but they are contingent facts
about Refinitiv or TradingView rather than facts about futures, and mixing the
two made one module answer two questions.

Import the spelling you need from its own module, so the import line says which
vendor a caller depends on::

    from futureskit.vendors.lseg import format_ric_contract
    from futureskit.vendors.tradingview import tradingview_chart_symbol

Nothing here is re-exported from the package root, and nothing here is imported
by `futureskit.notation`. URL assembly is not futureskit's job either: these
functions stop at the symbol.
"""
