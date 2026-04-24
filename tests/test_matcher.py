"""Tests for the ComponentMatcher."""

import pytest
from unittest.mock import MagicMock
from kicad_jlc_tools.matcher import ComponentMatcher
from kicad_jlc_tools.models import Component, MatchResult, MatchStatus


@pytest.fixture
def mock_db():
    db = MagicMock()
    db.is_available = True
    db.search.return_value = [
        MatchResult(lcsc="C12345", manufacturer="YAGEO", part_number="RC0402FR-0710KL", stock="10000")
    ]
    return db


def test_match_one(mock_db):
    matcher = ComponentMatcher(mock_db)
    comp = Component(ref="R1", value="10k", footprint="Resistor_SMD:R_0402_1005Metric")
    result = matcher.match_one(comp)
    assert result is not None
    assert result.lcsc == "C12345"


def test_match_one_no_result(mock_db):
    mock_db.search.return_value = []
    matcher = ComponentMatcher(mock_db)
    comp = Component(ref="C1", value="100nF", footprint="Capacitor_SMD:C_0402_1005Metric")
    result = matcher.match_one(comp)
    assert result is None


def test_match_all(mock_db):
    matcher = ComponentMatcher(mock_db)
    comps = [
        Component(ref="R1", value="10k", footprint="Resistor_SMD:R_0402_1005Metric"),
        Component(ref="R2", value="4.7k", footprint="Resistor_SMD:R_0603_1608Metric"),
    ]
    matches = matcher.match_all(comps)
    assert len(matches) == 2
    assert "R1" in matches
    assert "R2" in matches
    assert comps[0].status == MatchStatus.MATCHED


def test_match_all_skip_matched(mock_db):
    matcher = ComponentMatcher(mock_db)
    comps = [
        Component(ref="R1", value="10k", footprint="R_0402", lcsc="C11111",
                  status=MatchStatus.MANUAL),
        Component(ref="R2", value="4.7k", footprint="R_0603"),
    ]
    matches = matcher.match_all(comps, skip_matched=True)
    assert len(matches) == 1
    assert "R2" in matches


def test_match_all_progress(mock_db):
    progress_calls = []
    matcher = ComponentMatcher(mock_db)
    comps = [Component(ref="R1", value="10k", footprint="R_0402")]

    def on_progress(cur, total, ref):
        progress_calls.append((cur, total, ref))

    matcher.match_all(comps, progress_callback=on_progress)
    assert len(progress_calls) == 1
    assert progress_calls[0] == (1, 1, "R1")


def test_match_all_db_unavailable():
    db = MagicMock()
    db.is_available = False
    matcher = ComponentMatcher(db)
    comp = Component(ref="R1", value="10k", footprint="R_0402")
    result = matcher.match_one(comp)
    assert result is None
