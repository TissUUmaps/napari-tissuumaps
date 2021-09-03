"""This module implements useful io functions, mainly for dealing with the file
system.
"""
from pathlib import Path
from typing import Union


def is_path_tissuumaps_filename(path: Union[Path, str]) -> bool:
    """Returns True if the path corresponds to a valid tissuumap path.
    Whenever the user attempts to save, the plugins are checked iteratively until
    one corresponds to the right file format. This function checks if the user is
    trying to export to the tissuumap file format.

    Parameters
    ----------
    path : str
        Path to check
    Returns
    -------
    bool
        True if the path ends with a valid tissuumap file extension.
    """
    extensions = "".join(Path(path).suffixes)
    return extensions.endswith(".tmap")

