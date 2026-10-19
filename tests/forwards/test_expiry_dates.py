"""Tests for the public expiry-schedule primitives.

Inference and curation are not alternatives in practice: a desk has curated
expiries for the contracts it cares about and nothing for the tail. These
primitives make that union a first-class operation, so consumers stop
reimplementing it — badly, and usually by dropping the uncurated columns.
"""

import numpy as np
import pandas as pd
import pytest

from futureskit.forwards import (
    BEYOND_SAMPLE,
    infer_expiry_dates,
    merge_expiry_dates,
)


@pytest.fixture
def contracts():
    """Three deliveries: two observed, one never quoted."""
    index = pd.to_datetime(["2026-01-05", "2026-01-06", "2026-01-07"])
    return pd.DataFrame(
        {
            "CL_2026F": [10.0, 11.0, np.nan],
            "CL_2026G": [20.0, 21.0, 22.0],
            "CL_2026H": [np.nan, np.nan, np.nan],
        },
        index=index,
    )


def test_infer_expiry_dates_uses_a_gap_before_the_sample_end(contracts):
    """Only a column that fell silent early is observed to have expired."""
    assert infer_expiry_dates(contracts)["CL_2026F"] == pd.Timestamp("2026-01-06")


def test_infer_expiry_dates_gives_a_column_quoted_to_the_end_beyond_sample(
    contracts,
):
    """Still quoted on the last printing day is alive, not expiring here.

    Reading the sample end as an expiry is the windowed-inference hazard: on an
    eight-day window every live contract would be handed a roll on the final
    row.
    """
    assert infer_expiry_dates(contracts)["CL_2026G"] == BEYOND_SAMPLE


def test_infer_expiry_dates_gives_a_never_observed_column_nat(contracts):
    assert pd.isna(infer_expiry_dates(contracts)["CL_2026H"])


def test_infer_expiry_dates_ignores_a_trailing_blank_row(contracts):
    """A row on which nothing printed does not end the sample."""
    blanked = contracts.reindex(contracts.index.append(pd.to_datetime(["2026-01-08"])))

    assert infer_expiry_dates(blanked)["CL_2026G"] == BEYOND_SAMPLE
    assert infer_expiry_dates(blanked)["CL_2026F"] == pd.Timestamp("2026-01-06")


def test_merge_expiry_dates_prefers_the_curated_value(contracts):
    merged = merge_expiry_dates(contracts, {"CL_2026F": pd.Timestamp("2025-12-31")})

    assert merged["CL_2026F"] == pd.Timestamp("2025-12-31")


def test_merge_expiry_dates_fills_uncurated_columns_from_inference(contracts):
    merged = merge_expiry_dates(contracts, {"CL_2026G": pd.Timestamp("2026-02-20")})

    assert merged["CL_2026F"] == pd.Timestamp("2026-01-06")
    assert merged["CL_2026G"] == pd.Timestamp("2026-02-20")


def test_merge_expiry_dates_covers_every_frame_column(contracts):
    merged = merge_expiry_dates(contracts, {"CL_2026F": "2025-12-31"})

    assert list(merged) == list(contracts.columns)


def test_merge_expiry_dates_surfaces_nat_rather_than_dropping_the_column(
    contracts,
):
    """An all-NaN, uncurated column keeps its slot as NaT.

    Omitting it would shift every later delivery into an earlier tenor, which
    is the failure mode the deduplicating legacy helper still has.
    """
    merged = merge_expiry_dates(contracts, {"CL_2026F": "2025-12-31"})

    assert "CL_2026H" in merged
    assert pd.isna(merged["CL_2026H"])


def test_merge_expiry_dates_curates_an_otherwise_never_live_column(contracts):
    """Curation is the caller asserting the instrument exists."""
    merged = merge_expiry_dates(contracts, {"CL_2026H": "2026-03-31"})

    assert merged["CL_2026H"] == pd.Timestamp("2026-03-31")


@pytest.mark.parametrize("curated", [None, {}])
def test_merge_expiry_dates_with_no_curation_is_pure_inference(contracts, curated):
    assert merge_expiry_dates(contracts, curated) == infer_expiry_dates(contracts)


def test_merge_expiry_dates_ignores_curated_keys_that_name_no_column(contracts):
    """The result stays usable as an ``expiry_dates`` argument.

    ``resolve_expiry_dates`` requires an exact column match, so a curated map
    covering a wider board must not widen the merged schedule.
    """
    merged = merge_expiry_dates(
        contracts, {"CL_2026F": "2025-12-31", "CL_2026Z": "2026-11-30"}
    )

    assert "CL_2026Z" not in merged


def test_merge_expiry_dates_coerces_curated_values_to_timestamps(contracts):
    merged = merge_expiry_dates(contracts, {"CL_2026F": "2025-12-31"})

    assert isinstance(merged["CL_2026F"], pd.Timestamp)
