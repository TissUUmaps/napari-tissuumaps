"""This modules implements functions that convert the napari file format to Tissuumaps.
The functions are implemented such that the module can be reused in other context by
generating pythonic versions of the data first, then saving them.
"""
import json
from logging import getLogger
import logging
import os
from typing import Any, Dict, List, Optional, Union
from napari.types import FullLayerData
from napari.utils.io import imsave
import numpy as np
from matplotlib.colors import rgb2hex
from matplotlib.pyplot import get_cmap
from napari_tissuumaps.utils.io import (
    is_path_tissuumaps_filename,
    create_folder_if_not_exist,
)

SUPPORTED_FORMATS = ["image", "points", "labels", "shapes"]

logger = getLogger(__name__)


def filter_type(
    layer_data: List[FullLayerData], type_filter: Union[str, List[str]]
) -> List[FullLayerData]:
    """Filters a list of layers provided by Napari by layer type.
    Only the layers that corresponds to `type_filter` are returned.

    Parameters
    ----------
    layer_data : List[FullLayerData]
        The list of layers provided by Napari. Must contain tuples, with the third one
        corresponding to the layer type as a string.
    type_filter : Union[str, List[str]]
        The filter to use a string. It is possible to use multiple filters by providing
        a list of strings.
    Returns
    -------
    List[FullLayerData]
        The list of layers in the same format as the one in `layer_data` where the
        layer types *not* corresponding to `type_filter` are discarded.
    """
    # Making sure `file_type` is a list
    if not isinstance(type_filter, list):
        type_filter = [type_filter]

    return [
        (data, meta, layer_type)
        for (data, meta, layer_type) in layer_data
        if layer_type in type_filter
    ]


def generate_tmap_config(
    filename: str, layer_data: List[FullLayerData]
) -> Dict[str, Any]:
    """Generates a dict containing the tissumaps cfg of the napari layers to be saved.

    Parameters
    ----------
    filename : str
        The filename to use in Tissuumaps.
    layer_data : List[FullLayerData]
        The layers to be saved as provided by the Napari plugin manager. It contains a
        list of layers, which are themselves dictionary containing the data, the meta-
        data and the type of layer.
    Returns
    -------
    Dict[str, Any]
        The Tissuumaps configuration as a dictionary. The aim is to later save a json
        file with a .tmap extension.
    """
    # This function first create nested lists and dictionary to add the the final
    # dictionary in the latter part of the function.

    # Generating the list of markers (points).
    markers = []
    for data, meta, _ in filter_type(layer_data, "points"):
        markers.append(
            {
                "autoLoad": True,
                "comment": meta["name"],
                "expectedCSV": {
                    "X_col": "x",
                    "Y_col": "y",
                    "color": "color",
                    "group": "name",
                    "name": "",
                    "key": "letters",
                },
                "path": f"points/{meta['name']}.csv",
                "title": f"Download markers ({meta['name']})",
            }
        )

    # Generating the list of layers (images and labels)
    layers, layer_opacities, layer_visibilities = [], {}, {}
    idx = 0  # Image index
    # Each image gets a unique `idx` value, as well as each label in each Napari label
    # layer.
    for data, meta, layer_type in filter_type(layer_data, ["image", "labels"]):
        if layer_type == "image":
            layers.append(
                {"name": meta["name"], "tileSource": f"images/{meta['name']}.tif.dzi"}
            )
            layer_opacities[str(idx)] = str(meta["opacity"])
            layer_visibilities[str(idx)] = str(meta["visible"])
            idx += 1
        elif layer_type == "labels":
            # The labels objects can contain multiple labels each in Napari. They are
            # separated as multiple images in Tissuumaps.
            for j, label in enumerate(np.unique(data)):
                if label == 0:
                    continue
                layers.append(
                    {
                        "name": f"{meta['name']} ({label})",
                        "tileSource": f"labels/{meta['name']}_{j:02d}.tif.dzi",
                    }
                )
                layer_opacities[str(idx)] = str(meta["opacity"])
                layer_visibilities[str(idx)] = str(meta["visible"])
                idx += 1

    # The final configuration to be returned, combining all the lists and dictionaries
    # generated above.
    config = {
        "compositeMode": "lighter",
        "filename": filename,
        "layers": layers,
        "layerOpacities": layer_opacities,
        "layerVisibilities": layer_visibilities,
        "markerFiles": markers,
        "regions": {},
        "settings": [
            {
                "function": "_linkMarkersToChannels",
                "module": "overlayUtils",
                "value": True,
            },
            {"function": "_autoLoadCSV", "module": "dataUtils", "value": True},
            {"function": "_markerScale2", "module": "glUtils", "value": 7.5},
        ],
    }
    return config


