"""
This module is an example of a barebones writer plugin for napari

It implements the ``napari_get_writer`` and ``napari_write_image`` hook specifications.
see: https://napari.org/docs/dev/plugins/hook_specifications.html

Replace code below according to your needs
"""
from logging import getLogger
from typing import Any, Callable, List, Optional
from napari_plugin_engine import napari_hook_implementation
from napari.types import FullLayerData
from napari_tissuumaps.convert import tmap_writer, SUPPORTED_FORMATS
from napari_tissuumaps.utils.io import is_path_tissuumaps_filename

logger = getLogger(__name__)

# The WriterFunction is redefined from the original one in napari.types to change the
# return type from List[str] to Optional[str].
_WriterFunction = Callable[[str, List[FullLayerData]], Optional[str]]


@napari_hook_implementation
def napari_get_writer(path: str, layer_types: List[str]) -> Optional[_WriterFunction]:
    """Return function capable of writing napari layer data to ``path``.
    This function will be called whenever the user attempts to save multiple
    layers (e.g. via ``File -> Save Layers``, or
    :func:`~napari.plugins.io.save_layers`).
    This function must execute **quickly**, and should return ``None`` if
    ``path`` has an unrecognized extension for the reader plugin or the list of
    layer types are incompatible with what the plugin can write. If ``path`` is
    a recognized format, this function should return a *function* that accepts
    the same ``path``, and a list of tuples containing the data for each layer
    being saved in the form of ``(Layer.data, Layer._get_state(),
    Layer._type_string)``. The writer function should return a list of strings
    (the actual filepath(s) that were written).
    .. important::
        It is up to plugins to inspect and obey any extension in ``path``
        (and return ``None`` if it is an unsupported extension).
    An example function signature for a ``WriterFunction`` that might be
    returned by this hook specification is as follows:
    .. code-block:: python
        def writer_function(
            path: str, layer_data: List[Tuple[Any, Dict, str]]
        ) -> List[str]:
            ...
    Parameters
    ----------
    path : str
        Path to file, directory, or resource (like a URL).  Any extensions in
        the path should be examined and obeyed.  (i.e. if the plugin is
        incapable of returning a requested extension, it should return
        ``None``).
    layer_types : list of str
        List of layer types (e.g. "image", "labels") that will be provided to
        the writer function.
    Returns
    -------
    Callable or None
        A function that accepts the path, a list of layer_data (where
        layer_data is ``(data, meta, layer_type)``). If unable to write to the
        path or write the layer_data, must return ``None`` (not ``False``).
    """
    if not is_path_tissuumaps_filename(path):
        return None

    for layer_type in layer_types:
        if layer_type not in SUPPORTED_FORMATS:
            logger.warn(
                f"One of the layers's format ({layer_type}) is not supported when "
                "exporting to Tissuumaps. Skipped!"
            )

    return tmap_writer


@napari_hook_implementation
def napari_write_image(path: str, data: Any, meta: dict) -> Optional[str]:
    """Write image data and metadata into a path.
    It is the responsibility of the implementation to check any extension on
    ``path`` and return ``None`` if it is an unsupported extension.  If
    ``path`` has no extension, implementations may append their preferred
    extension.
    Parameters
    ----------
    path : str
        Path to file, directory, or resource (like a URL).
    data : array or list of array
        Image data. Can be N dimensional. If meta['rgb'] is ``True`` then the
        data should be interpreted as RGB or RGBA. If meta['multiscale'] is
        True, then the data should be interpreted as a multiscale image.
    meta : dict
        Image metadata.
    Returns
    -------
    path : str or None
        If data is successfully written, return the ``path`` that was written.
        Otherwise, if nothing was done, return ``None``.
    """
    return tmap_writer(path, [(data, meta, "image")])


@napari_hook_implementation
def napari_write_labels(path: str, data: Any, meta: dict) -> Optional[str]:
    """Write labels data and metadata into a path.
    It is the responsibility of the implementation to check any extension on
    ``path`` and return ``None`` if it is an unsupported extension.  If
    ``path`` has no extension, implementations may append their preferred
    extension.
    Parameters
    ----------
    path : str
        Path to file, directory, or resource (like a URL).
    data : array or list of array
        Integer valued label data. Can be N dimensional. Every pixel contains
        an integer ID corresponding to the region it belongs to. The label 0 is
        rendered as transparent. If a list and arrays are decreasing in shape
        then the data is from a multiscale image.
    meta : dict
        Labels metadata.
    Returns
    -------
    path : str or None
        If data is successfully written, return the ``path`` that was written.
        Otherwise, if nothing was done, return ``None``.
    """
    return tmap_writer(path, [(data, meta, "labels")])


@napari_hook_implementation
def napari_write_points(path: str, data: Any, meta: dict) -> Optional[str]:
    """Write points data and metadata into a path.
    It is the responsibility of the implementation to check any extension on
    ``path`` and return ``None`` if it is an unsupported extension.  If
    ``path`` has no extension, implementations may append their preferred
    extension.
    Parameters
    ----------
    path : str
        Path to file, directory, or resource (like a URL).
    data : array (N, D)
        Coordinates for N points in D dimensions.
    meta : dict
        Points metadata.
    Returns
    -------
    path : str or None
        If data is successfully written, return the ``path`` that was written.
        Otherwise, if nothing was done, return ``None``.
    """
    return tmap_writer(path, [(data, meta, "points")])


@napari_hook_implementation
def napari_write_shapes(path: str, data: Any, meta: dict) -> Optional[str]:
    """Write shapes data and metadata into a path.
    It is the responsibility of the implementation to check any extension on
    ``path`` and return ``None`` if it is an unsupported extension.  If
    ``path`` has no extension, implementations may append their preferred
    extension.
    Parameters
    ----------
    path : str
        Path to file, directory, or resource (like a URL).
    data : list
        List of shape data, where each element is an (N, D) array of the
        N vertices of a shape in D dimensions.
    meta : dict
        Shapes metadata.
    Returns
    -------
    path : str or None
        If data is successfully written, return the ``path`` that was written.
        Otherwise, if nothing was done, return ``None``.
    """
    # Not yet supported
    # TODO: When adding support, replace with:
    # return tmap_writer(path, [(data, meta, "shapes")])
    return None
