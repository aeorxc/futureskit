"""
Simplified continuous futures implementation for FuturesKit.

This module implements the logic for creating continuous futures series by
stitching together individual futures contracts based on configurable roll rules.

This version focuses on the clean object-oriented API without legacy compatibility layers.
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Optional, Union, Tuple
from datetime import date, datetime, timedelta
from dataclasses import dataclass
from enum import Enum
import pandas as pd
import numpy as np
import logging

from futureskit.contracts import FuturesContract

logger = logging.getLogger(__name__)


# ==================== Enums ====================

class RollRule(Enum):
    """Roll rules for continuous futures"""
    CALENDAR = 'calendar'          # Roll on fixed calendar days before expiry
    FIRST_NOTICE = 'first_notice'  # Roll on first notice day
    LAST_TRADING = 'last_trading'  # Roll on last trading day
    VOLUME = 'volume'              # Roll when next contract has higher volume
    OPEN_INTEREST = 'oi'          # Roll when next contract has higher OI
    
    @classmethod
    def from_string(cls, value: str) -> 'RollRule':
        """Convert string to RollRule enum"""
        mapping = {
            'c': cls.CALENDAR,
            'calendar': cls.CALENDAR,
            'f': cls.FIRST_NOTICE,
            'fn': cls.FIRST_NOTICE,
            'first_notice': cls.FIRST_NOTICE,
            'l': cls.LAST_TRADING,
            'lt': cls.LAST_TRADING,
            'last_trading': cls.LAST_TRADING,
            'v': cls.VOLUME,
            'volume': cls.VOLUME,
            'o': cls.OPEN_INTEREST,
            'n': cls.OPEN_INTEREST,  # Legacy notation support
            'oi': cls.OPEN_INTEREST,
            'open_interest': cls.OPEN_INTEREST,
        }
        return mapping.get(value.lower(), cls.CALENDAR)


class AdjustmentMethod(Enum):
    """Price adjustment methods for continuous series"""
    NONE = 'none'              # No adjustment (concatenate)
    BACK = 'back'              # Back-adjust historical prices
    FORWARD = 'forward'        # Forward-adjust future prices
    PROPORTIONAL = 'proportional'  # Proportional/ratio adjustment


# ==================== Data Classes ====================

@dataclass
class RollDate:
    """Represents a single roll date event in a continuous series."""
    from_contract: FuturesContract
    to_contract: FuturesContract
    roll_date: date
    rule: RollRule
    adjustment: Optional[float] = None  # Price adjustment at roll


@dataclass 
class RollSchedule:
    """Complete roll schedule for a continuous series."""
    roll_dates: List[RollDate]
    start_date: date
    end_date: date
    
    def get_active_contract(self, as_of_date: date) -> Optional[FuturesContract]:
        """Get the active contract for a given date."""
        for i, roll in enumerate(self.roll_dates):
            if as_of_date <= roll.roll_date:
                return roll.from_contract
        # If past all roll dates, return the last contract
        if self.roll_dates:
            return self.roll_dates[-1].to_contract
        return None


# ==================== Roll Strategies ====================

class RollStrategy(ABC):
    """Abstract base class for roll strategies."""
    
    @abstractmethod
    def determine_roll_date(
        self,
        current_contract: FuturesContract,
        next_contract: FuturesContract,
        contract_data: Dict[str, pd.DataFrame],
        offset: int = 0
    ) -> date:
        """Determine when to roll from current to next contract."""
        pass


class CalendarRollStrategy(RollStrategy):
    """Roll based on calendar days before expiry."""
    
    def determine_roll_date(
        self,
        current_contract: FuturesContract,
        next_contract: FuturesContract,
        contract_data: Dict[str, pd.DataFrame],
        offset: int = 0
    ) -> date:
        """Roll N days before expiry (offset determines N)."""
        # Get expiry date from contract
        if hasattr(current_contract, 'expiry_date') and current_contract.expiry_date:
            expiry = current_contract.expiry_date
        elif hasattr(current_contract, 'last_trade_date') and current_contract.last_trade_date:
            expiry = current_contract.last_trade_date
        else:
            # Default to last day of delivery month
            expiry = current_contract.delivery_date + pd.offsets.MonthEnd(0)
        
        # Apply offset (negative means roll earlier)
        if isinstance(expiry, pd.Timestamp):
            expiry = expiry.date()
            
        return expiry + timedelta(days=offset)


class VolumeRollStrategy(RollStrategy):
    """Roll when next contract has higher volume."""
    
    def determine_roll_date(
        self,
        current_contract: FuturesContract,
        next_contract: FuturesContract,
        contract_data: Dict[str, pd.DataFrame],
        offset: int = 0
    ) -> date:
        """Roll when next contract's volume exceeds current."""
        # Implementation would compare volumes and find crossover
        # For now, fallback to calendar-based roll
        return CalendarRollStrategy().determine_roll_date(
            current_contract, next_contract, contract_data, offset
        )


