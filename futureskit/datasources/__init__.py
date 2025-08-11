"""
FuturesKit data source interfaces and implementations.

Provides the base interface for data sources and example implementations
for view-only platforms like TradingView and Refinitiv.
"""

from futureskit.datasources.base import FuturesDataSource
from futureskit.datasources.tradingview import TradingViewDataSource
from futureskit.datasources.refinitiv import RefinitivDataSource

__all__ = [
    'FuturesDataSource',
    'TradingViewDataSource',
    'RefinitivDataSource'
]