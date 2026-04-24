class KicadJlcToolsError(Exception):
    """Base exception."""


class ParseError(KicadJlcToolsError):
    """S-expression parse failure."""


class SchematicError(KicadJlcToolsError):
    """Schematic read/write error."""


class DatabaseNotFoundError(KicadJlcToolsError):
    """FTS5 database not found."""


class DatabaseDownloadError(KicadJlcToolsError):
    """Download failure."""


class ComponentNotFoundError(KicadJlcToolsError):
    """Reference designator not found in schematic."""
