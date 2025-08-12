"""
TradingView datasource - view-only charting platform.

This datasource is for URL generation only and does not fetch data.
TradingView does not provide API access for data retrieval.
"""

from typing import Dict, List, Optional, Union
from datetime import date, datetime
import pandas as pd
from futureskit.datasources.base import FuturesDataSource
from futureskit.contracts import FuturesContract
from futureskit.notation import MONTH_TO_CODE


class TradingViewDataSource(FuturesDataSource):
    """
    View-only datasource for TradingView chart URLs.
    
    This datasource generates TradingView URLs but cannot fetch data,
    as TradingView does not provide API access for data retrieval.
    
    Note: TradingView feed mappings (e.g., BRN->ICEEUR) should be provided
    via vendor_map when creating Future objects, not hardcoded in this datasource.
    
    Example:
        >>> from futureskit.datasources.tradingview import TradingViewDataSource
        >>> from futureskit import Future
        >>> 
        >>> tv = TradingViewDataSource()
        >>> future = Future('BRN', datasource=tv, vendor_map={
        ...     'tradingview_symbol': 'BRN',
        ...     'tradingview_exchange': 'ICEEUR'
        ... })
        >>> contract = future.contract(2026, 'H')
        >>> urls = contract.get_urls()
        >>> print(urls['tradingview'])
        'https://www.tradingview.com/chart/?symbol=ICEEUR:BRNH26'
    """
    
    def __init__(self):
        """
        Initialize TradingView datasource.
        
        Note: Feed mappings should come from vendor_map in Future objects,
        not from this datasource.
        """
        pass
    
    # Data fetching methods - not implemented for view-only datasource
    
    def series(self, symbols: Union[str, List[str]], 
              fields: Optional[List[str]] = None,
              start_date: Optional[Union[date, str]] = None,
              **kwargs) -> pd.DataFrame:
        """Not implemented - TradingView is view-only."""
        raise NotImplementedError(
            "TradingView is a view-only datasource. "
            "Data fetching is not available through TradingView."
        )
    
    def curve(self, symbols: Union[str, List[str]], 
              curve_dates: Optional[Union[date, str, List[date], List[str]]] = None,
              fields: Optional[List[str]] = None,
              **kwargs) -> pd.DataFrame:
        """Not implemented - TradingView is view-only."""
        raise NotImplementedError(
            "TradingView is a view-only datasource. "
            "Data fetching is not available through TradingView."
        )
    
    def contracts(self, symbols: Union[str, List[str]],
                  start_date: Optional[Union[date, str]] = None,
                  start_year: Optional[int] = None,
                  end_year: Optional[int] = None,
                  fields: Optional[List[str]] = None,
                  **kwargs) -> pd.DataFrame:
        """Not implemented - TradingView is view-only."""
        raise NotImplementedError(
            "TradingView is a view-only datasource. "
            "Data fetching is not available through TradingView."
        )
    
    def get_contract_chain(self, root_symbol: str) -> List[FuturesContract]:
        """
        Generate a mock contract chain for testing/demonstration.
        
        This creates a chain of the next 12 monthly contracts for testing
        URL generation and other non-data functionality.
        """
        try:
            from dateutil.relativedelta import relativedelta
        except ImportError:
            # If dateutil not available, return empty list
            return []
        
        contracts = []
        current_date = datetime.now()
        
        # Generate next 12 monthly contracts
        for i in range(12):
            contract_date = current_date + relativedelta(months=i)
            month_code = MONTH_TO_CODE[contract_date.month]
            
            contract = FuturesContract(
                root_symbol=root_symbol,
                year=contract_date.year,
                month_code=month_code,
                datasource=self
            )
            contracts.append(contract)
        
        return contracts
    
    # URL generation methods
    
    def get_contract_url(self, root_symbol: str, year: int, month_code: str,
                        vendor_map: Optional[Dict[str, str]] = None) -> Dict[str, str]:
        """
        Generate TradingView URLs for a specific contract.
        
        Handles TradingView-specific symbol mapping and feed prefixing internally.
        TradingView contracts use YYYY format and have both chart and overview URLs.
        
        Args:
            root_symbol: The exchange root symbol (e.g., 'BRN')
            year: Contract year (full year, e.g., 2026)
            month_code: Month code (e.g., 'H' for March)
            vendor_map: Optional vendor-specific symbol mappings
        """
        vendor_map = vendor_map or {}
        
        # Get TradingView-specific symbol and feed
        tv_symbol = vendor_map.get('tradingview_symbol', root_symbol)
        feed = vendor_map.get('tradingview_exchange', '')
        
        # Build contract symbol with full year (YYYY format)
        contract_symbol = f"{tv_symbol}{month_code}{year}"
        
        # Add feed prefix if provided
        if feed:
            chart_symbol = f"{feed}:{contract_symbol}"
            # Overview URL uses dash format with contract parameter
            overview_symbol = f"{feed}-{tv_symbol}1!"
            overview_url = f"https://www.tradingview.com/symbols/{overview_symbol}/?contract={contract_symbol}"
        else:
            chart_symbol = contract_symbol
            overview_url = f"https://www.tradingview.com/symbols/{tv_symbol}1!/?contract={contract_symbol}"
        
        return {
            'tradingview': f"https://www.tradingview.com/chart/?symbol={chart_symbol}",
            'tradingview_overview': overview_url
        }
    
    def get_continuous_url(self, root_symbol: str, depth: int,
                          vendor_map: Optional[Dict[str, str]] = None) -> Dict[str, str]:
        """
        Generate TradingView URLs for continuous series.
        
        Handles TradingView-specific symbol mapping and feed prefixing internally.
        TradingView uses the format SYMBOL{N}! for continuous contracts.
        
        Args:
            root_symbol: The exchange root symbol (e.g., 'BRN')
            depth: Continuous depth (1=front, 2=second, etc.)
            vendor_map: Optional vendor-specific symbol mappings
        """
        vendor_map = vendor_map or {}
        
        # Get TradingView-specific symbol and feed
        tv_symbol = vendor_map.get('tradingview_symbol', root_symbol)
        feed = vendor_map.get('tradingview_exchange', '')
        
        # Build continuous symbol
        continuous_symbol = f"{tv_symbol}{depth}!"
        
        # Add feed prefix if provided
        if feed:
            final_symbol = f"{feed}:{continuous_symbol}"
        else:
            final_symbol = continuous_symbol
        
        return {
            'tradingview': f"https://www.tradingview.com/chart/?symbol={final_symbol}",
            'tradingview_overview': f"https://www.tradingview.com/symbols/{final_symbol}"
        }
    
    def supports_url_generation(self) -> bool:
        """TradingView datasource is primarily for URL generation."""
        return True
    
    def __repr__(self):
        return "TradingViewDataSource()"