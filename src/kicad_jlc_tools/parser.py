"""S-expression tokenizer and recursive-descent parser for KiCad .kicad_sch files."""

from __future__ import annotations

from .exceptions import ParseError


def _convert_atom(token: str) -> object:
    try:
        if any(ch in token for ch in ".eE"):
            return float(token)
        return int(token)
    except ValueError:
        return token


def tokenize(text: str) -> list:
    """Tokenize a KiCad S-expression string into a flat list of atoms and parens."""
    tokens: list = []
    i, length = 0, len(text)
    while i < length:
        ch = text[i]
        if ch in " \t\r\n":
            i += 1
            continue
        if ch in "()":
            tokens.append(ch)
            i += 1
            continue
        if ch == '"':
            i += 1
            buf: list[str] = []
            escaped = False
            while i < length:
                c = text[i]
                if escaped:
                    buf.append(c)
                    escaped = False
                elif c == "\\":
                    escaped = True
                elif c == '"':
                    break
                else:
                    buf.append(c)
                i += 1
            else:
                raise ParseError("Unterminated string in schematic.")
            tokens.append("".join(buf))
            i += 1
            continue
        j = i
        while j < length and text[j] not in "() \t\r\n":
            j += 1
        tokens.append(_convert_atom(text[i:j]))
        i = j
    return tokens


def _parse_expression(tokens: list, start: int = 0) -> tuple:
    if start >= len(tokens):
        raise ParseError("Unexpected end of tokens.")
    token = tokens[start]
    if token == "(":
        items: list = []
        idx = start + 1
        while idx < len(tokens) and tokens[idx] != ")":
            node, idx = _parse_expression(tokens, idx)
            items.append(node)
        if idx >= len(tokens):
            raise ParseError("Missing closing parenthesis.")
        return items, idx + 1
    if token == ")":
        raise ParseError("Unexpected ')'.")
    return token, start + 1


def parse_schematic(text: str) -> list:
    """Parse a KiCad .kicad_sch file into a nested-list AST.

    Returns the root AST node (a list whose first element is "kicad_sch").
    Raises ParseError if the text is not a valid KiCad schematic.
    """
    tokens = tokenize(text)
    expr, idx = _parse_expression(tokens, 0)
    if idx != len(tokens):
        raise ParseError("Extra tokens after parse.")
    if not isinstance(expr, list) or not expr or expr[0] != "kicad_sch":
        raise ParseError("Not a KiCad schematic file.")
    return expr
