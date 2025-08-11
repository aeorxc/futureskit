"""
Test FuturesKit's simplified continuous futures implementation.

This module tests the clean object-oriented API for continuous futures
without compatibility layers.
"""

import pytest
from datetime import date
import pandas as pd
import sys
import os

# Add futureskit to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from futureskit import Future, ContinuousFuture, RollRule, AdjustmentMethod
from futureskit.contracts import FuturesContract
from futureskit.continuous import ContinuousFutureBuilder


class MockDataSource:
    """Mock data source for testing."""
    
    def get_contract_chain(self, root_symbol: str):
        """Return mock contract chain."""
        contracts = []
        for month_offset in range(12):
            year = 2024
            month = month_offset + 1
            
            month_codes = 'FGHJKMNQUVXZ'
            month_code = month_codes[month - 1]
            
            contract = FuturesContract(
                root_symbol=root_symbol,
                year=year,
                month_code=month_code,
                datasource=self
            )
            contract.expiry_date = date(year, month, 25)
            # Add get_data method to all contracts
            contract.get_data = lambda start=None, end=None: self.get_data(start, end)
            contracts.append(contract)
        
        return contracts
    
    def series(self, symbols, **kwargs):
        """Return mock series data."""
        dates = pd.date_range('2024-01-01', '2024-12-31', freq='B')
        data = {}
        for symbol in symbols if isinstance(symbols, list) else [symbols]:
            # Create trending price data
            base_price = 100
            trend = pd.Series(range(len(dates))) * 0.01
            data[f"{symbol}_settlement"] = base_price + trend
        return pd.DataFrame(data, index=dates)
    
    def get_data(self, start_date=None, end_date=None):
        """Mock get_data for contracts."""
        dates = pd.date_range('2024-01-01', '2024-12-31', freq='B')
        if start_date:
            dates = dates[dates >= pd.Timestamp(start_date)]
        if end_date:
            dates = dates[dates <= pd.Timestamp(end_date)]
        
        # Create mock settlement data
        base_price = 100
        trend = pd.Series(range(len(dates))) * 0.01
        data = {
            'settlement': base_price + trend,
            'volume': 10000 + pd.Series(range(len(dates))) * 10,
        }
        return pd.DataFrame(data, index=dates)


def test_continuous_future_creation():
    """Test creating continuous futures with different configurations."""
    datasource = MockDataSource()
    future = Future("BRN", datasource)
    
    # Test default configuration
    continuous = future.continuous()
    assert continuous.roll_rule == RollRule.CALENDAR
    assert continuous.adjust == AdjustmentMethod.BACK
    assert continuous.depth == 1  # Front month (1-based internally)
    
    # Test custom configuration
    continuous = future.continuous(
        roll='volume',
        depth=1,  # Second month (0-based input)
        offset=-3,
        adjust='none'
    )
    assert continuous.roll_rule == RollRule.VOLUME
    assert continuous.adjust == AdjustmentMethod.NONE
    assert continuous.depth == 2  # 0-based becomes 1-based internally
    assert continuous.offset == -3


def test_continuous_future_notation():
    """Test continuous futures using notation."""
    datasource = MockDataSource()
    future = Future("CL", datasource)
    
    # Test different roll rules via notation
    test_cases = [
        ("n.1", RollRule.OPEN_INTEREST, 1),
        ("v.2", RollRule.VOLUME, 2),
        ("c.3", RollRule.CALENDAR, 3),
    ]
    
    for notation, expected_rule, expected_depth in test_cases:
        continuous = future.continuous(notation)
        assert continuous.roll_rule == expected_rule
        assert continuous.depth == expected_depth


def test_future_from_notation():
    """Test Future.from_notation with continuous contracts."""
    datasource = MockDataSource()
    
    # Regular contract
    future = Future.from_notation("BRN_2024F", datasource)
    assert isinstance(future, Future)
    assert future.root_symbol == "BRN"
    
    # Continuous contract
    continuous = Future.from_notation("BRN.n.1", datasource)
    assert isinstance(continuous, ContinuousFuture)
    assert continuous.root == "BRN"
    assert continuous.roll_rule == RollRule.OPEN_INTEREST
    assert continuous.depth == 1


