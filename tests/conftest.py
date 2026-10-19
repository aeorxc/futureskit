import os
import pytest
import pandas as pd


@pytest.fixture
def contracts():
    dirname, filename = os.path.split(os.path.abspath(__file__))
    cl = pd.read_csv(
        os.path.join(dirname, "test_cl.csv"),
        index_col=0,
        parse_dates=True,
        date_format="%Y-%m-%d",
    )
    return cl
