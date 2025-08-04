"""
Core futures notation parsing functionality.
"""

import re
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from datetime import datetime

from futureskit.exceptions import InvalidMonthCodeError, InvalidYearError, InvalidRollRuleError


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
    
    def to_string(self) -> str:
        """Convert back to canonical string format."""
        if self.is_continuous:
            return f"{self.root}.{self.roll_rule}.{self.contract_index}"
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
    
    def is_valid(self) -> bool:
        """Check if this represents a fully valid symbol."""
        if self.is_continuous:
            return bool(self.root and self.roll_rule and self.contract_index)
        else:
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
        # Canonical format: BRN_2026F
        re.compile(r'^([A-Z]+)_(\d{4})([FGHJKMNQUVXZ])$'),
        
        # Invalid canonical format (for error reporting): BRN_2026A
        re.compile(r'^([A-Z]+)_(\d{4})([A-Z])$'),
        
        # Short year format: BRN26F or BRNF26
        re.compile(r'^([A-Z]+)(\d{2})([FGHJKMNQUVXZ])$'),
        re.compile(r'^([A-Z]+)([FGHJKMNQUVXZ])(\d{2})$'),
        
        # With separators: BRN-26F, BRN 26F
        re.compile(r'^([A-Z]+)[-\s](\d{2})([FGHJKMNQUVXZ])$'),
        re.compile(r'^([A-Z]+)[-\s](\d{4})([FGHJKMNQUVXZ])$'),
    ]
    
    # Continuous contract pattern: BRN.n.1
    CONTINUOUS_PATTERN = re.compile(r'^([A-Z]+)\.([a-zA-Z]+)\.(\d+)$')
    
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
        
        # Try regular futures patterns
        for pattern in self.PATTERNS:
            match = pattern.match(symbol)
            if match:
                return self._parse_regular(match)
        
        # Failed to parse - try to extract what we can
        return self._partial_parse(symbol)
    
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
            current_year = datetime.now().year
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