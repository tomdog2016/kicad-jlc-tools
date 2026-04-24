"""Tests for the Schematic class."""

import pytest
from pathlib import Path
from kicad_jlc_tools.schematic import Schematic


@pytest.fixture
def sample_sch():
    fixture = Path(__file__).parent / "fixtures" / "sample.kicad_sch"
    return Schematic(fixture)


@pytest.fixture
def sample_text():
    return (Path(__file__).parent / "fixtures" / "sample.kicad_sch").read_text("utf-8")


def test_load_schematic(sample_sch):
    assert sample_sch.path.exists()


def test_extract_components(sample_sch):
    comps = sample_sch.components
    assert len(comps) == 3
    refs = {c.ref for c in comps}
    assert refs == {"R1", "C1", "R2"}


def test_component_properties(sample_sch):
    r1 = sample_sch.get_component("R1")
    assert r1 is not None
    assert r1.value == "10k"
    assert "R_0402" in r1.footprint
    assert r1.lcsc == "C25744"


def test_component_jlc_property(sample_sch):
    r2 = sample_sch.get_component("R2")
    assert r2 is not None
    assert r2.value == "4.7k"
    assert r2.lcsc == "C25900"  # Read from JLC property


def test_component_no_lcsc(sample_sch):
    c1 = sample_sch.get_component("C1")
    assert c1 is not None
    assert c1.lcsc == ""


def test_set_lcsc(sample_sch, tmp_path):
    sample_sch.set_lcsc("C1", "C12345")
    # The change is staged but not yet saved
    assert "C1" in sample_sch._pending_writes
    assert sample_sch._pending_writes["C1"]["LCSC"] == "C12345"


def test_set_footprint(sample_sch, tmp_path):
    sample_sch.set_footprint("R1", "Resistor_SMD:R_0805_2012Metric")
    assert "R1" in sample_sch._pending_writes
    assert sample_sch._pending_writes["R1"]["Footprint"] == "Resistor_SMD:R_0805_2012Metric"


def test_save_and_reload(sample_sch, tmp_path):
    target = tmp_path / "output.kicad_sch"
    sample_sch.set_lcsc("C1", "C99999")
    sample_sch.save(target, backup=False)

    # Reload and verify
    sch2 = Schematic(target)
    c1 = sch2.get_component("C1")
    assert c1 is not None
    assert c1.lcsc == "C99999"

    # Original R1 should be unchanged
    r1 = sch2.get_component("R1")
    assert r1.lcsc == "C25744"


def test_save_footprint_change(sample_text, tmp_path):
    sch = Schematic.from_text(sample_text)
    sch.set_footprint("R1", "Resistor_SMD:R_0805_2012Metric")
    target = tmp_path / "test.kicad_sch"
    sch.save(target, backup=False)

    sch2 = Schematic(target)
    r1 = sch2.get_component("R1")
    assert r1.footprint == "Resistor_SMD:R_0805_2012Metric"


def test_save_creates_backup(sample_sch, tmp_path):
    target = tmp_path / "test.kicad_sch"
    target.write_text(sample_sch._raw_text, encoding="utf-8")
    sample_sch.set_lcsc("R1", "C00001")
    sample_sch.save(target, backup=True)
    assert (tmp_path / "test.kicad_sch.bak").exists()
    # Backup should have original content
    backup_content = (tmp_path / "test.kicad_sch.bak").read_text("utf-8")
    assert "C00001" not in backup_content


def test_from_text(sample_text):
    sch = Schematic.from_text(sample_text)
    assert len(sch.components) == 3


def test_get_component_not_found(sample_sch):
    assert sample_sch.get_component("X99") is None


def test_set_property_not_found(sample_sch):
    from kicad_jlc_tools.exceptions import ComponentNotFoundError
    with pytest.raises(ComponentNotFoundError):
        sample_sch.set_lcsc("X99", "C00000")


def test_footprint_short(sample_sch):
    r1 = sample_sch.get_component("R1")
    assert r1.footprint_short == "R_0402_1005Metric"
