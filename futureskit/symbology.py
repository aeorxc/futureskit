"""
Symbol format conversion utilities.
"""

from typing import Optional
from futureskit.notation import ParsedSymbol, MONTH_CODES


class FeedConventions:
    """Common feed-specific conventions."""
    CME_PREFIX = "@"
    ICE_SUFFIX = ".L"
    
    @staticmethod
    def add_cme_prefix(symbol: str) -> str:
        """Add CME prefix to symbol."""
        return f"@{symbol}"
    
    @staticmethod
    def add_ice_suffix(symbol: str) -> str:
        """Add ICE suffix to symbol."""
        return f"{symbol}.L"


class SymbologyConverter:
    """Convert between different vendor symbol formats."""
    
    def to_cme_format(self, parsed: ParsedSymbol) -> Optional[str]:
        """
        Convert to CME format.
        
        Examples:
            BRN_2026F -> @BRN26F
            CL.n.1 -> @CL (for continuous front month)
        """
        if not parsed.root:
            return None
            
        if parsed.is_continuous:
            # CME doesn't have a standard continuous format
            # Return root with prefix for front month
            if parsed.contract_index == 1:
                return FeedConventions.add_cme_prefix(parsed.root)
            else:
                # Return with index suffix
                return FeedConventions.add_cme_prefix(f"{parsed.root}{parsed.contract_index}")
        
        if parsed.year and parsed.month:
            # Convert to 2-digit year
            year_2digit = parsed.year % 100
            symbol = f"{parsed.root}{year_2digit:02d}{parsed.month}"
            return FeedConventions.add_cme_prefix(symbol)
        
        return None
    
    def to_ice_format(self, parsed: ParsedSymbol) -> Optional[str]:
        """
        Convert to ICE format.
        
        Examples:
            BRN_2026F -> BRN26F
            BRN.n.1 -> BRN (for continuous front month)
        """
        if not parsed.root:
            return None
            
        if parsed.is_continuous:
            # ICE typically uses just root for front month
            if parsed.contract_index == 1:
                return parsed.root
            else:
                # No standard for other months
                return f"{parsed.root}M{parsed.contract_index}"
        
        if parsed.year and parsed.month:
            # Convert to 2-digit year
            year_2digit = parsed.year % 100
            return f"{parsed.root}{year_2digit:02d}{parsed.month}"
        
        return None
    
    def to_bloomberg_format(self, parsed: ParsedSymbol) -> Optional[str]:
        """
        Convert to Bloomberg format.
        
        Examples:
            BRN_2026F -> CO1F6 Comdty (Brent specific)
            CL_2026F -> CL1F6 Comdty (WTI specific)
            
        Note: This is commodity-specific and requires additional mapping.
        """
        if not parsed.root:
            return None
        
        # Bloomberg uses commodity-specific codes
        # This is a simplified example
        bloomberg_root_map = {
            'BRN': 'CO',  # Brent
            'CL': 'CL',   # WTI
            'NG': 'NG',   # Natural Gas
            'HO': 'HO',   # Heating Oil
            'RB': 'XB',   # RBOB Gasoline
        }
        
        bb_root = bloomberg_root_map.get(parsed.root, parsed.root)
        
        if parsed.is_continuous:
            # Bloomberg continuous format: CO1, CO2, etc.
            return f"{bb_root}{parsed.contract_index} Comdty"
        
        if parsed.year and parsed.month:
            # Bloomberg uses single letter month + single digit year
            year_1digit = parsed.year % 10
            return f"{bb_root}{parsed.month}{year_1digit} Comdty"
        
        return None
    
    def to_short_year_format(self, parsed: ParsedSymbol) -> Optional[str]:
        """
        Convert to 2-digit year format.
        
        Examples:
            BRN_2026F -> BRN26F
        """
        if not parsed.root or not parsed.year or not parsed.month:
            return None
            
        year_2digit = parsed.year % 100
        return f"{parsed.root}{year_2digit:02d}{parsed.month}"
    
    def to_marketplace_continuous(self, parsed: ParsedSymbol) -> Optional[str]:
        """
        Convert continuous notation to marketplace format.
        
        Examples:
            BRN.n.1 -> BRN_001_MONTH
            BRN.n.3 -> BRN_003_MONTH
        """
        if not parsed.is_continuous or not parsed.contract_index:
            return None
            
        return f"{parsed.root}_{parsed.contract_index:03d}_MONTH"