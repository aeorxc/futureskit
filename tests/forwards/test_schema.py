import pandas as pd
import pytest

from futureskit.forwards import validate_contract_matrix, validate_expiry_dates


@pytest.fixture
def forward_frame():
    return pd.DataFrame(
        {
            "Z prompt assessment": [70.0, 71.0],
            "A quarterly swap": [71.0, 72.0],
        },
        index=pd.to_datetime(["2025-12-01", "2025-12-02"]),
    )


def test_validate_contract_matrix_accepts_opaque_columns_in_caller_order(forward_frame):
    assert validate_contract_matrix(forward_frame) is None
    assert validate_contract_matrix(forward_frame, strict=False) == []


@pytest.mark.parametrize(
    ("matrix", "violation"),
    [
        (
            pd.DataFrame(
                [[70.0, 71.0]],
                index=pd.to_datetime(["2025-12-01"]),
                columns=["prompt", "prompt"],
            ),
            "columns must be unique",
        ),
        (
            pd.DataFrame({"prompt": [70.0]}, index=["2025-12-01"]),
            "index must be a pandas DatetimeIndex",
        ),
        (
            pd.DataFrame(
                {"prompt": [70.0, 71.0]},
                index=pd.to_datetime(["2025-12-02", "2025-12-01"]),
            ),
            "index must be sorted",
        ),
        (
            pd.DataFrame(
                {"prompt": [70.0, 71.0]},
                index=pd.to_datetime(["2025-12-01", "2025-12-01"]),
            ),
            "index must be unique",
        ),
        (
            pd.DataFrame(
                {"prompt": [70.0]},
                index=pd.DatetimeIndex(["2025-12-01"], tz="UTC"),
            ),
            "index must be timezone-naive",
        ),
        (
            pd.DataFrame(
                {"prompt": ["not a price"]},
                index=pd.to_datetime(["2025-12-01"]),
            ),
            "values must be numeric",
        ),
    ],
)
def test_validate_contract_matrix_raises_for_each_violation(matrix, violation):
    with pytest.raises(ValueError, match=violation):
        validate_contract_matrix(matrix)


def test_validate_contract_matrix_non_strict_lists_every_violation():
    matrix = pd.DataFrame(
        [["not a price", "still not a price"]],
        index=["2025-12-01"],
        columns=["BRN_2026G", "BRN_2026F"],
    )

    assert validate_contract_matrix(matrix, strict=False) == [
        "index must be a pandas DatetimeIndex",
        "values must be numeric",
    ]


@pytest.mark.parametrize(
    ("expiry_dates", "violation"),
    [
        (
            {"prompt assessment": "2025-12-20"},
            "values must be Timestamp-like",
        ),
        (
            {
                "prompt assessment": pd.Timestamp("2025-12-20", tz="UTC"),
            },
            "values must be timezone-naive",
        ),
    ],
)
def test_validate_expiry_dates_rejects_invalid_entries(expiry_dates, violation):
    with pytest.raises(ValueError, match=violation):
        validate_expiry_dates(expiry_dates)


def test_validate_expiry_dates_lists_missing_exact_column_identities(forward_frame):
    expiry_dates = {
        "Z prompt assessment": pd.Timestamp("2025-12-20"),
    }

    assert validate_expiry_dates(expiry_dates, forward_frame) == ["A quarterly swap"]


def test_validate_expiry_dates_accepts_complete_map_and_none(forward_frame):
    expiry_dates = {
        identity: pd.Timestamp("2025-12-20")
        for identity in forward_frame.columns
    }

    assert validate_expiry_dates(expiry_dates, forward_frame) == []
    assert validate_expiry_dates(None, forward_frame) == []
