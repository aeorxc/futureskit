"""
Main Futures classes that provide a high-level object interface.

This module provides the top-level Future class, which acts as a factory
for specific FuturesContract and ContinuousFuture objects.
"""

from typing import Optional, Any, List, Union, Tuple, Dict
from datetime import date, timedelta
from dataclasses import dataclass
from enum import Enum
import pandas as pd
import logging

from futureskit.notation import FuturesNotation
from futureskit.contracts import FuturesContract, ContractChain
from futureskit.continuous import (
    ContinuousFutureBuilder,
    RollRule,
    AdjustmentMethod,
    RollDate,
    RollSchedule
)

logger = logging.getLogger(__name__)

# --- Main Classes ---

class Future:
    """
    Represents a futures product line (e.g., 'CL' for WTI Crude).
    Acts as a factory for specific contracts and continuous series.
    """
    def __init__(self, root_symbol: str, datasource: Any, exchange: Optional[str] = None, 
                 metadata: Optional[Dict[str, Any]] = None,
                 vendor_map: Optional[Dict[str, str]] = None):
        self.root_symbol = root_symbol
        self.datasource = datasource
        self.exchange = exchange
        self.metadata = metadata or {}  # Store metadata
        self.vendor_map = vendor_map or {}  # Store vendor-specific symbol mappings
        self._chain = None  # Lazy loading
        self._notation = FuturesNotation()
    
    @classmethod
    def from_notation(cls, notation: str, datasource: Any, exchange: Optional[str] = None) -> Union['Future', 'ContinuousFuture']:
        """
        Create a Future or ContinuousFuture from notation string.
        
        Args:
            notation: Full notation string (e.g., 'BRN_2026F' or 'BRN.n.1')
            datasource: Data source for loading contract data
            exchange: Optional exchange identifier
            
        Returns:
            Future object for regular notation, ContinuousFuture for continuous notation
        
        Examples:
            # Regular contract
            future = Future.from_notation('BRN_2026F', datasource)
            
            # Continuous series
            continuous = Future.from_notation('BRN.n.1', datasource)
        """
        parser = FuturesNotation()
        parsed = parser.parse(notation)
        
        if parsed.is_continuous:
            # Create Future first, then continuous
            future = cls(parsed.root, datasource, exchange)
            continuous_notation = f"{parsed.roll_rule}.{parsed.contract_index}"
            return future.continuous(continuous_notation)
        else:
            # Regular Future
            return cls(parsed.root, datasource, exchange)
    
    @property
    def unit(self) -> Optional[str]:
        """Get unit from metadata (e.g., 'bbl', 'mt', 'gal')"""
        return self.metadata.get('unit')
    
    @property
    def currency(self) -> Optional[str]:
        """Get currency from metadata (e.g., 'USD', 'EUR')"""
        return self.metadata.get('currency')
    
    def get_metadata(self, key: str, default: Any = None) -> Any:
        """Safe metadata access with default value"""
        return self.metadata.get(key, default)
    
    @property
    def chain(self) -> ContractChain:
        """Lazily load and return the contract chain."""
        if self._chain is None:
            self._chain = self._load_chain()
        return self._chain

    def _load_chain(self) -> ContractChain:
        """Loads the contract chain from the datasource."""
        if hasattr(self.datasource, 'get_contract_chain'):
            contracts = self.datasource.get_contract_chain(self.root_symbol)
            # Set exchange and future reference if not already set
            for contract in contracts:
                if contract.exchange is None:
                    contract.exchange = self.exchange
                if contract.future is None:
                    contract.future = self  # Set reference to parent Future
            return ContractChain(self.root_symbol, contracts, self.exchange)
        logger.warning("Datasource has no 'get_contract_chain' method. Using empty chain.")
        return ContractChain(self.root_symbol, [], self.exchange)

    def contract(self, year: int, month_code: str) -> Optional[FuturesContract]:
        """Get a specific contract from the chain."""
        return self.chain.get_contract(year, month_code)

    def __getitem__(self, notation: str) -> Optional[FuturesContract]:
        """Get a contract using short notation (e.g., 'H26')."""
        parsed = self._notation.parse(f"{self.root_symbol}{notation}")
        if parsed.year and parsed.month:
            return self.contract(parsed.year, parsed.month)
        return None

    def continuous(self, notation: Optional[str] = None, **kwargs) -> 'ContinuousFuture':
        """
        Create a continuous futures series for this commodity.
        
        Args:
            notation: Optional continuous notation string (e.g., 'n.1' for front month by OI)
                     If provided, overrides kwargs
            **kwargs: Parameters for ContinuousFuture if notation not provided
        
        Returns:
            ContinuousFuture object configured according to notation or kwargs
        """
        if notation:
            # Parse continuous notation like "n.1" or "c.2"
            parsed = self._parse_continuous_notation(notation)
            return ContinuousFuture(self, **parsed)
        return ContinuousFuture(self, **kwargs)
    
    def _parse_continuous_notation(self, notation: str) -> dict:
        """
        Parse continuous notation into ContinuousFuture parameters.
        
        Notation format: {roll_rule}.{depth}
        Examples:
            'n.1' - Front month by open interest
            'v.2' - Second month by volume
            'c.1' - Front month by calendar
        """
        parts = notation.split('.')
        if len(parts) != 2:
            raise ValueError(f"Invalid continuous notation: {notation}. Expected format: 'rule.depth'")
        
        roll_rule = parts[0].lower()
        try:
            depth = int(parts[1]) - 1  # Convert from 1-based to 0-based
        except ValueError:
            raise ValueError(f"Invalid depth in notation: {parts[1]}. Must be an integer.")
        
        # Map notation roll rules to our RollRule values
        rule_mapping = {
            'n': 'oi',        # Open interest
            'v': 'volume',    # Volume
            'c': 'calendar',  # Calendar
            'fn': 'calendar', # First notice (use calendar for now)
            'lt': 'calendar', # Last trade (use calendar for now)
        }
        
        if roll_rule not in rule_mapping:
            raise ValueError(f"Invalid roll rule: {roll_rule}. Valid rules: {list(rule_mapping.keys())}")
        
        return {
            'roll': rule_mapping[roll_rule],
            'depth': depth,
            'offset': -5 if roll_rule == 'c' else 0,  # Default offset for calendar rolls
            'adjust': 'back'  # Default to back-adjustment
        }

    def __repr__(self):
        if self._chain is None:
            return f"Future({self.root_symbol!r}, contracts=unloaded)"
        else:
            return f"Future({self.root_symbol!r}, contracts={len(self._chain)})"


