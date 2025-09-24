"""
Futures contract representations

This module provides classes for representing individual futures contracts
and collections of contracts (curves/chains).
"""

from typing import List, Optional, Dict, Any
from datetime import date
from dataclasses import dataclass, field
import logging
import pandas as pd

from futureskit.notation import MONTH_CODES, MONTH_TO_CODE
from futureskit.conversion import ConvertibleMixin

logger = logging.getLogger(__name__)


@dataclass
class FuturesContract(ConvertibleMixin):
    """
    Represents a single, data-rich futures contract.

    This is the primary object for accessing price and metadata for a specific
    contract (e.g., CLH26). It uses dynamic properties to allow access to any
    field provided by the data source.
    """
    root_symbol: str
    year: int
    month_code: str
    exchange: Optional[str] = None
    feed: Optional[str] = None
    datasource: Optional[Any] = None
    future: Optional[Any] = None  # Reference to parent Future object

    # Internal state
    _metadata: Dict[str, Any] = field(default_factory=dict, init=False, repr=False)
    _price_data: Optional[pd.DataFrame] = field(default=None, init=False, repr=False)

    def __post_init__(self):
        """Initialize and load data if a datasource is provided."""
        if self.datasource:
            self._load_data()

    def _load_data(self):
        """Load contract metadata and price data from the datasource."""
        if not self.datasource:
            return
        try:
            if hasattr(self.datasource, 'get_contract_specs'):
                self._metadata = self.datasource.get_contract_specs(self.root_symbol, self.exchange)
            if hasattr(self.datasource, 'get_futures_contract'):
                self._price_data = self.datasource.get_futures_contract(self.root_symbol, self.year, self.month_code)
        except Exception as e:
            logger.warning(f"Failed to load data for {self}: {e}")

    def __getattr__(self, name: str) -> Any:
        """Dynamic attribute access for price series and metadata."""
        # Prevent infinite recursion for properties we've added
        if name in ('unit', 'currency', '_conversion_context', '_metadata', '_price_data'):
            raise AttributeError(f"'{type(self).__name__}' object has no attribute '{name}'")

        # Use object.__getattribute__ to avoid recursion
        try:
            price_data = object.__getattribute__(self, '_price_data')
            if price_data is not None and name in price_data.columns:
                return price_data[name]
        except AttributeError:
            pass

        try:
            metadata = object.__getattribute__(self, '_metadata')
            if name in metadata:
                value = metadata[name]
                if any(d in name for d in ['date', 'expiry', 'delivery']) and isinstance(value, str):
                    try:
                        return pd.to_datetime(value).date()
                    except (ValueError, TypeError):
                        pass
                return value
        except AttributeError:
            pass

        raise AttributeError(f"'{type(self).__name__}' object has no attribute '{name}'")

    def __getitem__(self, key: str) -> Any:
        """Dictionary-style access to fields."""
        try:
            return getattr(self, key)
        except AttributeError:
            raise KeyError(f"Field '{key}' not found in futures data for {self}")

    @property
    def month_num(self) -> int:
        return MONTH_CODES.get(self.month_code.upper(), 0)

    @property
    def delivery_date(self) -> date:
        return date(self.year, self.month_num, 1)

    def to_canonical(self) -> str:
        return f"{self.root_symbol}_{self.year}{self.month_code}"

    def to_short_year(self) -> str:
        year_2digit = str(self.year)[-2:]
        return f"{self.root_symbol}{year_2digit}{self.month_code}"

    def __str__(self) -> str:
        return self.to_canonical()

    @property
    def formats(self):
        """
        Returns a namespace with vendor format methods for this specific contract.
        
        Examples:
            contract.formats.tradingview()  # "ICEEUR:BRNH25"
            contract.formats.refinitiv()    # "LCOH5"
        """
        from futureskit.symbology import SymbologyConverter
        from functools import partial
        
        # Get vendor_map from parent Future object if available
        vendor_map = self.future.vendor_map if self.future and hasattr(self.future, 'vendor_map') else {}
        
        # Create a namespace object with bound methods
        class Formats:
            pass
        
        formats = Formats()
        
        # Bind each method with the contract's specific year/month
        formats.tradingview = partial(SymbologyConverter.tradingview, self.root_symbol, vendor_map, self.year, self.month_code)
        formats.refinitiv = partial(SymbologyConverter.refinitiv, self.root_symbol, vendor_map, self.year, self.month_code)
        formats.marketplace = partial(SymbologyConverter.marketplace, self.root_symbol, vendor_map, self.year, self.month_code)
        formats.cme = partial(SymbologyConverter.cme, self.root_symbol, vendor_map, self.year, self.month_code)
        formats.bloomberg = partial(SymbologyConverter.bloomberg, self.root_symbol, vendor_map, self.year, self.month_code)
        
        return formats
    
    def get_urls(self) -> Dict[str, str]:
        """
        Get URLs for this contract from the datasource.
        
        Returns:
            Dictionary of service names to URLs
        """
        if not self.datasource or not hasattr(self.datasource, 'get_contract_url'):
            return {}
        
        # Get vendor_map from parent Future object if available
        vendor_map = self.future.vendor_map if self.future and hasattr(self.future, 'vendor_map') else {}
        
        # Delegate to datasource - it handles all vendor-specific logic internally
        return self.datasource.get_contract_url(self.root_symbol, self.year, self.month_code, vendor_map)
    
    def to_dict(self, include_urls: bool = False) -> Dict[str, Any]:
        """
        Convert contract to dictionary representation.
        
        Args:
            include_urls: Whether to include URLs in the output
            
        Returns:
            Dictionary with contract data
        """
        data = {
            'root_symbol': self.root_symbol,
            'year': self.year,
            'month_code': self.month_code,
            'month_num': self.month_num,
            'delivery_date': self.delivery_date.isoformat() if self.delivery_date else None,
            'canonical': self.to_canonical(),
            'short_year': self.to_short_year(),
        }
        
        # Add exchange and feed if available
        if self.exchange:
            data['exchange'] = self.exchange
        if self.feed:
            data['feed'] = self.feed
            
        # Add metadata if loaded
        if self._metadata:
            data['metadata'] = self._metadata
            
        # Add URLs if requested
        if include_urls:
            data['urls'] = self.get_urls()
            
        return data

    def __repr__(self) -> str:
        return f"FuturesContract({self.root_symbol!r}, {self.year}, {self.month_code!r})"

    def __eq__(self, other) -> bool:
        if not isinstance(other, FuturesContract):
            return False
        return self.root_symbol == other.root_symbol and self.year == other.year and self.month_code == other.month_code

    def __lt__(self, other) -> bool:
        if not isinstance(other, FuturesContract):
            return NotImplemented
        return self.delivery_date < other.delivery_date

    # ConvertibleMixin helper methods
    def _get_commodity_group(self) -> str:
        """Get commodity group for conversions"""
        if self.future and hasattr(self.future, 'metadata'):
            return self.future.metadata.get('commodity_group', 'crude')
        return self._metadata.get('commodity_group', 'crude')

    def _get_contract_size(self) -> Optional[float]:
        """Get contract size from metadata"""
        if self.future and hasattr(self.future, 'metadata'):
            return self.future.metadata.get('Contract_Size')
        return self._metadata.get('Contract_Size')

    def _get_contract_unit(self) -> str:
        """Get contract unit from metadata"""
        # Avoid recursion - don't call self.unit here
        if self.future and hasattr(self.future, 'metadata'):
            # Get current unit without recursion
            current_unit = self.future.metadata.get('unit', 'bbl')
            return self.future.metadata.get('contract_unit', current_unit)
        current_unit = self._metadata.get('unit', 'bbl')
        return self._metadata.get('contract_unit', current_unit)

    def _get_symbol(self) -> str:
        """Get symbol for logging/error messages"""
        return f"{self.root_symbol}_{self.year}{self.month_code}"

    @property
    def unit(self) -> str:
        """Current unit from metadata or conversion context"""
        # Check for conversion context first (avoid attribute lookup)
        if hasattr(self, '_conversion_context'):
            context = object.__getattribute__(self, '_conversion_context')
            if context and context.current_unit:
                return context.current_unit
        # Check future metadata
        future = object.__getattribute__(self, 'future')
        if future and hasattr(future, 'metadata'):
            return future.metadata.get('unit', 'bbl')
        # Check internal metadata
        metadata = object.__getattribute__(self, '_metadata')
        return metadata.get('unit', 'bbl') if metadata else 'bbl'

    @property
    def currency(self) -> str:
        """Current currency from metadata or conversion context"""
        # Check for conversion context first (avoid attribute lookup)
        if hasattr(self, '_conversion_context'):
            context = object.__getattribute__(self, '_conversion_context')
            if context and context.current_currency:
                return context.current_currency
        # Check future metadata
        future = object.__getattribute__(self, 'future')
        if future and hasattr(future, 'metadata'):
            return future.metadata.get('currency', 'USD')
        # Check internal metadata
        metadata = object.__getattribute__(self, '_metadata')
        return metadata.get('currency', 'USD') if metadata else 'USD'

    @property
    def data(self) -> Optional[pd.DataFrame]:
        """Access to price data for conversion operations"""
        return self._price_data

    @data.setter
    def data(self, value: pd.DataFrame):
        """Set price data (used by conversion operations)"""
        self._price_data = value


