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

logger = logging.getLogger(__name__)


@dataclass
class FuturesContract:
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
        if self._price_data is not None and name in self._price_data.columns:
            return self._price_data[name]
        if name in self._metadata:
            value = self._metadata[name]
            if any(d in name for d in ['date', 'expiry', 'delivery']) and isinstance(value, str):
                try:
                    return pd.to_datetime(value).date()
                except (ValueError, TypeError):
                    pass
            return value
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
