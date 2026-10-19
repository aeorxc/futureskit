"""
Core futures notation parsing functionality.
"""

import re
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from datetime import date

from futureskit.exceptions import InvalidMonthCodeError, InvalidYearError

# Vendor symbol spelling lives in futureskit.vendors, never here. Contract
# grammar is identically true at any firm with any vendor; how Refinitiv or
# TradingView happens to spell a contract this year is not. This module must
# import nothing from futureskit.vendors — the dependency runs one way only,
# and tests/vendors/test_vendor_boundary.py pins it.


# Futures month codes mapping
MONTH_CODES = {
    'F': 1,   # January
    'G': 2,   # February  
    'H': 3,   # March
    'J': 4,   # April
    'K': 5,   # May
    'M': 6,   # June
    'N': 7,   # July
    'Q': 8,   # August
    'U': 9,   # September
    'V': 10,  # October
    'X': 11,  # November
    'Z': 12,  # December
}

# Reverse mapping for month codes
MONTH_TO_CODE = {v: k for k, v in MONTH_CODES.items()}

# Valid roll rules
ROLL_RULES = {
    'n': 'open_interest',
    'v': 'volume',
    'c': 'calendar',
    'fn': 'first_notice',
    'lt': 'last_trade',
}

@dataclass
class ParsedSymbol:
    """
    Represents a parsed futures symbol.
    
    Attributes:
        root: The commodity root symbol (e.g., 'BRN', 'CL')
        year: The contract year (4-digit) for regular futures
        month: The month code (e.g., 'F', 'Z') for regular futures
        is_continuous: True if this is a continuous contract
        roll_rule: The roll rule for continuous contracts ('n', 'v', 'c', etc.)
        contract_index: The contract position (1-based) for continuous contracts
        warnings: List of warnings encountered during parsing
        metadata: Additional metadata for future extensions
    """
    root: str
    year: Optional[int] = None
    month: Optional[str] = None
    is_continuous: bool = False
    roll_rule: Optional[str] = None
    contract_index: Optional[int] = None
    warnings: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    # Optional extended fields
    kind: Optional[str] = None            # 'contract' | 'continuous' | 'quarter' | 'calendar'
    quarter: Optional[int] = None         # 1..4
    calendar_year: Optional[int] = None   # YYYY
    
    def to_string(self) -> str:
        """Convert back to canonical string format."""
        if self.is_continuous:
            return f"{self.root}.{self.roll_rule}.{self.contract_index}"
        # Quarter canonical
        if self.quarter and self.year:
            return f"{self.root}_{self.year}Q{self.quarter}"
        # Calendar canonical
        if self.calendar_year:
            return f"{self.root}_CAL{self.calendar_year}"
        elif self.year and self.month:
            return f"{self.root}_{self.year}{self.month}"
        else:
            # Partial parse - return what we have
            parts = [self.root]
            if self.year:
                parts.append(f"_{self.year}")
            if self.month:
                parts.append(self.month)
            return "".join(parts)
    
    @property
    def delivery_month(self) -> Optional[date]:
        """The first of the delivery month, for a dated contract only.

        Quarters, calendars, continuous series and partial parses have no
        single delivery month and return ``None``. Only ``kind == 'contract'``
        answers, so a caller cannot silently take the front of a quarter strip
        as though it were a dated contract.

        Raises:
            InvalidMonthCodeError: If the contract carries a month that is not
                a futures month code. A dated contract with an unusable month
                is a parse defect, and returning ``None`` would hide it among
                the legitimately monthless kinds.
        """
        if self.kind != 'contract' or self.year is None or self.month is None:
            return None
        code = str(self.month).strip().upper()
        if code not in MONTH_CODES:
            raise InvalidMonthCodeError(
                f"Contract {self.to_string()!r} carries invalid futures month "
                f"code {self.month!r}"
            )
        return date(self.year, MONTH_CODES[code], 1)

    def to_date(self) -> Optional[date]:
        """Return :attr:`delivery_month`, mirroring :meth:`to_string`."""
        return self.delivery_month

    def is_valid(self) -> bool:
        """Check if this represents a fully valid symbol."""
        if self.is_continuous:
            return bool(self.root and self.roll_rule and self.contract_index)
        else:
            if self.quarter and self.year:
                return bool(self.root)
            if self.calendar_year:
                return bool(self.root)
            # For regular futures, also check that month code is valid
            return bool(self.root and self.year and self.month and self.month in MONTH_CODES)


