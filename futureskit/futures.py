"""
Main Futures classes that provide a high-level object interface.

This module provides the top-level Future class, which acts as a factory
for specific FuturesContract and ContinuousFuture objects.
"""

from typing import Optional, Any, List, Union, Tuple
from datetime import date, timedelta
from dataclasses import dataclass
from enum import Enum
import pandas as pd
import logging

from futureskit.notation import FuturesNotation
from futureskit.contracts import FuturesContract, ContractChain

logger = logging.getLogger(__name__)


# --- Enums and Dataclasses (previously in continuous.py) ---

class RollRule(Enum):
    """Roll rules for continuous futures"""
    FIRST_NOTICE = 'f'
    LAST_TRADING = 'l'
    VOLUME = 'v'
    OPEN_INTEREST = 'o'
    CALENDAR = 'c'

@dataclass
class RollDate:
    """Represents a single roll date event in a continuous series."""
    from_contract: FuturesContract
    to_contract: FuturesContract
    roll_date: date
    rule: RollRule

# --- Main Classes ---

class Future:
    """
    Represents a futures product line (e.g., 'CL' for WTI Crude).
    Acts as a factory for specific contracts and continuous series.
    """
    def __init__(self, root_symbol: str, datasource: Any, exchange: Optional[str] = None):
        self.root_symbol = root_symbol
        self.datasource = datasource
        self.exchange = exchange
        self.chain = self._load_chain()
        self._notation = FuturesNotation()

    def _load_chain(self) -> ContractChain:
        """Loads the contract chain from the datasource."""
        if hasattr(self.datasource, 'get_contract_chain'):
            contracts_data = self.datasource.get_contract_chain(self.root_symbol)
            contracts = [
                FuturesContract(
                    self.root_symbol, c['year'], c['month_code'],
                    exchange=self.exchange, datasource=self.datasource
                ) for c in contracts_data
            ]
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

    def continuous(self, **kwargs) -> 'ContinuousFuture':
        """Create a continuous futures series for this commodity."""
        return ContinuousFuture(self, **kwargs)

    def __repr__(self):
        return f"Future({self.root_symbol!r}, contracts={len(self.chain)})"


class ContinuousFuture:
    """
    Represents and evaluates a continuous futures series.
    This class now incorporates the logic from the old ContinuousFutures
    and ContinuousBuilder classes.
    """
    def __init__(self, 
                 future: Future,
                 roll: Union[str, RollRule] = 'calendar',
                 offset: int = -5,
                 adjust: str = 'back',
                 depth: int = 0):
        self.future = future
        self.root = future.root_symbol
        self.depth = depth + 1  # 1-based
        self.offset = offset
        self.adjust = adjust
        
        if isinstance(roll, RollRule):
            self.roll_rule = roll
        else:
            roll_map = {'volume': RollRule.VOLUME, 'v': RollRule.VOLUME,
                        'open_interest': RollRule.OPEN_INTEREST, 'oi': RollRule.OPEN_INTEREST, 'o': RollRule.OPEN_INTEREST,
                        'calendar': RollRule.CALENDAR, 'c': RollRule.CALENDAR,
                        'first_notice': RollRule.FIRST_NOTICE, 'f': RollRule.FIRST_NOTICE,
                        'last_trading': RollRule.LAST_TRADING, 'l': RollRule.LAST_TRADING}
            self.roll_rule = roll_map.get(roll.lower(), RollRule.CALENDAR)
            
        self._series: Optional[pd.DataFrame] = None
        self.roll_schedule: List[RollDate] = []

    def evaluate(self, start_date: Optional[date] = None, end_date: Optional[date] = None) -> pd.DataFrame:
        """Builds and returns the continuous series DataFrame."""
        if end_date is None: end_date = date.today()
        if start_date is None: start_date = end_date.replace(year=end_date.year - 5)

        logger.info(f"Building continuous series for {self.root} from {start_date} to {end_date}")
        
        self._generate_roll_schedule(start_date, end_date)
        segments = self._build_series_segments(start_date, end_date)
        
        # Placeholder for stitching and adjusting data
        if segments:
            # In a full implementation, you would fetch data for each segment,
            # stitch it, and apply adjustments.
            # For now, we return the data of the last contract in the first segment.
            last_contract = segments[0][2]
            if last_contract._price_data is not None:
                return last_contract._price_data

        logger.warning("Could not build continuous series.")
        return pd.DataFrame()

    def _generate_roll_schedule(self, start_date: date, end_date: date):
        """Generates the list of roll dates based on the rule."""
        # This logic is moved from the old ContinuousFutures class
        # (Implementation is a placeholder for now)
        self.roll_schedule = []
        logger.debug("Roll schedule generation is a placeholder.")

    def _build_series_segments(self, start_date: date, end_date: date) -> List[Tuple[date, date, FuturesContract]]:
        """Builds the segments based on the roll schedule."""
        # This logic is moved from the old ContinuousBuilder
        if not self.roll_schedule:
            active_contract = self.future.chain.get_nth_contract(self.depth, as_of=start_date)
            if active_contract:
                return [(start_date, end_date, active_contract)]
            return []
        # (Full segment building logic would go here)
        return []

    def __repr__(self):
        return f"ContinuousFuture({self.root!r}, roll='{self.roll_rule.value}', depth={self.depth-1})"