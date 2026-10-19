"""LSEG (formerly Refinitiv) contract notation: the RIC symbology.

Vendor spelling, not contract grammar: see :mod:`futureskit.vendors`.
"""

import re

from futureskit.exceptions import InvalidMonthCodeError
from futureskit.notation import MONTH_CODES

# Refinitiv/LSEG RIC contract-year width, keyed by exchange.
#
# This is a per-venue convention, not a global one: CME Group venues carry a
# two-digit year while ICE carries one, so October 2026 is ``CLV26`` on NYMEX but
# ``LCOV6`` on ICE. Applying either rule universally silently produces RICs that
# resolve to nothing for the other half of the board - a failure mode that reads
# as a missing entitlement rather than a formatting bug.
#
# Neither width is universal across vendors either: TradingView spells the same
# contract with a full four-digit year (see futureskit.vendors.tradingview), so
# there are three live conventions and no safe default among them.
CME_GROUP_EXCHANGES = frozenset({'CME', 'NYMEX', 'COMEX', 'CBOT', 'NYBOT'})
ONE_DIGIT_YEAR_EXCHANGES = frozenset({'ICE'})

# Trailing month/year of a contract RIC, either venue width.
_RIC_CONTRACT_SUFFIX = re.compile(
    rf"(?P<month>[{''.join(MONTH_CODES)}])(?P<year>\d{{1,2}})$"
)


def ric_year_digits(exchange: str) -> int:
    """
    Return the RIC contract-year width for a futures venue.

    Matching is case-insensitive and ignores surrounding whitespace. An
    unregistered venue raises rather than falling back to a default: a guessed
    convention is wrong for roughly half the board and fails silently.

    Args:
        exchange: Venue name, e.g. 'NYMEX' or 'ICE'

    Returns:
        2 for CME Group venues, 1 for ICE

    Raises:
        ValueError: If no convention is registered for the venue
    """
    normalized = str(exchange or '').strip().upper()
    if normalized in CME_GROUP_EXCHANGES:
        return 2
    if normalized in ONE_DIGIT_YEAR_EXCHANGES:
        return 1
    raise ValueError(
        f"No RIC contract-year convention is registered for exchange "
        f"{exchange!r}"
    )


def format_ric_contract(ric_root: str, month_code: str, year: int,
                        exchange: str, delayed: bool = False) -> str:
    """
    Build a Refinitiv/LSEG contract RIC for one RIC root.

    Args:
        ric_root: The vendor RIC root, e.g. 'CL' or 'LCO'. This is a registry
            mapping rather than something derivable - 'BRN' is 'LCO' to LSEG.
        month_code: Futures month code, e.g. 'V' for October
        year: Four-digit contract year
        exchange: Venue name, which selects the contract-year width
        delayed: Prefix with '/', Refinitiv's delayed-quote convention. Leave
            false for a real-time entitlement, and for URL generation.

    Returns:
        The contract RIC, e.g. 'CLV26' on NYMEX or 'LCOV6' on ICE

    Raises:
        ValueError: If the root is empty, the year is not four digits, or the
            venue has no registered convention
        InvalidMonthCodeError: If the month code is not a futures month
    """
    root = str(ric_root or '').strip()
    if not root:
        raise ValueError("RIC root must not be empty")
    code = str(month_code or '').strip().upper()
    if code not in MONTH_CODES:
        raise InvalidMonthCodeError(f"Invalid futures month code {month_code!r}")
    if not 1000 <= int(year) <= 9999:
        raise ValueError(f"Contract year must be four digits, got {year!r}")
    year_text = str(int(year))[-ric_year_digits(exchange):]
    prefix = '/' if delayed else ''
    return f"{prefix}{root}{code}{year_text}"


def contract_code_from_ric(ric: str) -> str:
    """
    Return the month/year suffix from a contract RIC.

    The result preserves the venue convention it was built with, so '/CLV26'
    yields 'V26' while '/LCOV6' yields 'V6'. This is the inverse needed by
    consumers joining vendor rows back onto their own contract codes.

    Args:
        ric: A contract RIC, with or without the delayed '/' prefix

    Returns:
        The month/year suffix, e.g. 'V26'

    Raises:
        ValueError: If the RIC does not end in a futures contract code
    """
    match = _RIC_CONTRACT_SUFFIX.search(str(ric or '').strip())
    if match is None:
        raise ValueError(
            f"RIC {ric!r} does not end in a valid futures contract code"
        )
    return f"{match.group('month')}{match.group('year')}"