@dataclass
class ContractChain:
    """Represents a chain/curve of futures contracts for a single commodity."""
    root_symbol: str
    contracts: List[FuturesContract]
    exchange: Optional[str] = None

    def __post_init__(self):
        self.contracts = sorted(self.contracts, key=lambda c: c.delivery_date)

    def get_contract(self, year: int, month_code: str) -> Optional[FuturesContract]:
        month_code = month_code.upper()
        for contract in self.contracts:
            if contract.year == year and contract.month_code == month_code:
                return contract
        return None

    def get_front_month(self, as_of: Optional[date] = None) -> Optional[FuturesContract]:
        as_of = as_of or date.today()
        future_contracts = [c for c in self.contracts if c.delivery_date >= as_of]
        return min(future_contracts, key=lambda c: c.delivery_date) if future_contracts else None

    def get_nth_contract(self, n: int, as_of: Optional[date] = None) -> Optional[FuturesContract]:
        as_of = as_of or date.today()
        future_contracts = [c for c in self.contracts if c.delivery_date >= as_of]
        return future_contracts[n - 1] if len(future_contracts) >= n else None

    def __len__(self) -> int:
        return len(self.contracts)

    def __iter__(self):
        return iter(self.contracts)

    def __getitem__(self, index):
        return self.contracts[index]
