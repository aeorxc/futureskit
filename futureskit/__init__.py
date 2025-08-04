"""
futureskit - A Python library for parsing and working with futures contract symbols and notation.
"""

__version__ = "0.1.0"

from futureskit.notation import FuturesNotation, ParsedSymbol, MONTH_CODES, MONTH_TO_CODE
from futureskit.symbology import SymbologyConverter
from futureskit.contracts import FuturesContract, ContractChain
from futureskit.futures import Future, ContinuousFuture, RollRule, RollDate
from futureskit.datasources import FuturesDataSource
from futureskit.exceptions import (
    FuturesKitError,
    InvalidSymbolError,
    InvalidMonthCodeError,
    InvalidYearError,
)

__all__ = [
    # Main futures classes
    "Future",
    "ContinuousFuture",
    # Notation parsing
    "FuturesNotation",
    "ParsedSymbol",
    # Symbology conversion
    "SymbologyConverter",
    # Contract representations
    "FuturesContract",
    "ContractChain",
    "MONTH_CODES",
    "MONTH_TO_CODE",
    # Continuous futures
    "RollRule", 
    "RollDate",
    # Data sources
    "FuturesDataSource",
    # Exceptions
    "FuturesKitError",
    "InvalidSymbolError",
    "InvalidMonthCodeError",
    "InvalidYearError",
]
