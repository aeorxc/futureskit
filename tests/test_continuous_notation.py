"""
Test continuous futures notation integration.

This module tests that continuous futures notation (e.g., BRN.n.1) 
properly integrates with the continuous futures implementation.
"""

import pytest
from datetime import date
import pandas as pd
import sys
import os

# Add futureskit to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from futureskit import Future, ContinuousFuture, FuturesNotation
from futureskit.continuous import RollRule
from futureskit.contracts import FuturesContract


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
            contracts.append(contract)
        
        return contracts


def test_continuous_notation_parsing():
    """Test that continuous notation is parsed correctly."""
    parser = FuturesNotation()
    
    # Test various continuous notations
    test_cases = [
        ("BRN.n.1", "BRN", "n", 1),     # Front month by open interest
        ("CL.v.2", "CL", "v", 2),       # Second month by volume
        ("HO.c.3", "HO", "c", 3),       # Third month by calendar
        ("NG.fn.1", "NG", "fn", 1),     # Front month by first notice
        ("RB.lt.2", "RB", "lt", 2),     # Second month by last trade
    ]
    
    for notation, expected_root, expected_rule, expected_index in test_cases:
        parsed = parser.parse(notation)
        assert parsed.is_continuous
        assert parsed.root == expected_root
        assert parsed.roll_rule == expected_rule
        assert parsed.contract_index == expected_index


def test_future_continuous_from_notation():
    """Test creating continuous futures from notation."""
    datasource = MockDataSource()
    
    # Create a Future and then continuous with notation
    future = Future("BRN", datasource)
    
    # Test different notations
    continuous_n1 = future.continuous("n.1")  # Front month by OI
    assert continuous_n1.roll_rule == RollRule.OPEN_INTEREST
    assert continuous_n1.depth == 1  # 1-based internally
    
    continuous_v2 = future.continuous("v.2")  # Second month by volume
    assert continuous_v2.roll_rule == RollRule.VOLUME
    assert continuous_v2.depth == 2
    
    continuous_c3 = future.continuous("c.3")  # Third month by calendar
    assert continuous_c3.roll_rule == RollRule.CALENDAR
    assert continuous_c3.depth == 3
    assert continuous_c3.offset == -5  # Default offset for calendar


def test_future_from_notation_regular():
    """Test Future.from_notation with regular contract notation."""
    datasource = MockDataSource()
    
    # Regular contract notation
    future = Future.from_notation("BRN_2024F", datasource)
    assert isinstance(future, Future)
    assert future.root_symbol == "BRN"


def test_future_from_notation_continuous():
    """Test Future.from_notation with continuous notation."""
    datasource = MockDataSource()
    
    # Continuous notation should return ContinuousFuture
    continuous = Future.from_notation("BRN.n.1", datasource)
    assert isinstance(continuous, ContinuousFuture)
    assert continuous.root == "BRN"
    assert continuous.roll_rule == RollRule.OPEN_INTEREST
    assert continuous.depth == 1


def test_continuous_notation_invalid():
    """Test error handling for invalid continuous notation."""
    datasource = MockDataSource()
    future = Future("BRN", datasource)
    
    # Invalid notation formats
    with pytest.raises(ValueError, match="Invalid continuous notation"):
        future.continuous("n1")  # Missing dot
    
    with pytest.raises(ValueError, match="Invalid continuous notation"):
        future.continuous("n.1.extra")  # Too many parts
    
    with pytest.raises(ValueError, match="Must be an integer"):
        future.continuous("n.abc")  # Non-integer depth
    
    with pytest.raises(ValueError, match="Invalid roll rule"):
        future.continuous("x.1")  # Invalid roll rule


def test_continuous_notation_with_kwargs():
    """Test that kwargs override works correctly."""
    datasource = MockDataSource()
    future = Future("BRN", datasource)
    
    # Without notation - use kwargs
    continuous = future.continuous(roll='volume', depth=1, offset=-3)
    assert continuous.roll_rule == RollRule.VOLUME
    assert continuous.depth == 2  # 0-based input becomes 1-based internally
    assert continuous.offset == -3
    
    # With notation - notation overrides kwargs
    continuous = future.continuous("n.1", roll='volume')  # notation wins
    assert continuous.roll_rule == RollRule.OPEN_INTEREST  # From notation, not kwargs


def test_continuous_notation_round_trip():
    """Test that continuous notation can be parsed and recreated."""
    datasource = MockDataSource()
    
    # Parse notation
    parser = FuturesNotation()
    parsed = parser.parse("BRN.n.1")
    
    # Create continuous future from parsed notation
    future = Future(parsed.root, datasource)
    continuous = future.continuous(f"{parsed.roll_rule}.{parsed.contract_index}")
    
    # Verify
    assert continuous.root == "BRN"
    assert continuous.roll_rule == RollRule.OPEN_INTEREST
    assert continuous.depth == 1
    
    # Recreate notation string
    notation_str = parsed.to_string()
    assert notation_str == "BRN.n.1"


def test_all_roll_rules_mapped():
    """Test that all roll rules from design doc are mapped."""
    datasource = MockDataSource()
    future = Future("BRN", datasource)
    
    # All rules from the design document
    roll_rules = {
        'n': RollRule.OPEN_INTEREST,
        'v': RollRule.VOLUME,
        'c': RollRule.CALENDAR,
        'fn': RollRule.CALENDAR,  # Using calendar as placeholder
        'lt': RollRule.CALENDAR,  # Using calendar as placeholder
    }
    
    for notation_rule, expected_enum in roll_rules.items():
        continuous = future.continuous(f"{notation_rule}.1")
        assert continuous.roll_rule == expected_enum


if __name__ == "__main__":
    # Run tests
    print("Testing continuous futures notation integration...")
    print("=" * 60)
    
    tests = [
        ("Notation parsing", test_continuous_notation_parsing),
        ("Future.continuous with notation", test_future_continuous_from_notation),
        ("Future.from_notation regular", test_future_from_notation_regular),
        ("Future.from_notation continuous", test_future_from_notation_continuous),
        ("Invalid notation handling", test_continuous_notation_invalid),
        ("Notation with kwargs", test_continuous_notation_with_kwargs),
        ("Notation round trip", test_continuous_notation_round_trip),
        ("All roll rules mapped", test_all_roll_rules_mapped),
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
        print("All tests passed! Continuous notation integration working correctly.")
    else:
        print(f"Some tests failed. Please review the failures above.")
        sys.exit(1)