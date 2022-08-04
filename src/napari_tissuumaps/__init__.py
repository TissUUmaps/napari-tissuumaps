try:
    from ._version import version as __version__
except ImportError:
    __version__ = "unknown"
from ._writer import write_layers
from .convert import tmap_writer

__all__ = ("write_layers", "tmap_writer")
