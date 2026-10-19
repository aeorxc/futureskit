"""Tests for strict canonical futures contract parsing."""

from datetime import date

import pytest

from futureskit import (
    FuturesNotation,
    MONTH_CODES,
    ParsedSymbol,
)
from futureskit.exceptions import InvalidMonthCodeError


@pytest.fixture
def notation():
    return FuturesNotation()


@pytest.mark.parametrize("month", MONTH_CODES)
def test_parse_canonical_contract_accepts_every_month_code(notation, month):
    parsed = notation.parse_canonical_contract(f"CL_2026{month}")

    assert parsed is not None
    assert parsed.root == "CL"
    assert parsed.year == 2026
    assert parsed.month == month
    assert parsed.kind == "contract"
    assert parsed.is_valid()


@pytest.mark.parametrize(
    ("symbol", "root", "year", "month"),
    [
        ("BRN_2027F", "BRN", 2027, "F"),
        ("OIL_WTI_CUSHING_2028Z", "OIL_WTI_CUSHING", 2028, "Z"),
        ("ES1_2029H", "ES1", 2029, "H"),
        ("0aejt_2026z", "0AEJT", 2026, "Z"),
        ("  brn_2027f  ", "BRN", 2027, "F"),
    ],
)
def test_parse_canonical_contract_returns_exact_contract_identity(
    notation, symbol, root, year, month
):
    parsed = notation.parse_canonical_contract(symbol)

    assert parsed is not None
    assert (parsed.root, parsed.year, parsed.month) == (root, year, month)
    assert parsed.kind == "contract"
    assert parsed.to_string() == f"{root}_{year}{month}"


@pytest.mark.parametrize("quarter", range(1, 5))
def test_parse_canonical_contract_accepts_quarters(notation, quarter):
    parsed = notation.parse_canonical_contract(f"CL_2026Q{quarter}")

    assert parsed is not None
    assert parsed.root == "CL"
    assert parsed.year == 2026
    assert parsed.quarter == quarter
    assert parsed.kind == "quarter"
    assert parsed.is_valid()

    alternate = notation.parse_canonical_contract(f"CL_Q{quarter}_2026")
    assert alternate is not None
    assert alternate.to_string() == f"CL_2026Q{quarter}"
    assert alternate.kind == "quarter"


def test_parse_canonical_contract_accepts_canonical_calendar(notation):
    parsed = notation.parse_canonical_contract("OIL_BRENT_CAL2026")

    assert parsed is not None
    assert parsed.root == "OIL_BRENT"
    assert parsed.calendar_year == 2026
    assert parsed.kind == "calendar"
    assert parsed.is_valid()


@pytest.mark.parametrize(
    "symbol",
    [
        "",
        "   ",
        "CL",
        "CL26Z",
        "CLZ26",
        "CL-26Z",
        "CL 26Z",
        "CL.n.1",
        "CL_M01",
        "CME_NymexFutures_EOD:CL_2026Z",
        "OIL_CAL",
        "OIL_CALENDAR",
        "OIL_CAL_SPREAD",
        "OIL_2026",
        "CL_2026",
        "CL_2026A",
        "CL_2026AA",
        "CL_2026Q0",
        "CL_2026Q5",
        "CL_2026Q10",
        "CL_Q0_2026",
        "CL_Q5_2026",
        "CL_CAL",
        "CL_CAL26",
        "CL_CAL20A6",
        "CL_0000Z",
        "CL_0999Z",
        "CL_20Z",
        "CL_20260Z",
        "CL_99999Z",
        "_2026Z",
        "CL__2026Z",
        "CL_2026ZZ",
    ],
)
def test_unrecognized_input_returns_none(notation, symbol):
    assert notation.parse_canonical_contract(symbol) is None


