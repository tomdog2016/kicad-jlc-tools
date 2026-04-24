"""Tests for the S-expression parser."""

from kicad_jlc_tools.parser import tokenize, parse_schematic
from kicad_jlc_tools.exceptions import ParseError
import pytest


def test_tokenize_simple():
    tokens = tokenize('(kicad_sch (version 20231120))')
    assert tokens == ["(", "kicad_sch", "(", "version", 20231120, ")", ")"]


def test_tokenize_string():
    tokens = tokenize('(property "Reference" "R1")')
    assert tokens == ["(", "property", "Reference", "R1", ")"]


def test_tokenize_escaped_string():
    tokens = tokenize('(value "hello \\"world\\"")')
    assert tokens == ["(", "value", 'hello "world"', ")"]


def test_tokenize_float():
    tokens = tokenize("(at 1.27 2.54 0)")
    assert tokens == ["(", "at", 1.27, 2.54, 0, ")"]


def test_tokenize_unterminated_string():
    with pytest.raises(ParseError, match="Unterminated"):
        tokenize('(value "no end')


def test_parse_schematic_valid():
    text = "(kicad_sch (version 20231120))"
    ast = parse_schematic(text)
    assert ast[0] == "kicad_sch"
    assert ast[1] == ["version", 20231120]


def test_parse_schematic_not_kicad():
    with pytest.raises(ParseError, match="Not a KiCad"):
        parse_schematic("(something_else)")


def test_parse_schematic_extra_tokens():
    with pytest.raises(ParseError, match="Extra tokens"):
        parse_schematic("(kicad_sch) (extra)")


def test_parse_fixture():
    from pathlib import Path
    fixture = Path(__file__).parent / "fixtures" / "sample.kicad_sch"
    text = fixture.read_text(encoding="utf-8")
    ast = parse_schematic(text)
    assert ast[0] == "kicad_sch"
    # Should have version, generator, uuid, paper, lib_symbols, and 3 symbols
    assert len(ast) > 5
