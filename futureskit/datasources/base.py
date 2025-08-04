"""
Abstract base class for futures data sources.

This module defines the interface that data providers must implement
to work with FuturesKit objects.
"""

from abc import ABC, abstractmethod
from typing import List, Optional, Union, TYPE_CHECKING
from datetime import date
import pandas as pd

if TYPE_CHECKING:
    from futureskit.contracts import FuturesContract


class FuturesDataSource(ABC):
    """
    Abstract interface for futures data providers.
    
    This defines what any data source must provide to work with FuturesKit.
    Implementations might fetch data from APIs, databases, files, etc.
    """
    
    @abstractmethod
    def series(self, 
               symbols: Union[str, List[str]], 
               fields: Optional[List[str]] = None,
               start_date: Optional[Union[date, str]] = None,
               end_date: Optional[Union[date, str]] = None,
               **kwargs) -> pd.DataFrame:
        """
        Get time series data for futures symbols.
        
        Args:
            symbols: Single symbol or list of symbols. Can be:
                     - Specific contracts: 'BRN_2026F', 'CL_2025H'
                     - Continuous series: 'BRN.n.1', 'CL.v.3'
                     - Root symbols: 'BRN', 'CL' (typically front month)
            fields: Specific fields to retrieve (e.g., ['close', 'volume'])
                    If None, return all available fields
            start_date: Start of date range (inclusive)
            end_date: End of date range (inclusive)
            **kwargs: Additional implementation-specific parameters
            
        Returns:
            DataFrame with DatetimeIndex and columns for each symbol/field combination.
            Column naming convention is implementation-specific but should be consistent.
            
        Raises:
            NotImplementedError: Must be implemented by subclasses
        """
        raise NotImplementedError
    
    @abstractmethod
    def curve(self, 
              symbols: Union[str, List[str]], 
              curve_date: Optional[Union[date, str]] = None,
              fields: Optional[List[str]] = None,
              **kwargs) -> pd.DataFrame:
        """
        Get forward curve data (snapshot of all contracts at a point in time).
        
        Args:
            symbols: Root symbol(s) to get curves for (e.g., 'BRN', 'CL')
            curve_date: Date of the curve. If None, return most recent curve
            fields: Specific fields to retrieve (e.g., ['settlement', 'volume'])
                    If None, return all available fields
            **kwargs: Additional implementation-specific parameters
            
        Returns:
            DataFrame with forward curve data. Structure is implementation-specific
            but typically includes contract identifiers and requested fields.
            
        Raises:
            NotImplementedError: Must be implemented by subclasses
        """
        raise NotImplementedError
    
    @abstractmethod
    def contracts(self,
                  symbols: Union[str, List[str]],
                  start_date: Optional[Union[date, str]] = None,
                  start_year: Optional[int] = None,
                  end_year: Optional[int] = None,
                  fields: Optional[List[str]] = None,
                  **kwargs) -> pd.DataFrame:
        """
        Get historical data for specific contract months.
        
        This method fetches time series data for all contracts of the given symbols
        within the specified date/year range. It's useful for analyzing historical
        contract data across multiple delivery months.
        
        Args:
            symbols: Root symbol(s) to get contracts for (e.g., 'BRN', 'CL')
            start_date: Optional start date for the time series data
            start_year: First year of contracts to include (e.g., 2023)
            end_year: Last year of contracts to include (e.g., 2024)
            fields: Specific fields to retrieve (e.g., ['settlement', 'volume'])
                    If None, return all available fields
            **kwargs: Additional implementation-specific parameters
            
        Returns:
            DataFrame with time series data for all contracts in the range.
            The structure is implementation-specific but typically has a
            DatetimeIndex and columns for each contract/field combination.
            
        Notes:
            - If neither start_year nor end_year is specified, implementation
              should choose a reasonable default (e.g., last 2 years)
            - The year parameters filter which contracts are included,
              not the date range of the data
            
        Raises:
            NotImplementedError: Must be implemented by subclasses
        """
        raise NotImplementedError
    
    @abstractmethod
    def get_contract_chain(self, root_symbol: str) -> List['FuturesContract']:
        """
        Get available contracts for a commodity.
        
        This method returns a list of FuturesContract objects representing
        all available contracts for the given root symbol. The contracts
        should have basic metadata (year, month_code) but typically won't
        have price data loaded yet.
        
        Args:
            root_symbol: The commodity root symbol (e.g., 'BRN', 'CL')
            
        Returns:
            List of FuturesContract objects sorted by delivery date.
            The contracts should have at minimum:
            - root_symbol
            - year
            - month_code
            - datasource (reference to self for lazy loading)
            
            Optional metadata that can be included:
            - first_trade_date
            - last_trade_date
            - expiry_date
            - is_active
            
        Notes:
            - Contracts should be returned in delivery date order
            - Price data should NOT be loaded (lazy loading pattern)
            - The datasource should be set to self so contracts can
              fetch their own data when needed
            
        Raises:
            NotImplementedError: Must be implemented by subclasses
        """
        raise NotImplementedError