"""
Tests for symbology conversion.
"""

import pytest
from futureskit import FuturesNotation
from futureskit.symbology import SymbologyConverter, FeedConventions


class TestSymbologyConverter:
    """Test the SymbologyConverter."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.notation = FuturesNotation()
        self.converter = SymbologyConverter()
    
    def test_to_cme_format_regular(self):
        """Test conversion to CME format for regular futures."""
        parsed = self.notation.parse("BRN_2026F")
        result = self.converter.to_cme_format(parsed)
        assert result == "@BRN26F"
        
        # Test with different year
        parsed = self.notation.parse("CL_2024Z")
        result = self.converter.to_cme_format(parsed)
        assert result == "@CL24Z"
    
    def test_to_cme_format_continuous(self):
        """Test conversion to CME format for continuous contracts."""
        # Front month
        parsed = self.notation.parse("BRN.n.1")
        result = self.converter.to_cme_format(parsed)
        assert result == "@BRN"
        
        # Second month
        parsed = self.notation.parse("CL.v.2")
        result = self.converter.to_cme_format(parsed)
        assert result == "@CL2"
    
    def test_to_ice_format_regular(self):
        """Test conversion to ICE format for regular futures."""
        parsed = self.notation.parse("BRN_2026F")
        result = self.converter.to_ice_format(parsed)
        assert result == "BRN26F"
        
        parsed = self.notation.parse("GASO_2025M")
        result = self.converter.to_ice_format(parsed)
        assert result == "GASO25M"
    
    def test_to_ice_format_continuous(self):
        """Test conversion to ICE format for continuous contracts."""
        # Front month
        parsed = self.notation.parse("BRN.n.1")
        result = self.converter.to_ice_format(parsed)
        assert result == "BRN"
        
        # Third month
        parsed = self.notation.parse("BRN.n.3")
        result = self.converter.to_ice_format(parsed)
        assert result == "BRNM3"
    
    def test_to_bloomberg_format(self):
        """Test conversion to Bloomberg format."""
        # Brent
        parsed = self.notation.parse("BRN_2026F")
        result = self.converter.to_bloomberg_format(parsed)
        assert result == "COF6 Comdty"
        
        # WTI
        parsed = self.notation.parse("CL_2024Z")
        result = self.converter.to_bloomberg_format(parsed)
        assert result == "CLZ4 Comdty"
        
        # Continuous
        parsed = self.notation.parse("BRN.n.1")
        result = self.converter.to_bloomberg_format(parsed)
        assert result == "CO1 Comdty"
        
        parsed = self.notation.parse("CL.n.3")
        result = self.converter.to_bloomberg_format(parsed)
        assert result == "CL3 Comdty"
    
    def test_to_short_year_format(self):
        """Test conversion to short year format."""
        parsed = self.notation.parse("BRN_2026F")
        result = self.converter.to_short_year_format(parsed)
        assert result == "BRN26F"
        
        # Test century rollover
        parsed = self.notation.parse("CL_2100M")
        result = self.converter.to_short_year_format(parsed)
        assert result == "CL00M"
    
    def test_to_marketplace_continuous(self):
        """Test conversion to marketplace continuous format."""
        parsed = self.notation.parse("BRN.n.1")
        result = self.converter.to_marketplace_continuous(parsed)
        assert result == "BRN_001_MONTH"
        
        parsed = self.notation.parse("CL.v.12")
        result = self.converter.to_marketplace_continuous(parsed)
        assert result == "CL_012_MONTH"
    
    def test_invalid_symbol_handling(self):
        """Test handling of invalid or incomplete symbols."""
        # No root
        parsed = self.notation.parse("")
        assert self.converter.to_cme_format(parsed) is None
        assert self.converter.to_ice_format(parsed) is None
        
        # Missing components
        from futureskit import ParsedSymbol
        partial = ParsedSymbol(root="BRN", year=2026)  # No month
        assert self.converter.to_cme_format(partial) is None
        assert self.converter.to_short_year_format(partial) is None
    
    def test_edge_cases(self):
        """Test additional edge cases for coverage."""
        # Test CME format with None check (line 80)
        parsed = self.notation.parse("XYZ_2026")
        assert self.converter.to_ice_format(parsed) is None
        
        # Test Bloomberg with None check (line 93)
        empty_parsed = self.notation.parse("")
        assert self.converter.to_bloomberg_format(empty_parsed) is None
        
        # Test Bloomberg with non-continuous, unknown root (line 116)
        parsed = self.notation.parse("XYZ_2026F")
        result = self.converter.to_bloomberg_format(parsed)
        assert result == "XYZF6 Comdty"
        
        # Test marketplace continuous with non-continuous symbol (line 140)
        parsed = self.notation.parse("BRN_2026F")
        assert self.converter.to_marketplace_continuous(parsed) is None
    
    def test_feed_conventions(self):
        """Test FeedConventions utility class."""
        assert FeedConventions.add_cme_prefix("CL26F") == "@CL26F"
        assert FeedConventions.add_ice_suffix("BRN26F") == "BRN26F.L"
    
    def test_unknown_commodity_bloomberg(self):
        """Test Bloomberg format for unknown commodity."""
        parsed = self.notation.parse("XYZ_2026F")
        result = self.converter.to_bloomberg_format(parsed)
        # Should use root as-is for unknown commodities
        assert result == "XYZF6 Comdty"
    
    def test_all_converters_with_same_input(self):
        """Test all converters with the same input."""
        parsed = self.notation.parse("BRN_2026F")
        
        results = {
            'canonical': parsed.to_string(),
            'cme': self.converter.to_cme_format(parsed),
            'ice': self.converter.to_ice_format(parsed),
            'bloomberg': self.converter.to_bloomberg_format(parsed),
            'short_year': self.converter.to_short_year_format(parsed),
        }
        
        expected = {
            'canonical': 'BRN_2026F',
            'cme': '@BRN26F',
            'ice': 'BRN26F',
            'bloomberg': 'COF6 Comdty',
            'short_year': 'BRN26F',
        }
        
        assert results == expected