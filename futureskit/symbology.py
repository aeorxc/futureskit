"""
Symbol format conversion utilities.
"""

from typing import Optional, Dict
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
    
    @staticmethod
    def to_cme_format(parsed: ParsedSymbol, vendor_map: Optional[Dict[str, str]] = None) -> Optional[str]:
        """
        Convert to CME format.
        
        Examples:
            BRN_2026F -> @BRN26F
            CL.n.1 -> @CL (for continuous front month)
        """
        vendor_map = vendor_map or {}
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
    
    @staticmethod
    def to_ice_format(parsed: ParsedSymbol, vendor_map: Optional[Dict[str, str]] = None) -> Optional[str]:
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
    
    @staticmethod
    def to_bloomberg_format(parsed: ParsedSymbol, vendor_map: Optional[Dict[str, str]] = None) -> Optional[str]:
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
    
    @staticmethod
    def to_short_year_format(parsed: ParsedSymbol, vendor_map: Optional[Dict[str, str]] = None) -> Optional[str]:
        """
        Convert to 2-digit year format.
        
        Examples:
            BRN_2026F -> BRN26F
        """
        if not parsed.root or not parsed.year or not parsed.month:
            return None
            
        year_2digit = parsed.year % 100
        return f"{parsed.root}{year_2digit:02d}{parsed.month}"
    
    @staticmethod
    def to_marketplace_continuous(parsed: ParsedSymbol, vendor_map: Optional[Dict[str, str]] = None) -> Optional[str]:
        """
        Convert continuous notation to marketplace format.
        
        Examples:
            BRN.n.1 -> BRN_001_MONTH
            BRN.n.3 -> BRN_003_MONTH
        """
        if not parsed.is_continuous or not parsed.contract_index:
            return None
            
        return f"{parsed.root}_{parsed.contract_index:03d}_MONTH"
    
    @staticmethod
    def to_tradingview_format(parsed: ParsedSymbol, 
                            vendor_map: Optional[Dict[str, str]] = None,
                            include_feed: bool = False) -> Optional[str]:
        """
        Convert to TradingView format using vendor mappings.
        
        Args:
            parsed: ParsedSymbol to convert
            vendor_map: Optional vendor-specific symbol mappings
            include_feed: If True, include exchange feed prefix (e.g., 'ICEEUR:')
        
        Examples (with vendor_map):
            BRN_2026F -> BRNH26 (or ICEEUR:BRNH26 with feed)
            BRN.n.1 -> BRN1! (or ICEEUR:BRN1! with feed)
            
        Examples (without vendor_map, using root):
            CL_2026F -> CLH26
            CL.n.1 -> CL1!
        """
        vendor_map = vendor_map or {}
        if not parsed.root:
            return None
        
        # Get TradingView-specific root symbol (default to parsed.root)
        tv_root = vendor_map.get('tradingview_symbol', parsed.root)
        tv_feed = vendor_map.get('tradingview_exchange', '')
        
        if parsed.is_continuous:
            # TradingView continuous format: BRN1!, CL2!
            symbol = f"{tv_root}{parsed.contract_index}!"
        elif parsed.year and parsed.month:
            # TradingView specific contract: BRNH26 (2-digit year)
            year_2digit = parsed.year % 100
            symbol = f"{tv_root}{parsed.month}{year_2digit:02d}"
        else:
            return None
        
        if include_feed and tv_feed:
            return f"{tv_feed}:{symbol}"
        return symbol
    
    @staticmethod
    def to_refinitiv_format(parsed: ParsedSymbol, 
                          vendor_map: Optional[Dict[str, str]] = None) -> Optional[str]:
        """
        Convert to Refinitiv RIC format using vendor mappings.
        
        Args:
            parsed: ParsedSymbol to convert
            vendor_map: Optional vendor-specific symbol mappings
        
        Examples (with vendor_map):
            BRN_2026F -> LCOF6 (using refinitiv_symbol: 'LCO')
            BRN.n.1 -> LCOc1
            
        Examples (without vendor_map):
            CL_2026F -> CLF6
            CL.n.1 -> CLc1
        """
        vendor_map = vendor_map or {}
        if not parsed.root:
            return None
        
        # Get Refinitiv-specific root (e.g., BRN -> LCO)
        refinitiv_root = vendor_map.get('refinitiv_symbol', parsed.root)
        
        if parsed.is_continuous:
            # Refinitiv continuous: LCOc1, CLc2
            return f"{refinitiv_root}c{parsed.contract_index}"
        elif parsed.year and parsed.month:
            # Refinitiv specific contract: LCOF6 (single digit year)
            year_1digit = parsed.year % 10
            return f"{refinitiv_root}{parsed.month}{year_1digit}"
        
        return None
    
    @staticmethod
    def to_marketplace_format(parsed: ParsedSymbol,
                            vendor_map: Optional[Dict[str, str]] = None,
                            include_feed: bool = True) -> Optional[str]:
        """
        Convert to marketplace format using vendor mappings.
        
        Args:
            parsed: ParsedSymbol to convert
            vendor_map: Optional vendor-specific symbol mappings
            include_feed: If True, include feed prefix (e.g., 'ICE_EuroFutures:')
        
        Examples:
            BRN_2026F -> ICE_EuroFutures:BRN_2026F
            BRN.n.1 -> ICE_EuroFutures:BRN_001_MONTH
        """
        vendor_map = vendor_map or {}
        if not parsed.root:
            return None
        
        mp_root = vendor_map.get('marketplace_symbol', parsed.root)
        mp_feed = vendor_map.get('marketplace_feed', '')
        
        if parsed.is_continuous:
            symbol = f"{mp_root}_{parsed.contract_index:03d}_MONTH"
        elif parsed.year and parsed.month:
            symbol = f"{mp_root}_{parsed.year}{parsed.month}"
        else:
            symbol = mp_root
        
        if include_feed and mp_feed:
            return f"{mp_feed}:{symbol}"
        return symbol
    
    # High-level convenience methods that build ParsedSymbol internally
    
    @staticmethod
    def tradingview(root_symbol: str,
                   vendor_map: Optional[Dict[str, str]] = None,
                   year: Optional[int] = None,
                   month: Optional[str] = None,
                   continuous_index: Optional[int] = None,
                   include_feed: bool = True) -> str:
        """
        High-level method to get TradingView format.
        
        Args:
            root_symbol: The commodity root symbol (e.g., 'BRN', 'CL')
            vendor_map: Optional vendor-specific symbol mappings
            year: Year for specific contract (e.g., 2026)
            month: Month code for specific contract (e.g., 'H' for March)
            continuous_index: Index for continuous contract (1=front, 2=second, etc.)
            include_feed: If True, include exchange feed prefix (e.g., 'ICEEUR:')
        
        Returns:
            TradingView formatted symbol string
        
        Examples:
            SymbologyConverter.tradingview('BRN', vendor_map, 2026, 'H')  # "ICEEUR:BRNH26"
            SymbologyConverter.tradingview('BRN', vendor_map, continuous_index=1)  # "ICEEUR:BRN1!"
        """
        parsed = SymbologyConverter._build_parsed_symbol(
            root_symbol, year, month, continuous_index, roll_rule='v'
        )
        return SymbologyConverter.to_tradingview_format(parsed, vendor_map, include_feed)
    
    @staticmethod
    def refinitiv(root_symbol: str,
                 vendor_map: Optional[Dict[str, str]] = None,
                 year: Optional[int] = None,
                 month: Optional[str] = None,
                 continuous_index: Optional[int] = None) -> str:
        """
        High-level method to get Refinitiv RIC format.
        
        Args:
            root_symbol: The commodity root symbol (e.g., 'BRN', 'CL')
            vendor_map: Optional vendor-specific symbol mappings
            year: Year for specific contract (e.g., 2026)
            month: Month code for specific contract (e.g., 'H' for March)
            continuous_index: Index for continuous contract (1=front, 2=second, etc.)
        
        Returns:
            Refinitiv RIC formatted symbol string
        
        Examples:
            SymbologyConverter.refinitiv('BRN', vendor_map, 2026, 'H')  # "LCOH6"
            SymbologyConverter.refinitiv('BRN', vendor_map, continuous_index=1)  # "LCOc1"
        """
        parsed = SymbologyConverter._build_parsed_symbol(
            root_symbol, year, month, continuous_index, roll_rule='v'
        )
        return SymbologyConverter.to_refinitiv_format(parsed, vendor_map)
    
    @staticmethod
    def marketplace(root_symbol: str,
                   vendor_map: Optional[Dict[str, str]] = None,
                   year: Optional[int] = None,
                   month: Optional[str] = None,
                   continuous_index: Optional[int] = None,
                   include_feed: bool = True) -> str:
        """
        High-level method to get marketplace format.
        
        Args:
            root_symbol: The commodity root symbol (e.g., 'BRN', 'CL')
            vendor_map: Optional vendor-specific symbol mappings
            year: Year for specific contract (e.g., 2026)
            month: Month code for specific contract (e.g., 'H' for March)
            continuous_index: Index for continuous contract (1=front, 2=second, etc.)
            include_feed: If True, include feed prefix (e.g., 'ICE_EuroFutures:')
        
        Returns:
            Marketplace formatted symbol string
        
        Examples:
            SymbologyConverter.marketplace('BRN', vendor_map, 2026, 'H')  # "ICE_EuroFutures:BRN_2026H"
            SymbologyConverter.marketplace('BRN', vendor_map, continuous_index=1)  # "ICE_EuroFutures:BRN_001_MONTH"
        """
        parsed = SymbologyConverter._build_parsed_symbol(
            root_symbol, year, month, continuous_index, roll_rule='n'
        )
        return SymbologyConverter.to_marketplace_format(parsed, vendor_map, include_feed)
    
    @staticmethod
    def cme(root_symbol: str,
           vendor_map: Optional[Dict[str, str]] = None,
           year: Optional[int] = None,
           month: Optional[str] = None,
           continuous_index: Optional[int] = None) -> str:
        """
        High-level method to get CME format.
        
        Args:
            root_symbol: The commodity root symbol (e.g., 'CL', 'NG')
            vendor_map: Optional vendor-specific symbol mappings
            year: Year for specific contract (e.g., 2026)
            month: Month code for specific contract (e.g., 'H' for March)
            continuous_index: Index for continuous contract (1=front, 2=second, etc.)
        
        Returns:
            CME formatted symbol string
        
        Examples:
            SymbologyConverter.cme('CL', vendor_map, 2026, 'H')  # "@CLH26"
            SymbologyConverter.cme('CL', vendor_map, continuous_index=1)  # "@CL"
        """
        parsed = SymbologyConverter._build_parsed_symbol(
            root_symbol, year, month, continuous_index, roll_rule='v'
        )
        return SymbologyConverter.to_cme_format(parsed, vendor_map)
    
    @staticmethod
    def bloomberg(root_symbol: str,
                 vendor_map: Optional[Dict[str, str]] = None,
                 year: Optional[int] = None,
                 month: Optional[str] = None,
                 continuous_index: Optional[int] = None) -> str:
        """
        High-level method to get Bloomberg format.
        
        Args:
            root_symbol: The commodity root symbol (e.g., 'BRN', 'CL')
            vendor_map: Optional vendor-specific symbol mappings
            year: Year for specific contract (e.g., 2026)
            month: Month code for specific contract (e.g., 'H' for March)
            continuous_index: Index for continuous contract (1=front, 2=second, etc.)
        
        Returns:
            Bloomberg formatted symbol string
        
        Examples:
            SymbologyConverter.bloomberg('BRN', vendor_map, 2026, 'H')  # "COH6 Comdty"
            SymbologyConverter.bloomberg('BRN', vendor_map, continuous_index=1)  # "CO1 Comdty"
        """
        parsed = SymbologyConverter._build_parsed_symbol(
            root_symbol, year, month, continuous_index, roll_rule='v'
        )
        return SymbologyConverter.to_bloomberg_format(parsed, vendor_map)
    
    @staticmethod
    def _build_parsed_symbol(root_symbol: str,
                           year: Optional[int] = None,
                           month: Optional[str] = None,
                           continuous_index: Optional[int] = None,
                           roll_rule: str = 'v') -> ParsedSymbol:
        """
        Build a ParsedSymbol from the given parameters.
        
        Args:
            root_symbol: The commodity root symbol
            year: Year for specific contract
            month: Month code for specific contract
            continuous_index: Index for continuous contract
            roll_rule: Roll rule for continuous contracts
        
        Returns:
            ParsedSymbol object
        """
        if continuous_index:
            # Create continuous ParsedSymbol
            return ParsedSymbol(
                root=root_symbol,
                is_continuous=True,
                contract_index=continuous_index,
                roll_rule=roll_rule
            )
        elif year and month:
            # Create specific contract ParsedSymbol
            return ParsedSymbol(
                root=root_symbol,
                year=year,
                month=month
            )
        else:
            # Default to front month continuous
            return ParsedSymbol(
                root=root_symbol,
                is_continuous=True,
                contract_index=1,
                roll_rule=roll_rule
            )