def test_continuous_builder():
    """Test ContinuousFutureBuilder directly."""
    datasource = MockDataSource()
    
    # Create mock contracts
    contracts = [
        FuturesContract("CL", 2024, 'F', datasource),  # Jan
        FuturesContract("CL", 2024, 'G', datasource),  # Feb
        FuturesContract("CL", 2024, 'H', datasource),  # Mar
    ]
    
    # Set delivery dates and add get_data method
    for i, contract in enumerate(contracts):
        contract._delivery_date = date(2024, i+1, 1)  
        contract.expiry_date = date(2024, i+1, 25)
        # Add get_data method to contract
        contract.get_data = lambda start=None, end=None: datasource.get_data(start, end)
    
    # Create builder
    builder = ContinuousFutureBuilder(
        contracts=contracts,
        roll_rule='calendar',
        offset=-5,
        depth=1,
        adjustment='back'
    )
    
    # Test configuration
    assert builder.roll_rule == RollRule.CALENDAR
    assert builder.offset == -5
    assert builder.depth == 1
    assert builder.adjustment == AdjustmentMethod.BACK
    
    # Test roll schedule building
    schedule = builder.build_roll_schedule(
        start_date=date(2024, 1, 1),
        end_date=date(2024, 3, 31)
    )
    
    # Should have rolls between contracts
    assert len(schedule.roll_dates) == 2  # Jan->Feb, Feb->Mar
    assert schedule.start_date == date(2024, 1, 1)
    assert schedule.end_date == date(2024, 3, 31)


def test_roll_schedule_functionality():
    """Test roll schedule methods."""
    datasource = MockDataSource()
    future = Future("NG", datasource)
    continuous = future.continuous(roll='calendar', offset=-5)
    
    # Get roll schedule
    schedule = continuous.get_roll_schedule(
        start_date=date(2024, 1, 1),
        end_date=date(2024, 6, 30)
    )
    
    # Test get_active_contract
    test_date = date(2024, 3, 15)
    active_contract = schedule.get_active_contract(test_date)
    assert active_contract is not None
    assert hasattr(active_contract, 'to_canonical')


def test_different_roll_rules():
    """Test different roll rules work correctly."""
    datasource = MockDataSource()
    future = Future("RB", datasource)
    
    # Test each roll rule
    roll_rules = ['calendar', 'volume', 'oi']
    expected_enums = [RollRule.CALENDAR, RollRule.VOLUME, RollRule.OPEN_INTEREST]
    
    for rule_str, expected_enum in zip(roll_rules, expected_enums):
        continuous = future.continuous(roll=rule_str)
        assert continuous.roll_rule == expected_enum


def test_different_adjustment_methods():
    """Test different adjustment methods."""
    datasource = MockDataSource()
    future = Future("HO", datasource)
    
    # Test each adjustment method
    adjust_methods = ['none', 'back']
    expected_enums = [AdjustmentMethod.NONE, AdjustmentMethod.BACK]
    
    for method_str, expected_enum in zip(adjust_methods, expected_enums):
        continuous = future.continuous(adjust=method_str)
        assert continuous.adjust == expected_enum


def test_continuous_repr():
    """Test string representation of continuous futures."""
    datasource = MockDataSource()
    future = Future("WTI", datasource)
    continuous = future.continuous(roll='calendar', depth=0, adjust='back')
    
    repr_str = repr(continuous)
    assert "WTI" in repr_str
    assert "calendar" in repr_str
    assert "back" in repr_str


if __name__ == "__main__":
    # Run tests
    print("Testing FuturesKit simplified continuous futures...")
    print("=" * 60)
    
    tests = [
        ("Continuous future creation", test_continuous_future_creation),
        ("Continuous notation", test_continuous_future_notation),
        ("Future.from_notation", test_future_from_notation),
        ("ContinuousFutureBuilder", test_continuous_builder),
        ("Roll schedule functionality", test_roll_schedule_functionality),
        ("Different roll rules", test_different_roll_rules),
        ("Different adjustments", test_different_adjustment_methods),
        ("String representation", test_continuous_repr),
    ]
    
    passed = 0
    failed = 0
    
    for test_name, test_func in tests:
        try:
            test_func()
            print(f"[PASS] {test_name}")
            passed += 1
        except AssertionError as e:
            print(f"[FAIL] {test_name}: {e}")
            failed += 1
        except Exception as e:
            print(f"[ERROR] {test_name}: {e}")
            failed += 1
    
    print("=" * 60)
    print(f"Results: {passed} passed, {failed} failed")
    
    if failed == 0:
        print("All tests passed! Simplified continuous futures working correctly.")
    else:
        print(f"Some tests failed. Please review the failures above.")
        sys.exit(1)