class FuturesNotation:
    """
    Parse futures symbols into canonical format.
    
    Canonical formats:
    - Regular: ROOT_YYYYM (e.g., BRN_2026F)
    - Continuous: ROOT.rule.index (e.g., BRN.n.1)
    
    Indexing: 1-based (1 = front month, 2 = second month)
    
    Supported roll rules:
    - n: Open interest
    - v: Volume
    - c: Calendar
    - fn: First notice
    - lt: Last trade
    """
    
    # Regular futures patterns
    PATTERNS = [
        # Canonical format: BRN_2026F or OIL_DATED_2026F
        # Capture everything before _YYYYM as root
        re.compile(r'^(.+)_(\d{4})([FGHJKMNQUVXZ])$'),
        
        # Invalid canonical format (for error reporting): BRN_2026A
        re.compile(r'^(.+)_(\d{4})([A-Z])$'),
        
        # Short year format: BRN26F or BRNF26
        re.compile(r'^([A-Z]+)(\d{2})([FGHJKMNQUVXZ])$'),
        re.compile(r'^([A-Z]+)([FGHJKMNQUVXZ])(\d{2})$'),
        
        # With separators: BRN-26F, BRN 26F
        re.compile(r'^([A-Z]+)[-\s](\d{2})([FGHJKMNQUVXZ])$'),
        re.compile(r'^([A-Z]+)[-\s](\d{4})([FGHJKMNQUVXZ])$'),
    ]
    
    def __init__(self, today: date | None = None):
        self._today = today

    # Continuous contract pattern: BRN.n.1 or OIL_BRENT.n.1
    CONTINUOUS_PATTERN = re.compile(r'^(.+)\.([a-zA-Z]+)\.(\d+)$')
    # Strict canonical contract patterns.  These intentionally exclude vendor
    # prefixes and shorthand aliases accepted by ``parse``.
    CANONICAL_ROOT_PATTERN = r'[A-Z0-9]+(?:_[A-Z0-9]+)*'
    CANONICAL_MONTHLY_PATTERN = re.compile(
        rf'^({CANONICAL_ROOT_PATTERN})_(\d{{4}})([FGHJKMNQUVXZ])$'
    )
    CANONICAL_MONTHLY_SHAPE_PATTERN = re.compile(
        rf'^({CANONICAL_ROOT_PATTERN})_\d{{4}}[A-Z]+$'
    )
    CANONICAL_QUARTER_SHAPE_PATTERNS = (
        re.compile(rf'^({CANONICAL_ROOT_PATTERN})_\d{{4}}Q.+$'),
        re.compile(rf'^({CANONICAL_ROOT_PATTERN})_Q.+_\d{{4}}$'),
    )
    CANONICAL_CALENDAR_SHAPE_PATTERN = re.compile(
        rf'^({CANONICAL_ROOT_PATTERN})_CAL\d{{4}}.*$'
    )
    CANONICAL_QUARTER_PATTERN = re.compile(
        rf'^({CANONICAL_ROOT_PATTERN})_(\d{{4}})Q([1-4])$'
    )
    CANONICAL_ALTERNATE_QUARTER_PATTERN = re.compile(
        rf'^({CANONICAL_ROOT_PATTERN})_Q([1-4])_(\d{{4}})$'
    )
    CANONICAL_CALENDAR_PATTERN = re.compile(
        rf'^({CANONICAL_ROOT_PATTERN})_CAL(\d{{4}})$'
    )
    LEGACY_YEAR_MONTH_PATTERN = re.compile(
        rf'^({CANONICAL_ROOT_PATTERN})(\d{{2}})([FGHJKMNQUVXZ])$'
    )
    LEGACY_MONTH_YEAR_PATTERN = re.compile(
        rf'^({CANONICAL_ROOT_PATTERN})([FGHJKMNQUVXZ])(\d{{2}})$'
    )
    LEGACY_SEPARATED_YEAR_MONTH_PATTERN = re.compile(
        rf'^({CANONICAL_ROOT_PATTERN})[- ](\d{{2}}|\d{{4}})'
        rf'([FGHJKMNQUVXZ])$'
    )
    REFERENCE_CONTINUOUS_ROOT_PATTERN = (
        rf'{CANONICAL_ROOT_PATTERN}(?:\.{CANONICAL_ROOT_PATTERN})*'
    )
    REFERENCE_CONTINUOUS_PATTERN = re.compile(
        rf'^({REFERENCE_CONTINUOUS_ROOT_PATTERN})\.([A-Z]+)\.(\d+)$'
    )
    REFERENCE_CONTINUOUS_M_PATTERN = re.compile(
        rf'^({REFERENCE_CONTINUOUS_ROOT_PATTERN})_M(\d{{2}})$'
    )
    # Continuous M-notation: ROOT_M01
    CONTINUOUS_M_PATTERN = re.compile(r'^(.+)_M(\d{2})$')
    # Quarter patterns
    QUARTER_PATTERNS = [
        re.compile(r'^(.+)_(\d{4})Q([1-4])$'),
        re.compile(r'^(.+)_Q([1-4])_(\d{4})$'),
    ]
    # Calendar pattern
    CALENDAR_PATTERN = re.compile(r'^(.+)_CAL(\d{4})$')
    
    def parse(self, symbol: str) -> ParsedSymbol:
        """
        Parse a futures symbol into its components.
        
        Args:
            symbol: The symbol to parse
            
        Returns:
            ParsedSymbol with extracted components and any warnings
        """
        if not symbol:
            return ParsedSymbol(root="", warnings=["Empty symbol provided"])
        
        # Clean the symbol
        symbol_clean = symbol.strip()
        
        # Check for continuous contract first (preserve case for roll rule)
        if '.' in symbol_clean:
            parts = symbol_clean.split('.')
            if len(parts) == 3:
                # Reconstruct with uppercase root but preserve roll rule case
                normalized = f"{parts[0].upper()}.{parts[1].lower()}.{parts[2]}"
                continuous_match = self.CONTINUOUS_PATTERN.match(normalized)
                if continuous_match:
                    return self._parse_continuous(continuous_match, symbol_clean)

        # For non-continuous symbols, uppercase everything
        symbol = symbol_clean.upper()

        # Try M-notation continuous
        m_match = self.CONTINUOUS_M_PATTERN.match(symbol)
        if m_match:
            root = m_match.group(1)
            depth = int(m_match.group(2))
            return ParsedSymbol(root=root, is_continuous=True, roll_rule='n', contract_index=depth, kind='continuous')

        # Try regular futures patterns
        for pattern in self.PATTERNS:
            match = pattern.match(symbol)
            if match:
                return self._parse_regular(match)

        # Quarter
        for qp in self.QUARTER_PATTERNS:
            qmatch = qp.match(symbol)
            if qmatch:
                groups = qmatch.groups()
                # groups: (root, X, Y) where X/Y could be year or quarter
                if len(groups[1]) == 4 and groups[1].isdigit():
                    root, year_str, qstr = groups
                else:
                    root, qstr, year_str = groups
                return ParsedSymbol(root=root, year=int(year_str), quarter=int(qstr), kind='quarter')

        # Calendar
        cmatch = self.CALENDAR_PATTERN.match(symbol)
        if cmatch:
            root, y = cmatch.groups()
            return ParsedSymbol(root=root, calendar_year=int(y), kind='calendar')
        
        # Failed to parse - try to extract what we can
        return self._partial_parse(symbol)

    def parse_canonical_contract(self, symbol: str) -> Optional[ParsedSymbol]:
        """Parse a strict canonical contract reference.

        Unlike :meth:`parse`, this method accepts only canonical contract
        notation: ``ROOT_YYYYM``, either supported canonical quarter form, or
        ``ROOT_CALYYYY``.  It is intended for callers that must distinguish an
        exact contract from a root symbol without accidentally accepting a
        vendor alias.

        This is a recognition API, not a validator. Bare roots, non-canonical
        aliases, and malformed inputs all return ``None``. The method never
        guesses whether an otherwise valid root was intended as a contract.

        Args:
            symbol: Candidate canonical contract reference.

        Returns:
            A parsed contract, quarter, or calendar symbol; otherwise ``None``.

        """
        if not symbol:
            return None

        normalized = symbol.strip().upper()
        if not normalized:
            return None

        monthly_match = self.CANONICAL_MONTHLY_PATTERN.fullmatch(normalized)
        if monthly_match:
            root, year, month = monthly_match.groups()
            year_value = self._canonical_year(year)
            if year_value is None:
                return None
            return ParsedSymbol(
                root=root,
                year=year_value,
                month=month,
                kind='contract',
            )

        quarter_match = self.CANONICAL_QUARTER_PATTERN.fullmatch(normalized)
        if quarter_match:
            root, year, quarter = quarter_match.groups()
            year_value = self._canonical_year(year)
            if year_value is None:
                return None
            return ParsedSymbol(
                root=root,
                year=year_value,
                quarter=int(quarter),
                kind='quarter',
            )

        alternate_quarter_match = (
            self.CANONICAL_ALTERNATE_QUARTER_PATTERN.fullmatch(normalized)
        )
        if alternate_quarter_match:
            root, quarter, year = alternate_quarter_match.groups()
            year_value = self._canonical_year(year)
            if year_value is None:
                return None
            return ParsedSymbol(
                root=root,
                year=year_value,
                quarter=int(quarter),
                kind='quarter',
            )

        calendar_match = self.CANONICAL_CALENDAR_PATTERN.fullmatch(normalized)
        if calendar_match:
            root, year = calendar_match.groups()
            year_value = self._canonical_year(year)
            if year_value is None:
                return None
            return ParsedSymbol(
                root=root,
                calendar_year=year_value,
                kind='calendar',
            )

        return None

    def parse_contract_reference(self, symbol: str) -> Optional[ParsedSymbol]:
        """Recognize a supported, unqualified futures contract reference.

        This method extends :meth:`parse_canonical_contract` with the explicit
        legacy monthly and continuous aliases supported by FuturesKit. It is a
        recognition API: bare roots, malformed references, and provider- or
        feed-qualified symbols return ``None`` rather than being partially
        parsed or guessed.

        Supported references are:

        * canonical monthly, quarter, and calendar contracts;
        * monthly aliases such as ``BRN26Z``, ``BRNZ26``, ``BRN-26Z``, and
          ``BRN 26Z``;
        * continuous aliases such as ``BRN.n.1`` and ``BRN_M01``.

        Args:
            symbol: Candidate contract reference.

        Returns:
            A fully recognized symbol, or ``None``.

        """
        canonical = self.parse_canonical_contract(symbol)
        if canonical is not None:
            return canonical

        if not symbol:
            return None

        normalized = symbol.strip().upper()
        if not normalized:
            return None

        continuous_match = self.REFERENCE_CONTINUOUS_PATTERN.fullmatch(
            normalized
        )
        if continuous_match:
            root, roll_rule, contract_index = continuous_match.groups()
            roll_rule = roll_rule.lower()
            index_value = int(contract_index)
            if roll_rule not in ROLL_RULES or index_value < 1:
                return None
            return ParsedSymbol(
                root=root,
                is_continuous=True,
                roll_rule=roll_rule,
                contract_index=index_value,
                kind='continuous',
            )

        continuous_m_match = self.REFERENCE_CONTINUOUS_M_PATTERN.fullmatch(
            normalized
        )
        if continuous_m_match:
            root, contract_index = continuous_m_match.groups()
            index_value = int(contract_index)
            if index_value < 1:
                return None
            return ParsedSymbol(
                root=root,
                is_continuous=True,
                roll_rule='n',
                contract_index=index_value,
                kind='continuous',
            )

        # A malformed canonical-looking reference must not be reinterpreted
        # as a compact short-year alias with a longer root. For example,
        # ``CL_0999Z`` is not ``CL_09`` plus ``99Z``. These guards come after
        # explicit continuous recognition so an unambiguous continuous root
        # may itself contain calendar- or quarter-like text.
        if self.CANONICAL_MONTHLY_SHAPE_PATTERN.fullmatch(normalized):
            return None
        if any(
            pattern.fullmatch(normalized)
            for pattern in self.CANONICAL_QUARTER_SHAPE_PATTERNS
        ):
            return None
        if self.CANONICAL_CALENDAR_SHAPE_PATTERN.fullmatch(normalized):
            return None

        for pattern in (
            self.LEGACY_YEAR_MONTH_PATTERN,
            self.LEGACY_MONTH_YEAR_PATTERN,
        ):
            legacy_match = pattern.fullmatch(normalized)
            if legacy_match is None:
                continue

            root, first, second = legacy_match.groups()
            if not re.search(r'[A-Z]', root) or root[-1].isdigit():
                return None
            if first.isdigit():
                year, month = first, second
            else:
                month, year = first, second
            return ParsedSymbol(
                root=root,
                year=self._normalize_year(year),
                month=month,
                kind='contract',
            )

        separated_match = self.LEGACY_SEPARATED_YEAR_MONTH_PATTERN.fullmatch(
            normalized
        )
        if separated_match:
            root, year, month = separated_match.groups()
            if len(year) == 4:
                year_value = self._canonical_year(year)
                if year_value is None:
                    return None
            else:
                year_value = self._normalize_year(year)
            return ParsedSymbol(
                root=root,
                year=year_value,
                month=month,
                kind='contract',
            )

        return None

    @staticmethod
    def _canonical_year(year: str) -> Optional[int]:
        """Return a valid canonical year without applying alias normalization."""
        year_value = int(year)
        if year_value < 1000:
            return None
        return year_value
    
    def _parse_continuous(self, match: re.Match, original: str) -> ParsedSymbol:
        """Parse a continuous contract symbol."""
        root = match.group(1)
        roll_rule = match.group(2).lower()
        contract_index = int(match.group(3))
        
        warnings = []
        
        # Validate roll rule
        if roll_rule not in ROLL_RULES:
            warnings.append(f"Unknown roll rule: {roll_rule}")
        
        # Validate index (1-based)
        if contract_index < 1:
            warnings.append(f"Contract index should be 1-based, got: {contract_index}")
        
        return ParsedSymbol(
            root=root,
            is_continuous=True,
            roll_rule=roll_rule,
            contract_index=contract_index,
            warnings=warnings
        )
    
    def _parse_regular(self, match: re.Match) -> ParsedSymbol:
        """Parse a regular futures contract symbol."""
        groups = match.groups()
        root = groups[0]
        warnings = []
        
        # Handle different group orders (year-month vs month-year)
        if groups[1].isdigit():
            year_str = groups[1]
            month = groups[2]
        else:
            month = groups[1]
            year_str = groups[2]
        
        # Convert year to 4-digit
        year = self._normalize_year(year_str)
        
        # Validate month code
        if month not in MONTH_CODES:
            warnings.append(f"Invalid month code: {month}")
        
        return ParsedSymbol(
            root=root,
            year=year,
            month=month,
            warnings=warnings
        )
    
    def _normalize_year(self, year_str: str) -> int:
        """Convert 2-digit year to 4-digit year."""
        year = int(year_str)
        
        if year < 100:
            # 2-digit year - use 20-year rule
            current_year = (self._today or date.today()).year
            current_century = (current_year // 100) * 100
            current_year_2digit = current_year % 100
            
            # If the 2-digit year is greater than current + 10, assume it's in the past
            if year > current_year_2digit + 10:
                # e.g., if current is 2024 (24) and we see 99, that's 1999
                year = current_century - 100 + year
            else:
                # Otherwise it's in the current century
                # e.g., if current is 2024 (24) and we see 26, that's 2026
                year = current_century + year
        
        return year
    
    def _partial_parse(self, symbol: str) -> ParsedSymbol:
        """Attempt to extract what we can from an unparseable symbol."""
        warnings = [f"Could not fully parse symbol: {symbol}"]
        
        # Try to extract root (leading letters)
        root_match = re.match(r'^([A-Z]+)', symbol)
        root = root_match.group(1) if root_match else symbol
        
        # Try to find a year (4 consecutive digits)
        year_match = re.search(r'(\d{4})', symbol)
        year = int(year_match.group(1)) if year_match else None
        
        # Try to find a valid month code at the end or separated
        month = None
        # Look for month code at end of string or before/after separators
        for code in MONTH_CODES:
            # Check if it's at the end
            if symbol.endswith(code):
                month = code
                break
            # Check if it's separated by underscore or space
            if f'_{code}' in symbol or f' {code}' in symbol or f'-{code}' in symbol:
                month = code
                break
        
        return ParsedSymbol(
            root=root,
            year=year,
            month=month,
            warnings=warnings
        )
    
    def is_futures_symbol(self, symbol: str) -> bool:
        """
        Check if a symbol appears to be a futures symbol.
        
        Args:
            symbol: The symbol to check
            
        Returns:
            True if the symbol appears to be a futures symbol
        """
        try:
            parsed = self.parse(symbol)
            return parsed.is_valid() or parsed.is_continuous
        except Exception:
            return False
