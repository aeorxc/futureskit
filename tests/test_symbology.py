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
    
    def test_to_tradingview_format(self):
        """Test conversion to TradingView format."""
        # Regular contract with feed
        parsed = self.notation.parse("BRN_2026F")
        vendor_map = {'tradingview_symbol': 'BRN', 'tradingview_exchange': 'ICEEUR'}
        result = self.converter.to_tradingview_format(parsed, vendor_map, include_feed=True)
        assert result == "ICEEUR:BRNF26"
        
        # Without feed
        result = self.converter.to_tradingview_format(parsed, vendor_map, include_feed=False)
        assert result == "BRNF26"
        
        # Without vendor_map
        result = self.converter.to_tradingview_format(parsed, {}, include_feed=True)
        assert result == "BRNF26"
        
        # Continuous
        parsed = self.notation.parse("BRN.n.1")
        result = self.converter.to_tradingview_format(parsed, vendor_map, include_feed=True)
        assert result == "ICEEUR:BRN1!"
        
        # Continuous without feed
        result = self.converter.to_tradingview_format(parsed, vendor_map, include_feed=False)
        assert result == "BRN1!"
    
    def test_to_refinitiv_format(self):
        """Test conversion to Refinitiv format."""
        # Regular contract with vendor mapping
        parsed = self.notation.parse("BRN_2026F")
        vendor_map = {'refinitiv_symbol': 'LCO'}
        result = self.converter.to_refinitiv_format(parsed, vendor_map)
        assert result == "LCOF6"
        
        # Without vendor_map - should use root symbol
        result = self.converter.to_refinitiv_format(parsed, {})
        assert result == "BRNF6"
        
        # Continuous
        parsed = self.notation.parse("BRN.n.1")
        result = self.converter.to_refinitiv_format(parsed, vendor_map)
        assert result == "LCOc1"
        
        # Continuous without vendor_map
        result = self.converter.to_refinitiv_format(parsed, {})
        assert result == "BRNc1"
    
    def test_high_level_vendor_methods(self):
        """Test high-level convenience methods."""
        # TradingView
        result = SymbologyConverter.tradingview(
            'BRN', {'tradingview_symbol': 'BRN', 'tradingview_exchange': 'ICEEUR'},
            year=2026, month='H', include_feed=True
        )
        assert result == "ICEEUR:BRNH26"
        
        # TradingView without feed
        result = SymbologyConverter.tradingview(
            'BRN', {'tradingview_symbol': 'BRN', 'tradingview_exchange': 'ICEEUR'},
            year=2026, month='H', include_feed=False
        )
        assert result == "BRNH26"
        
        # TradingView continuous
        result = SymbologyConverter.tradingview(
            'BRN', {'tradingview_symbol': 'BRN', 'tradingview_exchange': 'ICEEUR'},
            continuous_index=1, include_feed=True
        )
        assert result == "ICEEUR:BRN1!"
        
        # Refinitiv
        result = SymbologyConverter.refinitiv(
            'BRN', {'refinitiv_symbol': 'LCO'},
            year=2026, month='H'
        )
        assert result == "LCOH6"
        
        # Refinitiv continuous
        result = SymbologyConverter.refinitiv(
            'BRN', {'refinitiv_symbol': 'LCO'},
            continuous_index=1
        )
        assert result == "LCOc1"


class TestDataSourceURLGeneration:
    """Test URL generation in datasources."""
    
    def test_tradingview_datasource_urls(self):
        """Test TradingView datasource URL generation."""
        from futureskit.datasources import TradingViewDataSource
        
        tv = TradingViewDataSource()
        
        # Test contract URL
        urls = tv.get_contract_url('BRN', 2026, 'H')
        assert 'tradingview' in urls
        assert 'BRNH2026' in urls['tradingview']
        # Note: Contract URLs now have both chart and overview
        
        # Test continuous URL
        urls = tv.get_continuous_url('BRN', 1)
        assert 'BRN1!' in urls['tradingview']
        
        # Test symbol without mapping (should just use the symbol as-is)
        urls = tv.get_contract_url('XYZ', 2026, 'H')
        assert 'XYZH2026' in urls['tradingview']
    
    def test_refinitiv_datasource_urls(self):
        """Test Refinitiv datasource URL generation."""
        from futureskit.datasources import RefinitivDataSource
        
        ref = RefinitivDataSource()
        
        # Test contract URL (expects RIC symbol)
        urls = ref.get_contract_url('LCO', 2026, 'H')
        assert 'refinitiv' in urls
        assert 'LCOH6' in urls['refinitiv']
        
        # Test continuous URL
        urls = ref.get_continuous_url('LCO', 1)
        assert 'LCOc1' in urls['refinitiv']
    
    def test_datasource_data_methods_not_implemented(self):
        """Test that data methods raise NotImplementedError."""
        from futureskit.datasources import TradingViewDataSource, RefinitivDataSource
        
        tv = TradingViewDataSource()
        ref = RefinitivDataSource()
        
        with pytest.raises(NotImplementedError):
            tv.series(['BRN'])
        
        with pytest.raises(NotImplementedError):
            ref.curve(['BRN'])
        
        with pytest.raises(NotImplementedError):
            tv.contracts(['BRN'])
        
        with pytest.raises(NotImplementedError):
            ref.series(['BRN'])
    
    def test_datasource_supports_url_generation(self):
        """Test that datasources report they support URL generation."""
        from futureskit.datasources import TradingViewDataSource, RefinitivDataSource
        
        tv = TradingViewDataSource()
        ref = RefinitivDataSource()
        
        assert tv.supports_url_generation() == True
        assert ref.supports_url_generation() == True
    
    def test_tradingview_contract_chain(self):
        """Test TradingView mock contract chain generation."""
        from futureskit.datasources import TradingViewDataSource
        
        tv = TradingViewDataSource()
        contracts = tv.get_contract_chain('BRN')
        
        # Should generate 12 monthly contracts
        assert len(contracts) == 12
        
        # Check first contract
        first = contracts[0]
        assert first.root_symbol == 'BRN'
        assert first.datasource == tv
    
    def test_refinitiv_contract_chain(self):
        """Test Refinitiv contract chain (currently empty)."""
        from futureskit.datasources import RefinitivDataSource
        
        ref = RefinitivDataSource()
        contracts = ref.get_contract_chain('BRN')
        
        # Should return empty list for now
        assert contracts == []