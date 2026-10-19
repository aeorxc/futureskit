"""
Tests for Refinitiv/LSEG RIC contract notation.

The contract-year width is a per-venue convention rather than a global one, and
getting it wrong fails quietly: the RIC is well-formed, the vendor simply has no
instrument by that name, so the symptom looks like a missing entitlement. These
tests pin both conventions and the refusal to guess a third.
"""

import pytest

from futureskit.vendors.lseg import (
    CME_GROUP_EXCHANGES,
    ONE_DIGIT_YEAR_EXCHANGES,
    contract_code_from_ric,
    format_ric_contract,
    ric_year_digits,
)
from futureskit.exceptions import InvalidMonthCodeError


class TestRicYearDigits:
    @pytest.mark.parametrize("exchange", sorted(CME_GROUP_EXCHANGES))
    def test_cme_group_venues_are_two_digit(self, exchange):
        assert ric_year_digits(exchange) == 2

    @pytest.mark.parametrize("exchange", sorted(ONE_DIGIT_YEAR_EXCHANGES))
    def test_ice_is_one_digit(self, exchange):
        assert ric_year_digits(exchange) == 1

    @pytest.mark.parametrize("exchange", ["nymex", "  NyMeX ", "ice", " ICE "])
    def test_matching_ignores_case_and_whitespace(self, exchange):
        assert ric_year_digits(exchange) in (1, 2)

    @pytest.mark.parametrize("exchange", ["DME", "SGX", "SHFE", "", None])
    def test_unregistered_venues_refuse_to_guess(self, exchange):
        with pytest.raises(ValueError, match="No RIC contract-year convention"):
            ric_year_digits(exchange)


class TestFormatRicContract:
    def test_cme_group_carries_a_two_digit_year(self):
        assert format_ric_contract("CL", "V", 2026, "NYMEX") == "CLV26"
        assert format_ric_contract("RB", "H", 2027, "NYMEX") == "RBH27"

    def test_ice_carries_a_one_digit_year(self):
        assert format_ric_contract("LCO", "V", 2026, "ICE") == "LCOV6"
        assert format_ric_contract("LGO", "Z", 2027, "ICE") == "LGOZ7"

    def test_the_same_contract_differs_only_by_venue(self):
        """The whole point: identical month and year, different width."""
        assert format_ric_contract("CL", "V", 2026, "NYMEX") == "CLV26"
        assert format_ric_contract("LCO", "V", 2026, "ICE") == "LCOV6"

    def test_delayed_adds_the_slash_prefix(self):
        assert format_ric_contract("CL", "V", 2026, "NYMEX", delayed=True) == "/CLV26"
        assert format_ric_contract("LCO", "V", 2026, "ICE", delayed=True) == "/LCOV6"

    def test_real_time_is_the_default(self):
        assert not format_ric_contract("CL", "V", 2026, "NYMEX").startswith("/")

    def test_month_code_is_normalised(self):
        assert format_ric_contract("CL", "v", 2026, "NYMEX") == "CLV26"
        assert format_ric_contract("CL", " V ", 2026, "NYMEX") == "CLV26"

    @pytest.mark.parametrize("month", ["A", "I", "", "VV", None])
    def test_non_futures_month_codes_are_rejected(self, month):
        with pytest.raises(InvalidMonthCodeError):
            format_ric_contract("CL", month, 2026, "NYMEX")

    @pytest.mark.parametrize("root", ["", "   ", None])
    def test_empty_root_is_rejected(self, root):
        with pytest.raises(ValueError, match="RIC root must not be empty"):
            format_ric_contract(root, "V", 2026, "NYMEX")

    @pytest.mark.parametrize("year", [26, 6, 999, 10000])
    def test_year_must_be_four_digits(self, year):
        """A two-digit year here would silently truncate to the wrong contract."""
        with pytest.raises(ValueError, match="four digits"):
            format_ric_contract("CL", "V", year, "NYMEX")

    def test_unregistered_venue_propagates(self):
        with pytest.raises(ValueError, match="No RIC contract-year convention"):
            format_ric_contract("OQD", "V", 2026, "DME")

    def test_decade_rollover_keeps_the_trailing_digits(self):
        assert format_ric_contract("CL", "F", 2030, "NYMEX") == "CLF30"
        assert format_ric_contract("LCO", "F", 2030, "ICE") == "LCOF0"


class TestContractCodeFromRic:
    @pytest.mark.parametrize(
        "ric,expected",
        [
            ("/CLV26", "V26"),
            ("CLV26", "V26"),
            ("/LCOV6", "V6"),
            ("LCOV6", "V6"),
            ("/LGOZ7", "Z7"),
        ],
    )
    def test_the_venue_convention_is_preserved(self, ric, expected):
        assert contract_code_from_ric(ric) == expected

    @pytest.mark.parametrize("ric", ["/CL", "LCO", "", None, "/NOT-A-CONTRACT"])
    def test_non_contract_rics_are_rejected(self, ric):
        with pytest.raises(ValueError, match="does not end in a valid"):
            contract_code_from_ric(ric)

    @pytest.mark.parametrize(
        "root,month,year,exchange",
        [
            ("CL", "V", 2026, "NYMEX"),
            ("LCO", "V", 2026, "ICE"),
            ("GC", "Z", 2029, "COMEX"),
            ("LGO", "F", 2030, "ICE"),
        ],
    )
    def test_round_trips_with_the_formatter(self, root, month, year, exchange):
        ric = format_ric_contract(root, month, year, exchange, delayed=True)
        code = contract_code_from_ric(ric)
        assert code.startswith(month)
        assert ric.endswith(code)