class OpenInterestRollStrategy(RollStrategy):
    """Roll when next contract has higher open interest."""
    
    def determine_roll_date(
        self,
        current_contract: FuturesContract,
        next_contract: FuturesContract,
        contract_data: Dict[str, pd.DataFrame],
        offset: int = 0
    ) -> date:
        """Roll when next contract's OI exceeds current."""
        # Implementation would compare OI and find crossover
        # For now, fallback to calendar-based roll
        return CalendarRollStrategy().determine_roll_date(
            current_contract, next_contract, contract_data, offset
        )


# ==================== Roll Strategy Factory ====================

class RollStrategyFactory:
    """Factory for creating roll strategies."""
    
    _strategies = {
        RollRule.CALENDAR: CalendarRollStrategy,
        RollRule.FIRST_NOTICE: CalendarRollStrategy,  # For now, same as calendar
        RollRule.LAST_TRADING: CalendarRollStrategy,  # For now, same as calendar
        RollRule.VOLUME: VolumeRollStrategy,
        RollRule.OPEN_INTEREST: OpenInterestRollStrategy,
    }
    
    @classmethod
    def create(cls, rule: RollRule) -> RollStrategy:
        """Create a roll strategy for the given rule."""
        strategy_class = cls._strategies.get(rule, CalendarRollStrategy)
        return strategy_class()


# ==================== Adjustment Strategies ====================

class AdjustmentStrategy(ABC):
    """Abstract base class for price adjustment strategies."""
    
    @abstractmethod
    def calculate_adjustments(
        self,
        roll_schedule: RollSchedule,
        contract_data: Dict[str, pd.DataFrame]
    ) -> Dict[date, float]:
        """Calculate price adjustments for each roll date."""
        pass
    
    @abstractmethod
    def apply_adjustments(
        self,
        series: pd.Series,
        adjustments: Dict[date, float]
    ) -> pd.Series:
        """Apply adjustments to a price series."""
        pass


class NoAdjustmentStrategy(AdjustmentStrategy):
    """No price adjustment - simple concatenation."""
    
    def calculate_adjustments(
        self,
        roll_schedule: RollSchedule,
        contract_data: Dict[str, pd.DataFrame]
    ) -> Dict[date, float]:
        """No adjustments needed."""
        return {}
    
    def apply_adjustments(
        self,
        series: pd.Series,
        adjustments: Dict[date, float]
    ) -> pd.Series:
        """Return series unchanged."""
        return series