def test_permissive_parse_remains_backward_compatible(notation):
    invalid_month = notation.parse("CL_2026A")
    short_alias = notation.parse("CL26Z")

    assert invalid_month.month == "A"
    assert "Invalid month code: A" in invalid_month.warnings
    assert short_alias.to_string() == "CL_2026Z"


@pytest.mark.parametrize(
    ("symbol", "root", "year", "month"),
    [
        ("BRN26Z", "BRN", 2026, "Z"),
        ("BRNZ26", "BRN", 2026, "Z"),
        ("BRN-26Z", "BRN", 2026, "Z"),
        ("BRN 26Z", "BRN", 2026, "Z"),
        ("BRN-2026Z", "BRN", 2026, "Z"),
        ("BRN 2026Z", "BRN", 2026, "Z"),
        ("0aejt26z", "0AEJT", 2026, "Z"),
        ("OIL_2026_ROOT26Z", "OIL_2026_ROOT", 2026, "Z"),
        ("OIL_2026_ROOTZ26", "OIL_2026_ROOT", 2026, "Z"),
    ],
)
def test_parse_contract_reference_accepts_legacy_monthly_aliases(
    notation, symbol, root, year, month
):
    parsed = notation.parse_contract_reference(symbol)

    assert parsed is not None
    assert (parsed.root, parsed.year, parsed.month) == (root, year, month)
    assert parsed.kind == "contract"
    assert parsed.to_string() == f"{root}_{year}{month}"
    assert parsed.is_valid()


@pytest.mark.parametrize(
    "symbol",
    [
        "CL_2026Z",
        "CL_2026Q1",
        "CL_Q1_2026",
        "CL_CAL2026",
    ],
)
def test_parse_contract_reference_accepts_strict_canonical_forms(notation, symbol):
    assert notation.parse_contract_reference(symbol) == (
        notation.parse_canonical_contract(symbol)
    )


@pytest.mark.parametrize(
    ("symbol", "root", "rule", "index"),
    [
        ("CL.n.1", "CL", "n", 1),
        ("oil_2026_root.V.12", "OIL_2026_ROOT", "v", 12),
        ("0aejt.fn.2", "0AEJT", "fn", 2),
        ("Corn_CBOT.USD.n.1", "CORN_CBOT.USD", "n", 1),
        ("CL_M01", "CL", "n", 1),
        ("Corn_CBOT.USD_M05", "CORN_CBOT.USD", "n", 5),
        ("OIL_2026_ROOT_M12", "OIL_2026_ROOT", "n", 12),
    ],
)
def test_parse_contract_reference_accepts_valid_continuous_aliases(
    notation, symbol, root, rule, index
):
    parsed = notation.parse_contract_reference(symbol)

    assert parsed is not None
    assert parsed.root == root
    assert parsed.is_continuous
    assert parsed.roll_rule == rule
    assert parsed.contract_index == index
    assert parsed.kind == "continuous"
    assert parsed.is_valid()


@pytest.mark.parametrize(
    "symbol",
    [
        "",
        "   ",
        "CL",
        "OIL_CAL",
        "OIL_2026",
        "OIL_0999Z",
        "CL_0999Z",
        "2026Z",
        "CL2026Z",
        "CL0999Z",
        "CL_CAL2026Z",
        "CL_2026Q01",
        "CL_2026A",
        "CL_2026Q0",
        "CL_2026Q5",
        "CL_Q0_2026",
        "CL_Q5_2026",
        "CL_CAL0999",
        "CL_CAL26",
        "CL.x.1",
        "CL.n.0",
        "CL.n.-1",
        "CL.n.one",
        "CL..1",
        "CL.n.1.extra",
        "CL_M00",
        "CL_M1",
        "CL_M001",
        "CME_NymexFutures_EOD:CL_2026Z",
        "CME_NymexFutures_EOD:CL26Z",
        "ICE:CL.n.1",
        "ICE:Corn_CBOT.USD_M05",
        "Corn_CBOT..USD_M05",
        "@CL26Z",
        "BRN-0999Z",
        "BRN 0999Z",
    ],
)
def test_parse_contract_reference_rejects_unrecognized_input(notation, symbol):
    assert notation.parse_contract_reference(symbol) is None


