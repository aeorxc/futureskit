import pytest
from futureskit.notation import FuturesNotation

def test_parse_m_continuous():
    fn = FuturesNotation()
    p = fn.parse('BRN_M01')
    assert p.is_continuous is True
    assert p.root == 'BRN'
    assert p.contract_index == 1
    assert p.roll_rule == 'n'
    assert p.to_string() == 'BRN.n.1'

def test_parse_quarter_both_forms():
    fn = FuturesNotation()
    p1 = fn.parse('BRN_2026Q1')
    assert p1.kind == 'quarter'
    assert p1.root == 'BRN'
    assert p1.year == 2026
    assert p1.quarter == 1
    assert p1.is_valid() is True
    assert p1.to_string() == 'BRN_2026Q1'

    p2 = fn.parse('BRN_Q3_2026')
    assert p2.kind == 'quarter'
    assert p2.root == 'BRN'
    assert p2.year == 2026
    assert p2.quarter == 3
    assert p2.is_valid() is True

def test_parse_calendar():
    fn = FuturesNotation()
    p = fn.parse('BRN_CAL2026')
    assert p.kind == 'calendar'
    assert p.root == 'BRN'
    assert p.calendar_year == 2026
    assert p.is_valid() is True
    assert p.to_string() == 'BRN_CAL2026'
