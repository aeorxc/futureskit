"""
Tests for futures notation parsing.
"""

import pytest
from datetime import datetime
from futureskit import FuturesNotation, ParsedSymbol


class TestFuturesNotation:
    """Test the FuturesNotation parser."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.notation = FuturesNotation()
    
    def test_canonical_format(self):
        """Test parsing canonical format ROOT_YYYYM."""
        result = self.notation.parse("BRN_2026F")
        
        assert result.root == "BRN"
        assert result.year == 2026
        assert result.month == "F"
        assert result.is_continuous is False
        assert result.warnings == []
        assert result.to_string() == "BRN_2026F"
    
    def test_short_year_format(self):
        """Test parsing 2-digit year format."""
        # Test BRN26F format
        result = self.notation.parse("BRN26F")
        assert result.root == "BRN"
        assert result.year == 2026  # Assumes current century for near dates
        assert result.month == "F"
        assert result.to_string() == "BRN_2026F"
        
        # Test far future dates (should use previous century)
        result = self.notation.parse("BRN99Z")
        # 99 is more than 10 years from current, so should be 1999
        assert result.year == 1999
    
    def test_month_before_year_format(self):
        """Test parsing BRNF26 format."""
        result = self.notation.parse("BRNF26")
        assert result.root == "BRN"
        assert result.year == 2026
        assert result.month == "F"
        assert result.to_string() == "BRN_2026F"
    
    def test_with_separators(self):
        """Test parsing with separators."""
        # Test with hyphen
        result = self.notation.parse("BRN-26F")
        assert result.root == "BRN"
        assert result.year == 2026
        assert result.month == "F"
        
        # Test with space
        result = self.notation.parse("BRN 26F")
        assert result.root == "BRN"
        assert result.year == 2026
        assert result.month == "F"
    
    def test_continuous_contract(self):
        """Test parsing continuous contract notation."""
        # Front month by open interest
        result = self.notation.parse("BRN.n.1")
        assert result.root == "BRN"
        assert result.is_continuous is True
        assert result.roll_rule == "n"
        assert result.contract_index == 1
        assert result.to_string() == "BRN.n.1"
        
        # Third month by volume
        result = self.notation.parse("CL.v.3")
        assert result.root == "CL"
        assert result.roll_rule == "v"
        assert result.contract_index == 3
        assert result.to_string() == "CL.v.3"
    
    def test_all_month_codes(self):
        """Test all valid month codes."""
        month_codes = ['F', 'G', 'H', 'J', 'K', 'M', 'N', 'Q', 'U', 'V', 'X', 'Z']
        
        for code in month_codes:
            result = self.notation.parse(f"CL_2026{code}")
            assert result.month == code
            assert result.warnings == []
    
    def test_invalid_month_code(self):
        """Test handling of invalid month codes."""
        result = self.notation.parse("BRN_2026A")
        
        assert result.root == "BRN"
        assert result.year == 2026
        assert result.month == "A"  # Keep invalid month but add warning
        assert "Invalid month code: A" in result.warnings
        assert not result.is_valid()  # Should not be valid with invalid month
    
    def test_invalid_roll_rule(self):
        """Test handling of invalid roll rules."""
        result = self.notation.parse("BRN.x.1")
        
        assert result.root == "BRN"
        assert result.roll_rule == "x"
        assert result.contract_index == 1
        assert "Unknown roll rule: x" in result.warnings
    
    def test_zero_based_index_warning(self):
        """Test warning for 0-based index."""
        result = self.notation.parse("BRN.n.0")
        
        assert result.contract_index == 0
        assert "Contract index should be 1-based, got: 0" in result.warnings
    
    def test_partial_parse(self):
        """Test partial parsing of malformed symbols."""
        # Symbol with no valid pattern
        result = self.notation.parse("BRN2026")
        
        assert result.root == "BRN"
        assert result.year == 2026
        assert result.month is None
        assert "Could not fully parse symbol: BRN2026" in result.warnings
    
    def test_empty_symbol(self):
        """Test handling of empty symbol."""
        result = self.notation.parse("")
        
        assert result.root == ""
        assert "Empty symbol provided" in result.warnings
        assert not result.is_valid()
    
    def test_case_insensitive(self):
        """Test case insensitive parsing."""
        result = self.notation.parse("brn_2026f")
        
        assert result.root == "BRN"
        assert result.month == "F"
        assert result.to_string() == "BRN_2026F"
    
    def test_is_futures_symbol(self):
        """Test is_futures_symbol method."""
        assert self.notation.is_futures_symbol("BRN_2026F") is True
        assert self.notation.is_futures_symbol("BRN.n.1") is True
        assert self.notation.is_futures_symbol("BRN") is False
        assert self.notation.is_futures_symbol("") is False
        assert self.notation.is_futures_symbol("INVALID") is False
    
    def test_is_valid_method(self):
        """Test ParsedSymbol.is_valid() method."""
        # Valid regular futures
        result = self.notation.parse("BRN_2026F")
        assert result.is_valid() is True
        
        # Valid continuous
        result = self.notation.parse("BRN.n.1")
        assert result.is_valid() is True
        
        # Invalid - missing month
        result = self.notation.parse("BRN_2026")
        assert result.is_valid() is False
        
        # Invalid - missing index
        result = ParsedSymbol(root="BRN", is_continuous=True, roll_rule="n")
        assert result.is_valid() is False
    
    def test_complex_roots(self):
        """Test parsing symbols with complex roots."""
        # Multi-character roots
        result = self.notation.parse("GOLD_2026F")
        assert result.root == "GOLD"
        assert result.year == 2026
        assert result.month == "F"
        
        # With numbers (though unusual)
        result = self.notation.parse("ES1_2026F")
        assert result.root == "ES"  # Numbers not included in root pattern
        assert result.year == 2026
        assert result.month == "F"