"""Immutable parameters for continuous-series construction."""

from __future__ import annotations

from collections.abc import Hashable, Iterator, Mapping
from dataclasses import dataclass, field
from datetime import date, datetime
from enum import Enum
from typing import Any, TypeAlias


def _positive_integer(value: Any, name: str) -> None:
    if not isinstance(value, int) or isinstance(value, bool) or value < 1:
        raise ValueError(f"{name} must be a positive integer")


def _non_negative_integer(value: Any, name: str) -> None:
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise ValueError(f"{name} must be a non-negative integer")


def _plain_datetime(value: datetime) -> datetime:
    """Copy a datetime subclass without changing its timezone semantics."""
    if not isinstance(value.year, int):
        raise ValueError(  # noqa: TRY004 -- datetime-like NaT is an invalid value
            "datetime identity must not be NaT"
        )
    if type(value) is datetime:
        return value
    converter = getattr(value, "to_pydatetime", None)
    if converter is not None:
        converted = converter(warn=False)
        if type(converted) is datetime:
            return converted
    return datetime(
        value.year,
        value.month,
        value.day,
        value.hour,
        value.minute,
        value.second,
        value.microsecond,
        tzinfo=value.tzinfo,
        fold=value.fold,
    )


def _plain_expiry(value: Any) -> date | datetime:
    """Validate and copy an expiry value into a standard-library object."""
    if isinstance(value, datetime):
        if value.tzinfo is not None:
            raise ValueError("anchor_expiries values must be timezone-naive")
        return _plain_datetime(value)
    if isinstance(value, date):
        return date(value.year, value.month, value.day)
    raise ValueError("anchor_expiries values must be date-like")


def _plain_identity(value: Hashable) -> Hashable:
    if isinstance(value, datetime):
        return _plain_datetime(value)
    if isinstance(value, date):
        return date(value.year, value.month, value.day)
    if isinstance(value, tuple):
        return tuple(_plain_identity(item) for item in value)
    if isinstance(value, frozenset):
        return frozenset(_plain_identity(item) for item in value)
    return value


@dataclass(frozen=True, slots=True, eq=False)
class FrozenExpiryMap(Mapping[Hashable, date | datetime]):
    """Hashable, insertion-ordered copy of an expiry mapping."""

    _items: tuple[tuple[Hashable, date | datetime], ...]

    @classmethod
    def from_mapping(cls, values: Mapping[Hashable, Any]) -> FrozenExpiryMap:
        if not isinstance(values, Mapping):
            raise TypeError("anchor_expiries must be a mapping or None")
        items: list[tuple[Hashable, date | datetime]] = []
        seen: set[Hashable] = set()
        for identity, expiry in values.items():
            try:
                hash(identity)
            except TypeError as exc:
                raise ValueError("anchor_expiries keys must be hashable") from exc
            normalized_identity = _plain_identity(identity)
            if normalized_identity in seen:
                raise ValueError(
                    "anchor_expiries keys must be unique after normalization"
                )
            seen.add(normalized_identity)
            items.append((normalized_identity, _plain_expiry(expiry)))
        return cls(tuple(items))

    def __getitem__(self, key: Hashable) -> date | datetime:
        normalized_key = _plain_identity(key)
        for identity, expiry in self._items:
            if identity == normalized_key:
                return expiry
        raise KeyError(key)

    def __iter__(self) -> Iterator[Hashable]:
        return (identity for identity, _ in self._items)

    def __len__(self) -> int:
        return len(self._items)

    def __hash__(self) -> int:
        return hash(frozenset(self._items))