def test_parse_contract_reference_never_uses_partial_parser(notation, monkeypatch):
    def fail_if_called(symbol):
        raise AssertionError(f"partial parser called for {symbol}")

    monkeypatch.setattr(notation, "_partial_parse", fail_if_called)

    assert notation.parse_contract_reference("CL_2026A") is None
    assert notation.parse_contract_reference("CL26Z").to_string() == "CL_2026Z"


@pytest.mark.parametrize("separator", ["-", " "])
def test_parse_contract_reference_validates_separated_four_digit_year(
    notation, separator
):
    lower_boundary = notation.parse_contract_reference(f"BRN{separator}1000Z")
    upper_boundary = notation.parse_contract_reference(f"BRN{separator}9999Z")

    assert lower_boundary is not None
    assert lower_boundary.to_string() == "BRN_1000Z"
    assert upper_boundary is not None
    assert upper_boundary.to_string() == "BRN_9999Z"
    assert notation.parse_contract_reference(f"BRN{separator}0999Z") is None


@pytest.mark.parametrize(
    "symbol",
    [
        "BRN00Z",
        "BRNZ00",
        "BRN-00Z",
        "BRN 00Z",
        "BRN99Z",
        "BRNZ99",
        "BRN-99Z",
        "BRN 99Z",
    ],
)
def test_parse_contract_reference_uses_existing_two_digit_year_normalization(
    notation, symbol
):
    parsed = notation.parse_contract_reference(symbol)
    permissive = notation.parse(symbol)

    assert parsed is not None
    assert parsed.year == permissive.year


class TestDeliveryMonth:
    """``delivery_month`` answers only for a dated contract.

    Every other kind either has no single delivery month (quarter, calendar,
    continuous) or was never recognized as a contract at all, and guessing one
    would let a caller treat the front of a strip as a dated contract.
    """

    @pytest.mark.parametrize("month", MONTH_CODES)
    def test_every_month_code_resolves_to_the_first_of_that_month(
        self, notation, month
    ):
        parsed = notation.parse_canonical_contract(f"CL_2026{month}")

        assert parsed.delivery_month == date(2026, MONTH_CODES[month], 1)

    def test_to_date_matches_the_property(self, notation):
        parsed = notation.parse_canonical_contract("BRN_2026H")

        assert parsed.to_date() == parsed.delivery_month == date(2026, 3, 1)

    def test_a_legacy_alias_contract_also_resolves(self, notation):
        parsed = notation.parse_contract_reference("BRN26Z")

        assert parsed.delivery_month == date(parsed.year, 12, 1)

    @pytest.mark.parametrize(
        "symbol", ["CL_2026Q1", "CL_CAL2026", "CL.n.1", "CL_M01"]
    )
    def test_non_contract_kinds_have_no_delivery_month(self, notation, symbol):
        parsed = notation.parse_contract_reference(symbol)

        assert parsed is not None
        assert parsed.kind != "contract"
        assert parsed.delivery_month is None
        assert parsed.to_date() is None

    def test_a_permissive_parse_without_a_kind_has_no_delivery_month(
        self, notation
    ):
        """``parse`` does not assert contract identity, so neither does this."""
        parsed = notation.parse("CL_2026Z")

        assert parsed.kind is None
        assert parsed.delivery_month is None

    def test_an_invalid_month_on_a_contract_raises(self):
        parsed = ParsedSymbol(root="CL", year=2026, month="A", kind="contract")

        with pytest.raises(InvalidMonthCodeError, match="invalid futures month"):
            parsed.delivery_month

    def test_a_contract_missing_its_month_returns_none(self):
        parsed = ParsedSymbol(root="CL", year=2026, kind="contract")

        assert parsed.delivery_month is None