class BackAdjustmentStrategy(AdjustmentStrategy):
    """Back-adjust historical prices to remove roll gaps."""
    
    def calculate_adjustments(
        self,
        roll_schedule: RollSchedule,
        contract_data: Dict[str, pd.DataFrame]
    ) -> Dict[date, float]:
        """Calculate cumulative adjustments at each roll."""
        adjustments = {}
        cumulative_adj = 0.0
        
        for roll in roll_schedule.roll_dates:
            # Get prices on roll date
            from_key = roll.from_contract.to_canonical()
            to_key = roll.to_contract.to_canonical()
            
            if from_key in contract_data and to_key in contract_data:
                from_df = contract_data[from_key]
                to_df = contract_data[to_key]
                
                # Find price on roll date
                from_price = self._get_price_on_date(from_df, roll.roll_date)
                to_price = self._get_price_on_date(to_df, roll.roll_date)
                
                if from_price is not None and to_price is not None:
                    # Adjustment is the difference
                    adjustment = to_price - from_price
                    cumulative_adj += adjustment
                    adjustments[roll.roll_date] = cumulative_adj
        
        return adjustments
    
    def apply_adjustments(
        self,
        series: pd.Series,
        adjustments: Dict[date, float]
    ) -> pd.Series:
        """Apply back-adjustments to historical data."""
        adjusted = series.copy()
        
        # Sort adjustments by date (most recent first for back-adjustment)
        sorted_adjustments = sorted(adjustments.items(), reverse=True)
        
        for adj_date, adj_value in sorted_adjustments:
            # Adjust all data before this date
            mask = adjusted.index < pd.Timestamp(adj_date)
            adjusted[mask] = adjusted[mask] + adj_value
        
        return adjusted
    
    def _get_price_on_date(self, df: pd.DataFrame, target_date: date) -> Optional[float]:
        """Extract price from dataframe on given date."""
        # Look for settlement or close price columns
        price_cols = [c for c in df.columns if any(
            p in c.lower() for p in ['settlement', 'close', 'price']
        )]
        
        if not price_cols or pd.Timestamp(target_date) not in df.index:
            return None
        
        value = df.loc[pd.Timestamp(target_date), price_cols[0]]
        return float(value) if pd.notna(value) else None


# ==================== Main ContinuousFuture Builder ====================