@dataclass(frozen=True, slots=True)
class ExpiryOffset:
    """Roll a number of observed trading days before expiry, inclusively.

    ``days=N`` is the existing futureskit ``roll_days=N`` convention: always
    exactly ``N`` printing days before the anchor, with no exceptions.
    Marketplace ``rollDays=N`` matches it exactly at ``N=0`` and ``N=1``. For
    larger ``N`` Marketplace subtracts calendar days and snaps forward to the
    next trading day, so its offset varies with the calendar and saturates over
    long weekends; there is no exact mapping above one. Expiry schedules are
    known before the roll date, so this rule requires no future observations.
    """

    days: int = 0
    lookahead_days: int = 0

    def __post_init__(self) -> None:
        _non_negative_integer(self.days, "days")
        _non_negative_integer(self.lookahead_days, "lookahead_days")
        if self.lookahead_days:
            raise ValueError("expiry-offset rolls cannot use future observations")


RollRule: TypeAlias = ExpiryOffset


class Adjustment(str, Enum):
    """Continuous-series adjustment axis.

    ``PERPETUAL`` and ``INTERPOLATED`` both name the observation-based linear
    blend implemented by :func:`futureskit.forwards.generate_series`.
    Ratio modes require both roll-date prices to be strictly positive; use a
    spread mode when either price is zero or negative.
    """

    NONE = "none"
    BACKWARD_SPREAD = "backward_spread"
    FORWARD_SPREAD = "forward_spread"
    BACKWARD_RATIO = "backward_ratio"
    FORWARD_RATIO = "forward_ratio"
    PERPETUAL = "perpetual"
    INTERPOLATED = "interpolated"


@dataclass(frozen=True, slots=True)
class RollSpec:
    """Data-only specification of one continuous-series roll convention."""

    depth: int = 1
    month_filter: tuple[int, ...] | int | None = None
    roll_rule: RollRule = field(default_factory=ExpiryOffset)
    adjustment: Adjustment = Adjustment.NONE
    interpolate_days: int = 0
    anchor_expiries: FrozenExpiryMap | Mapping[Hashable, Any] | None = None

    def __post_init__(self) -> None:
        _positive_integer(self.depth, "depth")
        _non_negative_integer(self.interpolate_days, "interpolate_days")
        if not isinstance(self.roll_rule, ExpiryOffset):
            raise TypeError("roll_rule must be an ExpiryOffset")
        if not isinstance(self.adjustment, Adjustment):
            raise TypeError("adjustment must be an Adjustment")

        months = self.month_filter
        if months is not None:
            try:
                months = (months,) if isinstance(months, int) else tuple(months)
            except TypeError as exc:
                raise ValueError("month_filter must be an integer or iterable") from exc
            if not months:
                raise ValueError("month_filter must not be empty")
            if any(
                not isinstance(month, int)
                or isinstance(month, bool)
                or month not in range(1, 13)
                for month in months
            ):
                raise ValueError("month_filter values must be integers from 1 to 12")
            object.__setattr__(self, "month_filter", tuple(sorted(set(months))))

        blending = self.adjustment in {
            Adjustment.PERPETUAL,
            Adjustment.INTERPOLATED,
        }
        if blending and self.interpolate_days == 0:
            raise ValueError("blended adjustments require interpolate_days > 0")
        if not blending and self.interpolate_days:
            raise ValueError(
                "interpolate_days is only valid for perpetual or interpolated adjustment"
            )

        anchors = self.anchor_expiries
        if anchors is not None:
            anchors = FrozenExpiryMap.from_mapping(anchors)
            object.__setattr__(self, "anchor_expiries", anchors)


def resolve_roll_spec(roll_spec: RollSpec | None, roll_days: int | None) -> RollSpec:
    """Resolve the preferred specification or the legacy roll-days argument."""
    if roll_spec is not None:
        if not isinstance(roll_spec, RollSpec):
            raise ValueError("roll_spec must be a RollSpec or None")
        if roll_days is not None:
            raise ValueError("roll_spec and roll_days are mutually exclusive")
        return roll_spec
    days = 0 if roll_days is None else roll_days
    return RollSpec(roll_rule=ExpiryOffset(days=days))
