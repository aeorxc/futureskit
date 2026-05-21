"""
futureskit - A Python library for parsing and working with futures contract symbols and notation.
"""

try:
    from futureskit._version import version as __version__
except ImportError:
    __version__ = "0.0.0+unknown"

from futureskit.notation import (
    FuturesNotation,
    ParsedSymbol,
    MONTH_CODES,
    MONTH_TO_CODE,
)
from futureskit.symbology import SymbologyConverter
from futureskit.contracts import FuturesContract, ContractChain
from futureskit.futures import Future, ContinuousFuture
from futureskit.continuous import (
    RollRule,
    RollDate,
    RollSchedule,
    AdjustmentMethod,
    ContinuousFutureBuilder,
)
from futureskit.datasources import FuturesDataSource
from futureskit.conversion import ConvertibleMixin, ConversionContext
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
    "RollSchedule",
    "AdjustmentMethod",
    "ContinuousFutureBuilder",
    # Data sources
    "FuturesDataSource",
    # Conversion utilities
    "ConvertibleMixin",
    "ConversionContext",
    # Exceptions
    "FuturesKitError",
    "InvalidSymbolError",
    "InvalidMonthCodeError",
    "InvalidYearError",
]