class ContinuousFutureBuilder:
    """
    Builder for creating continuous futures series.
    
    This class handles the complex logic of stitching together individual
    futures contracts into a continuous series.
    """
    
    def __init__(
        self,
        contracts: List[FuturesContract],
        roll_rule: Union[str, RollRule] = RollRule.CALENDAR,
        offset: int = 0,
        depth: int = 1,
        adjustment: Union[str, AdjustmentMethod] = AdjustmentMethod.NONE
    ):
        """Initialize the continuous future builder."""
        self.contracts = sorted(contracts, key=lambda c: c.delivery_date)
        self.roll_rule = RollRule.from_string(roll_rule) if isinstance(roll_rule, str) else roll_rule
        self.offset = offset
        self.depth = depth
        self.adjustment = AdjustmentMethod(adjustment) if isinstance(adjustment, str) else adjustment
        
        self._roll_strategy = RollStrategyFactory.create(self.roll_rule)
        self._adjustment_strategy = self._create_adjustment_strategy()
    
    def _create_adjustment_strategy(self) -> AdjustmentStrategy:
        """Create the appropriate adjustment strategy."""
        if self.adjustment == AdjustmentMethod.BACK:
            return BackAdjustmentStrategy()
        elif self.adjustment == AdjustmentMethod.NONE:
            return NoAdjustmentStrategy()
        else:
            # TODO: Implement forward and proportional adjustment
            return NoAdjustmentStrategy()
    
    def build_roll_schedule(
        self,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        contract_data: Optional[Dict[str, pd.DataFrame]] = None
    ) -> RollSchedule:
        """Build the roll schedule for the continuous series."""
        if not self.contracts:
            return RollSchedule([], start_date or date.today(), end_date or date.today())
        
        # Default date range
        if start_date is None:
            start_date = min(c.first_trade_date or c.delivery_date 
                           for c in self.contracts)
        if end_date is None:
            end_date = date.today()
        
        # Load contract data if needed
        if contract_data is None:
            contract_data = self._load_contract_data(start_date, end_date)
        
        roll_dates = []
        
        # Build rolls between consecutive contracts
        for i in range(len(self.contracts) - self.depth):
            current = self.contracts[i + self.depth - 1]
            next_contract = self.contracts[i + self.depth]
            
            roll_date = self._roll_strategy.determine_roll_date(
                current, next_contract, contract_data, self.offset
            )
            
            roll_dates.append(RollDate(
                from_contract=current,
                to_contract=next_contract,
                roll_date=roll_date,
                rule=self.roll_rule
            ))
        
        return RollSchedule(roll_dates, start_date, end_date)
    
    def build_series(
        self,
        field: str = 'settlement',
        start_date: Optional[date] = None,
        end_date: Optional[date] = None
    ) -> pd.Series:
        """Build the continuous futures series."""
        # Load all contract data
        contract_data = self._load_contract_data(start_date, end_date)
        
        # Build roll schedule
        schedule = self.build_roll_schedule(start_date, end_date, contract_data)
        
        # Stitch contracts together
        continuous_series = self._stitch_contracts(schedule, contract_data, field)
        
        # Calculate and apply adjustments
        if self.adjustment != AdjustmentMethod.NONE:
            adjustments = self._adjustment_strategy.calculate_adjustments(
                schedule, contract_data
            )
            continuous_series = self._adjustment_strategy.apply_adjustments(
                continuous_series, adjustments
            )
        
        return continuous_series
    
    def _load_contract_data(
        self,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None
    ) -> Dict[str, pd.DataFrame]:
        """Load historical data for all contracts."""
        contract_data = {}
        
        for contract in self.contracts:
            # Get data from the contract's datasource
            if hasattr(contract, 'datasource') and contract.datasource:
                df = contract.get_data(start_date, end_date)
                if df is not None and not df.empty:
                    contract_data[contract.to_canonical()] = df
        
        return contract_data
    
    def _stitch_contracts(
        self,
        schedule: RollSchedule,
        contract_data: Dict[str, pd.DataFrame],
        field: str
    ) -> pd.Series:
        """Stitch together contracts according to roll schedule."""
        segments = []
        
        # Handle the first contract (before any rolls)
        if schedule.roll_dates:
            first_contract = schedule.roll_dates[0].from_contract
            first_key = first_contract.to_canonical()
            
            if first_key in contract_data:
                df = contract_data[first_key]
                field_col = self._find_field_column(df, field)
                if field_col:
                    # Data up to first roll
                    mask = df.index <= pd.Timestamp(schedule.roll_dates[0].roll_date)
                    segments.append(df.loc[mask, field_col])
        
        # Handle rolls
        for i, roll in enumerate(schedule.roll_dates):
            to_key = roll.to_contract.to_canonical()
            
            if to_key in contract_data:
                df = contract_data[to_key]
                field_col = self._find_field_column(df, field)
                
                if field_col:
                    # Determine the date range for this contract
                    start = pd.Timestamp(roll.roll_date) + timedelta(days=1)
                    
                    if i < len(schedule.roll_dates) - 1:
                        # Until next roll
                        end = pd.Timestamp(schedule.roll_dates[i + 1].roll_date)
                    else:
                        # Last contract - until end date
                        end = pd.Timestamp(schedule.end_date)
                    
                    mask = (df.index > start) & (df.index <= end)
                    segments.append(df.loc[mask, field_col])
        
        # Concatenate all segments
        if segments:
            return pd.concat(segments).sort_index()
        
        return pd.Series()
    
    def _find_field_column(self, df: pd.DataFrame, field: str) -> Optional[str]:
        """Find the column matching the requested field."""
        field_lower = field.lower()
        
        # Direct match
        if field in df.columns:
            return field
        
        # Case-insensitive match
        for col in df.columns:
            if col.lower() == field_lower:
                return col
        
        # Partial match
        for col in df.columns:
            if field_lower in col.lower():
                return col
        
        # Common aliases
        aliases = {
            'settlement': ['settle', 'sett'],
            'close': ['px_last', 'last'],
            'volume': ['vol'],
            'open_interest': ['oi', 'openint']
        }
        
        if field_lower in aliases:
            for alias in aliases[field_lower]:
                for col in df.columns:
                    if alias in col.lower():
                        return col
        
        return None