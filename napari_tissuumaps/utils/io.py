import os
from typing import Optional


def is_path_tissuumaps_filename(path: str) -> bool:
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
    return path.endswith(".tmap")


def create_folder_if_not_exist(path: str, subfolder: Optional[str] = None) -> str:
    if subfolder:
        full_path = os.path.join(path, subfolder)
    else:
        full_path = path

    if not os.path.exists(full_path):
        os.mkdir(full_path)
    return full_path
