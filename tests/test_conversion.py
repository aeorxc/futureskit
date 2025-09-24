"""
Tests for conversion functionality (unit, currency, lots).
"""

import pytest
import pandas as pd
from datetime import date
from unittest.mock import Mock, patch
from dataclasses import dataclass

from futureskit.contracts import FuturesContract
from futureskit.futures import Future
from futureskit.conversion import ConvertibleMixin, ConversionContext


class TestUnitConversion:
    """Test unit conversion functionality"""

    def test_contract_unit_conversion_chainable(self):
        """Test that unit conversions are chainable"""
        # Create a mock future with metadata
        mock_future = Mock()
        mock_future.metadata = {
            'unit': 'bbl',
            'commodity_group': 'crude',
            'Contract_Size': 1000
        }

        # Create contract
        contract = FuturesContract(
            root_symbol='CL',
            year=2026,
            month_code='H',
            future=mock_future
        )

        # Mock price data
        contract._price_data = pd.DataFrame({
            'Close': [80.0, 81.0, 82.0]
        })

        # Chain conversions (without actual commodutil)
        with patch('futureskit.conversion.convfactors') as mock_conv:
            mock_conv.convert_price.return_value = pd.DataFrame({
                'Close': [10.96, 11.10, 11.23]  # Simulated mt prices
            })

            converted = contract.to_unit('mt')

            # Check conversion was called
            mock_conv.convert_price.assert_called_once()
            assert converted.unit == 'mt'
            assert converted._conversion_context.original_unit == 'bbl'
            assert 'unit: bbl -> mt' in converted._conversion_context.conversions_applied

    def test_contract_unit_conversion_immutable(self):
        """Test that conversions return new instances"""
        mock_future = Mock()
        mock_future.metadata = {
            'unit': 'bbl',
            'commodity_group': 'crude',
            'Contract_Size': 1000
        }

        contract = FuturesContract(
            root_symbol='CL',
            year=2026,
            month_code='H',
            future=mock_future
        )

        with patch('futureskit.conversion.convfactors'):
            converted = contract.to_unit('mt')

            # Original should be unchanged
            assert contract.unit == 'bbl'
            assert not hasattr(contract, '_conversion_context')

            # New instance should have conversion
            assert converted.unit == 'mt'
            assert converted is not contract

    def test_skip_same_unit_conversion(self):
        """Test that converting to same unit returns same object"""
        mock_future = Mock()
        mock_future.metadata = {
            'unit': 'bbl',
            'commodity_group': 'crude'
        }

        contract = FuturesContract(
            root_symbol='CL',
            year=2026,
            month_code='H',
            future=mock_future
        )

        # Convert to same unit
        same = contract.to_unit('bbl')
        assert same is contract  # Should be same object


class TestLotConversion:
    """Test lot/volume conversion functionality"""

    def test_lots_to_volume_basic(self):
        """Test basic lot to volume conversion"""
        mock_future = Mock()
        mock_future.metadata = {
            'unit': 'bbl',
            'Contract_Size': 1000,
            'contract_unit': 'bbl',
            'commodity_group': 'crude'
        }

        contract = FuturesContract(
            root_symbol='CL',
            year=2026,
            month_code='H',
            future=mock_future
        )

        # 10 lots = 10,000 barrels
        volume = contract.lots_to_volume(10)
        assert volume == 10000.0

    def test_lots_to_volume_with_unit_conversion(self):
        """Test lot to volume with unit conversion"""
        mock_future = Mock()
        mock_future.metadata = {
            'unit': 'bbl',
            'Contract_Size': 1000,
            'contract_unit': 'bbl',
            'commodity_group': 'crude'
        }

        contract = FuturesContract(
            root_symbol='CL',
            year=2026,
            month_code='H',
            future=mock_future
        )

        with patch('futureskit.conversion.convfactors') as mock_conv:
            # Mock conversion from bbl to mt
            mock_conv.convert_volume.return_value = 1365.7  # ~10,000 bbl in mt

            volume_mt = contract.lots_to_volume(10, 'mt')

            mock_conv.convert_volume.assert_called_once_with(
                10000.0, 'bbl', 'mt', 'crude'
            )
            assert volume_mt == 1365.7

    def test_volume_to_lots_basic(self):
        """Test volume to lots conversion"""
        mock_future = Mock()
        mock_future.metadata = {
            'unit': 'bbl',
            'Contract_Size': 1000,
            'contract_unit': 'bbl',
            'commodity_group': 'crude'
        }

        contract = FuturesContract(
            root_symbol='CL',
            year=2026,
            month_code='H',
            future=mock_future
        )

        # 50,000 barrels = 50 lots
        lots = contract.volume_to_lots(50000, 'bbl')
        assert lots == 50.0

    def test_volume_to_lots_fractional(self):
        """Test volume to lots with fractional result"""
        mock_future = Mock()
        mock_future.metadata = {
            'unit': 'bbl',
            'Contract_Size': 1000,
            'contract_unit': 'bbl',
            'commodity_group': 'crude'
        }

        contract = FuturesContract(
            root_symbol='CL',
            year=2026,
            month_code='H',
            future=mock_future
        )

        # 25,500 barrels = 25.5 lots
        lots = contract.volume_to_lots(25500, 'bbl')
        assert lots == 25.5

    def test_lots_conversion_no_contract_size_error(self):
        """Test error when Contract_Size is missing"""
        mock_future = Mock()
        mock_future.metadata = {
            'unit': 'bbl',
            # No Contract_Size!
        }

        contract = FuturesContract(
            root_symbol='CL',
            year=2026,
            month_code='H',
            future=mock_future
        )

        with pytest.raises(ValueError, match="No Contract_Size defined"):
            contract.lots_to_volume(10)


