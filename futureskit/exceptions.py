"""
Custom exceptions for futureskit.
"""


class FuturesKitError(Exception):
    """Base exception for all futureskit errors."""
    pass


class InvalidSymbolError(FuturesKitError):
    """Raised when a symbol cannot be parsed."""
    pass


class InvalidMonthCodeError(FuturesKitError):
    """Raised when an invalid month code is encountered."""
    pass


class InvalidYearError(FuturesKitError):
    """Raised when an invalid year is encountered."""
    pass


class InvalidRollRuleError(FuturesKitError):
    """Raised when an invalid roll rule is encountered."""
    pass