class ContinuousFuture:
    """
    Represents and evaluates a continuous futures series.
    
    This class provides a high-level interface to the ContinuousFutureBuilder,
    making it easy to create and work with continuous futures series.
    """
    def __init__(self, 
                 future: Future,
                 roll: Union[str, RollRule] = 'calendar',
                 offset: int = -5,
                 adjust: Union[str, AdjustmentMethod] = 'back',
                 depth: int = 0):
        """
        Initialize a continuous future.
        
        Args:
            future: The underlying Future object
            roll: Roll rule (calendar, volume, oi, etc.)
            offset: Days offset from roll rule (negative = roll earlier)
            adjust: Adjustment method (none, back, forward, proportional)
            depth: Contract depth (0=front month, 1=second month, etc.)
        """
        self.future = future
        self.root = future.root_symbol
        self.depth = depth + 1  # Convert to 1-based for compatibility
        self.offset = offset
        
        # Convert string inputs to enums
        if isinstance(roll, str):
            self.roll_rule = RollRule.from_string(roll)
        else:
            self.roll_rule = roll
            
        if isinstance(adjust, str):
            self.adjust = AdjustmentMethod(adjust)
        else:
            self.adjust = adjust
        
        # Internal state
        self._builder: Optional[ContinuousFutureBuilder] = None
        self._series: Optional[pd.Series] = None
        self._roll_schedule: Optional[RollSchedule] = None

    @property
    def builder(self) -> ContinuousFutureBuilder:
        """Lazy initialization of the builder."""
        if self._builder is None:
            # Get contracts from the future's chain
            contracts = list(self.future.chain)
            
            self._builder = ContinuousFutureBuilder(
                contracts=contracts,
                roll_rule=self.roll_rule,
                offset=self.offset,
                depth=self.depth,
                adjustment=self.adjust
            )
        return self._builder

    def evaluate(
        self,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        field: str = 'settlement'
    ) -> pd.DataFrame:
        """
        Build and return the continuous series.
        
        Args:
            start_date: Start of the series (defaults to 5 years ago)
            end_date: End of the series (defaults to today)
            field: Price field to use (settlement, close, etc.)
            
        Returns:
            DataFrame with the continuous series
        """
        if end_date is None:
            end_date = date.today()
        if start_date is None:
            start_date = end_date.replace(year=end_date.year - 5)

        logger.info(f"Building continuous series for {self.root} from {start_date} to {end_date}")
        
        # Build the series using the builder
        series = self.builder.build_series(
            field=field,
            start_date=start_date,
            end_date=end_date
        )
        
        # Store for future reference
        self._series = series
        
        # Convert to DataFrame for compatibility
        if isinstance(series, pd.Series):
            df = series.to_frame(name=f"{self.root}_M{self.depth}")
        else:
            df = pd.DataFrame(series)
        
        return df
    
    def get_roll_schedule(
        self,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None
    ) -> RollSchedule:
        """
        Get the roll schedule for the continuous series.
        
        Args:
            start_date: Start of the schedule
            end_date: End of the schedule
            
        Returns:
            RollSchedule object with all roll dates
        """
        if self._roll_schedule is None:
            self._roll_schedule = self.builder.build_roll_schedule(
                start_date=start_date,
                end_date=end_date
            )
        return self._roll_schedule
    
    def get_active_contract(self, as_of_date: date) -> Optional[FuturesContract]:
        """
        Get the active contract for a given date.
        
        Args:
            as_of_date: The date to check
            
        Returns:
            The active FuturesContract on that date
        """
        schedule = self.get_roll_schedule()
        return schedule.get_active_contract(as_of_date)
    
    @property
    def formats(self):
        """
        Returns a namespace with vendor format methods for this continuous series.
        
        Examples:
            continuous.formats.tradingview()  # "ICEEUR:BRN1!" for front month
            continuous.formats.refinitiv()    # "LCOc1"
        """
        from futureskit.symbology import SymbologyConverter
        from functools import partial
        
        # Create a namespace object with bound methods
        class Formats:
            pass
        
        formats = Formats()
        
        # Bind each method with the continuous series depth
        # Note: future.vendor_map is accessed through self.future
        vendor_map = self.future.vendor_map if hasattr(self.future, 'vendor_map') else {}
        
        formats.tradingview = partial(SymbologyConverter.tradingview, self.future.root_symbol, vendor_map, continuous_index=self.depth)
        formats.refinitiv = partial(SymbologyConverter.refinitiv, self.future.root_symbol, vendor_map, continuous_index=self.depth)
        formats.marketplace = partial(SymbologyConverter.marketplace, self.future.root_symbol, vendor_map, continuous_index=self.depth)
        formats.cme = partial(SymbologyConverter.cme, self.future.root_symbol, vendor_map, continuous_index=self.depth)
        formats.bloomberg = partial(SymbologyConverter.bloomberg, self.future.root_symbol, vendor_map, continuous_index=self.depth)
        
        return formats

    def __repr__(self):
        return f"ContinuousFuture({self.root!r}, roll='{self.roll_rule.value}', depth={self.depth-1}, adjust='{self.adjust.value}')"