class TestCurrencyConversion:
    """Test currency conversion placeholder functionality"""

    def test_currency_conversion_placeholder(self):
        """Test that currency conversion is tracked but not implemented"""
        mock_future = Mock()
        mock_future.metadata = {
            'currency': 'USD',
            'unit': 'bbl',
            'commodity_group': 'crude'
        }

        contract = FuturesContract(
            root_symbol='CL',
            year=2026,
            month_code='H',
            future=mock_future
        )

        # Should track intent but not actually convert
        converted = contract.to_currency('EUR')

        assert converted.currency == 'EUR'
        assert converted._conversion_context.original_currency == 'USD'
        assert 'currency: USD -> EUR [pending]' in converted._conversion_context.conversions_applied

    def test_currency_skip_same(self):
        """Test that converting to same currency returns same object"""
        mock_future = Mock()
        mock_future.metadata = {
            'currency': 'USD',
            'unit': 'bbl'
        }

        contract = FuturesContract(
            root_symbol='CL',
            year=2026,
            month_code='H',
            future=mock_future
        )

        same = contract.to_currency('USD')
        assert same is contract


class TestChainableConversions:
    """Test chaining multiple conversions"""

    def test_chain_unit_and_currency(self):
        """Test chaining unit and currency conversions"""
        mock_future = Mock()
        mock_future.metadata = {
            'unit': 'bbl',
            'currency': 'USD',
            'commodity_group': 'crude',
            'Contract_Size': 1000
        }

        contract = FuturesContract(
            root_symbol='CL',
            year=2026,
            month_code='H',
            future=mock_future
        )

        with patch('futureskit.conversion.convfactors'):
            # Chain conversions
            converted = contract.to_unit('mt').to_currency('EUR')

            # Check both conversions tracked
            assert converted.unit == 'mt'
            assert converted.currency == 'EUR'
            assert len(converted._conversion_context.conversions_applied) == 2
            assert 'unit: bbl -> mt' in converted._conversion_context.conversions_applied
            assert 'currency: USD -> EUR [pending]' in converted._conversion_context.conversions_applied

    def test_conversion_history_property(self):
        """Test conversion_history property"""
        mock_future = Mock()
        mock_future.metadata = {
            'unit': 'bbl',
            'currency': 'USD',
            'commodity_group': 'crude'
        }

        contract = FuturesContract(
            root_symbol='CL',
            year=2026,
            month_code='H',
            future=mock_future
        )

        # No conversions yet
        assert contract.conversion_history == []

        with patch('futureskit.conversion.convfactors'):
            converted = contract.to_unit('mt').to_currency('EUR')

            # Should have conversion history
            history = converted.conversion_history
            assert len(history) == 2
            assert history[0] == 'unit: bbl -> mt'
            assert history[1] == 'currency: USD -> EUR [pending]'


class TestMetadataHandling:
    """Test metadata handling in conversions"""

    def test_metadata_updates_on_conversion(self):
        """Test that Future metadata is updated on conversion"""
        mock_future = Mock()
        mock_future.metadata = {
            'unit': 'bbl',
            'commodity_group': 'crude'
        }

        contract = FuturesContract(
            root_symbol='CL',
            year=2026,
            month_code='H',
            future=mock_future
        )

        with patch('futureskit.conversion.convfactors'):
            converted = contract.to_unit('mt')

            # Future metadata should be updated
            assert converted.future.metadata['unit'] == 'mt'
            assert converted.future.metadata['original_unit'] == 'bbl'

    def test_metadata_fallback_without_future(self):
        """Test metadata access without future reference"""
        # Contract without future reference
        contract = FuturesContract(
            root_symbol='CL',
            year=2026,
            month_code='H'
        )

        # Set metadata directly
        contract._metadata = {
            'unit': 'bbl',
            'commodity_group': 'crude',
            'Contract_Size': 1000,
            'contract_unit': 'bbl'
        }

        # Should still work
        assert contract.unit == 'bbl'
        assert contract._get_commodity_group() == 'crude'
        assert contract._get_contract_size() == 1000

        volume = contract.lots_to_volume(5)
        assert volume == 5000.0