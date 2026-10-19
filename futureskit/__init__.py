"""
futureskit - A Python library for parsing and working with futures contract symbols and notation.
"""

from futureskit import forwards
from futureskit.forwards.continuous import (
    generate_multiple_continuous_series,
    generate_series,
)
from futureskit.forwards.rollspec import Adjustment, ExpiryOffset, RollSpec
from futureskit.forwards.schema import validate_contract_matrix, validate_expiry_dates
from futureskit.notation import (
    FuturesNotation,
    ParsedSymbol,
    MONTH_CODES,
    MONTH_TO_CODE,
)

# Vendor symbol spelling is deliberately NOT re-exported here. Import it from
# the vendor module that owns it, so an import line names the vendor a caller
# depends on:
#
#     from futureskit.vendors.lseg import format_ric_contract
#     from futureskit.vendors.tradingview import tradingview_chart_symbol
from futureskit.exceptions import (
    FuturesKitError,
    InvalidSymbolError,
    InvalidMonthCodeError,
    InvalidYearError,
)

__all__ = [
    # Forwards DataFrame surface
    "forwards",
    "RollSpec",
    "Adjustment",
    "ExpiryOffset",
    "generate_series",
    "generate_multiple_continuous_series",
    "validate_contract_matrix",
    "validate_expiry_dates",
    # Notation parsing
    "FuturesNotation",
    "ParsedSymbol",
    "MONTH_CODES",
    "MONTH_TO_CODE",
    # Exceptions
    "FuturesKitError",
    "InvalidSymbolError",
    "InvalidMonthCodeError",
    "InvalidYearError",
]
