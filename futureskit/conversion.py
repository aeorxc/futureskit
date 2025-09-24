"""
Conversion utilities for futures contracts.

This module provides mixins and utilities for converting between units, currencies,
and lots/volumes for futures contracts.
"""

from typing import Optional, List, Any, TYPE_CHECKING
from dataclasses import dataclass, replace
from copy import deepcopy
import logging

if TYPE_CHECKING:
    import pandas as pd

logger = logging.getLogger(__name__)

# Import commodutil for unit conversions if available
try:
    from commodutil import convfactors
    HAS_COMMODUTIL = True
except ImportError:
    HAS_COMMODUTIL = False
    logger.warning("commodutil not available - unit conversions will be limited")


@dataclass
class ConversionContext:
    """Tracks conversion history and context."""
    original_unit: Optional[str] = None
    current_unit: Optional[str] = None
    original_currency: Optional[str] = None
    current_currency: Optional[str] = None
    conversions_applied: List[str] = None

    def __post_init__(self):
        if self.conversions_applied is None:
            self.conversions_applied = []


class ConvertibleMixin:
    """
    Mixin that adds unit, currency, and lot conversion capabilities.

    Classes using this mixin should implement:
    - unit property (current unit)
    - currency property (current currency)
    - data property (pandas DataFrame with price data)
    - _get_commodity_group() method
    - _get_contract_size() method
    - _get_contract_unit() method
    - _get_symbol() method for logging
    """

    def to_unit(self, target_unit: str) -> 'ConvertibleMixin':
        """
        Convert prices to a different unit.

        Args:
            target_unit: Target unit (e.g., 'mt', 'gal', 'bbl')

        Returns:
            New instance with converted prices and updated unit
        """
        current_unit = self.unit

        # Skip if same unit
        if current_unit == target_unit:
            return self

        if not HAS_COMMODUTIL:
            raise ImportError("commodutil required for unit conversions. Install with: pip install commodutil")

        # Create a copy for immutability
        new_obj = self._copy_for_conversion()

        # Initialize conversion context if needed
        if not hasattr(new_obj, '_conversion_context'):
            new_obj._conversion_context = ConversionContext(
                original_unit=current_unit,
                current_unit=current_unit
            )

        # Get commodity group for conversion
        commodity_group = new_obj._get_commodity_group()

        # Convert price data if available
        if hasattr(new_obj, 'data') and new_obj.data is not None:
            try:
                # Convert using commodutil
                converted_data = convfactors.convert_price(
                    new_obj.data,
                    current_unit,
                    target_unit,
                    commodity_group
                )
                new_obj.data = converted_data
            except Exception as e:
                logger.error(f"Failed to convert {new_obj._get_symbol()} from {current_unit} to {target_unit}: {e}")
                raise

        # Update context
        new_obj._conversion_context.current_unit = target_unit
        new_obj._conversion_context.conversions_applied.append(f"unit: {current_unit} -> {target_unit}")

        # Update metadata if object has future reference
        if hasattr(new_obj, 'future') and new_obj.future:
            if hasattr(new_obj.future, 'metadata'):
                new_obj.future.metadata = new_obj.future.metadata.copy() if new_obj.future.metadata else {}
                new_obj.future.metadata['unit'] = target_unit
                new_obj.future.metadata['original_unit'] = new_obj._conversion_context.original_unit

        return new_obj

    def to_currency(self, target_currency: str, fx_provider=None) -> 'ConvertibleMixin':
        """
        Convert prices to a different currency.

        Args:
            target_currency: Target currency code (e.g., 'EUR', 'GBP')
            fx_provider: Optional FX rate provider (future implementation)

        Returns:
            New instance with converted prices and updated currency

        Note:
            Currency conversion is not yet implemented. This method currently
            only tracks the conversion request for future implementation.
        """
        current_currency = self.currency

        # Skip if same currency
        if current_currency == target_currency:
            return self

        # Create a copy for immutability
        new_obj = self._copy_for_conversion()

        # Initialize conversion context if needed
        if not hasattr(new_obj, '_conversion_context'):
            new_obj._conversion_context = ConversionContext(
                original_currency=current_currency,
                current_currency=current_currency
            )

        # TODO: Implement actual currency conversion when FX provider is available
        # For now, just track the conversion request
        new_obj._conversion_context.current_currency = target_currency
        new_obj._conversion_context.conversions_applied.append(
            f"currency: {current_currency} -> {target_currency} [pending]"
        )

        # Update metadata if object has future reference
        if hasattr(new_obj, 'future') and new_obj.future:
            if hasattr(new_obj.future, 'metadata'):
                new_obj.future.metadata = new_obj.future.metadata.copy() if new_obj.future.metadata else {}
                new_obj.future.metadata['currency'] = target_currency
                new_obj.future.metadata['original_currency'] = new_obj._conversion_context.original_currency

        logger.info(f"Currency conversion from {current_currency} to {target_currency} tracked (not yet implemented)")

        return new_obj

    def lots_to_volume(self, num_lots: float, unit: Optional[str] = None) -> float:
        """
        Convert number of lots to volume.

        Args:
            num_lots: Number of futures lots
            unit: Optional target unit for volume. If not specified, uses contract unit.

        Returns:
            Volume in specified unit

        Example:
            >>> contract.lots_to_volume(10)  # 10 CL lots = 10,000 barrels
            10000.0
            >>> contract.lots_to_volume(10, 'mt')  # Convert to metric tons
            1365.7
        """
        contract_size = self._get_contract_size()
        if contract_size is None:
            raise ValueError(f"No Contract_Size defined for {self._get_symbol()}")

        contract_unit = self._get_contract_unit()

        # Calculate volume in contract units
        volume = num_lots * contract_size

        # If no target unit specified, return in contract units
        if unit is None or unit == contract_unit:
            return volume

        # Convert to target unit
        if not HAS_COMMODUTIL:
            raise ImportError("commodutil required for unit conversions. Install with: pip install commodutil")

        commodity_group = self._get_commodity_group()

        try:
            converted_volume = convfactors.convert_volume(
                volume,
                contract_unit,
                unit,
                commodity_group
            )
            return converted_volume
        except Exception as e:
            logger.error(f"Failed to convert volume from {contract_unit} to {unit}: {e}")
            raise

    def volume_to_lots(self, volume: float, unit: Optional[str] = None) -> float:
        """
        Convert volume to number of lots.

        Args:
            volume: Volume amount
            unit: Unit of the volume (defaults to contract unit)

        Returns:
            Number of futures lots (can be fractional)

        Example:
            >>> contract.volume_to_lots(50000, 'bbl')  # 50,000 barrels = 50 CL lots
            50.0
            >>> contract.volume_to_lots(6828.5, 'mt')  # metric tons to lots
            50.0
        """
        contract_size = self._get_contract_size()
        if contract_size is None:
            raise ValueError(f"No Contract_Size defined for {self._get_symbol()}")

        contract_unit = self._get_contract_unit()

        # If unit not specified, assume contract unit
        if unit is None:
            unit = contract_unit

        # Convert volume to contract units if needed
        if unit != contract_unit:
            if not HAS_COMMODUTIL:
                raise ImportError("commodutil required for unit conversions. Install with: pip install commodutil")

            commodity_group = self._get_commodity_group()

            try:
                volume = convfactors.convert_volume(
                    volume,
                    unit,
                    contract_unit,
                    commodity_group
                )
            except Exception as e:
                logger.error(f"Failed to convert volume from {unit} to {contract_unit}: {e}")
                raise

        # Calculate number of lots
        num_lots = volume / contract_size
        return num_lots

    @property
    def conversion_history(self) -> List[str]:
        """
        Get list of conversions applied to this object.

        Returns:
            List of conversion descriptions
        """
        if hasattr(self, '_conversion_context') and self._conversion_context:
            return self._conversion_context.conversions_applied
        return []

    def _copy_for_conversion(self) -> 'ConvertibleMixin':
        """
        Create a copy of the object for conversion.

        Default implementation uses deepcopy. Override if needed.
        """
        return deepcopy(self)

    # Abstract methods that subclasses should implement
    def _get_commodity_group(self) -> str:
        """Get commodity group for conversion calculations."""
        raise NotImplementedError

    def _get_contract_size(self) -> Optional[float]:
        """Get contract size for lot calculations."""
        raise NotImplementedError

    def _get_contract_unit(self) -> str:
        """Get contract unit for lot calculations."""
        raise NotImplementedError

    def _get_symbol(self) -> str:
        """Get symbol string for logging."""
        raise NotImplementedError