def tmap_writer(path: str, layer_data: List[FullLayerData]) -> Optional[str]:
    """Creates a Tissuumaps project folder based on a Napari list of layers.

    Parameters
    ----------
    path : str
        The path to save the Tissuumaps project to. Must contain the name of the
        tissumap project file, including the .tmap extension.
    layer_data : List[FullLayerData]
        The list of layers to save as provided by Napari.
    Returns
    -------
    str
        A string containing the path to the Tissuumaps project folder if the save was
        successful, otherwise None.
    """

    # Sanity check to verify the user wants to save a tmap file.
    if not is_path_tissuumaps_filename(path):
        return None

    # The main tissuumaps project folder is created.
    create_folder_if_not_exist(path)

    filename = os.path.basename(path)  # Extracting the filename from path
    filename = filename[: filename.find(".")]  # Removing the extension from the name
    # Creation of the tmap file
    tmap_cfg = generate_tmap_config(filename, layer_data)
    tmap_file = open(f"{path}/main.tmap", "w+")
    tmap_file.write(json.dumps(tmap_cfg, indent=4))
    tmap_file.close()
    # Saving the files
    for data, meta, layer_type in layer_data:
        if layer_type == "image":
            # The Napari images can directly be saved to tif.
            image_folder = create_folder_if_not_exist(path, "images")
            path_image = os.path.join(image_folder, f"{meta['name']}.tif")
            imsave(path_image, data)
        elif layer_type == "points":
            # The Napari points are in a different coordinate system (y,x) that must be
            # converted to Tissuumaps which uses (x,y). The colors of the individual
            # points are extracted from the metadata.
            points_folder = create_folder_if_not_exist(path, "points")
            path_points = os.path.join(points_folder, f"{meta['name']}.csv")
            # Constructing the columns
            y, x = data[:, 0:1], data[:, 1:2]
            color = np.array([[rgb2hex(color)] for color in meta["face_color"]])
            points = np.block([x, y, color])
            # Saving the csv file manually.
            points_file = open(path_points, "w+")
            points_file.write("name,x,y,color\n")
            for _x, _y, _color in points:
                points_file.write(f"{meta['name']},{_x},{_y},{_color}\n")
            points_file.close()
        elif layer_type == "labels":
            # The labels layers may have multiple sub-labels that must be separated in
            # different images for Tissuumaps to read. Each label gets a color given by
            # a colormap from matplotlib, instead of being provided by Napari.
            cmap = get_cmap("tab10")
            labels_folder = create_folder_if_not_exist(path, "labels")
            for i, label in enumerate(np.unique(data)):
                if label == 0:
                    continue
                path_label = os.path.join(labels_folder, f"{meta['name']}_{i:02d}.tif")
                # Currently the colormap cycles when there are more labels than
                # available colors
                color = cmap(i % cmap.N)[:3]
                label_img = np.ones(data.shape + (3,)) * color
                mask = data == label
                label_img[~mask] = 0
                imsave(path_label, (label_img * 255.0).astype(np.uint8))
        elif layer_type == "shapes":
            # TODO: Add support for shapes layers.
            # Tissuumaps needs to have points coordinates that corresponds to the pixel
            # positions but also normalized in the range [0,1]. The next version of
            # Napari will allow that. (Latest version is 0.4.10, released on 17 Jun 21)
            logging.warning("Shape layers are not yet supported.")
        else:
            logging.warning(
                f"Layer \"{meta['name']}\" cannot be saved. This type of layer "
                "({layer_type}) is not yet implemented."
            )
    return path
