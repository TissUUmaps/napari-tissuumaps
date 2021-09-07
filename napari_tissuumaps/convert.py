"""This modules implements functions that convert the napari file format to Tissuumaps.
The functions are implemented such that the module can be reused in other context by
generating pythonic versions of the data first, then saving them.
"""
import json
from logging import getLogger
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
from napari.types import FullLayerData
from napari.utils.io import imsave
from napari.viewer import current_viewer
import numpy as np
from napari_tissuumaps.utils.io import is_path_tissuumaps_filename


SUPPORTED_FORMATS = ["image", "points", "labels", "shapes"]
TMAP_COLORS = [
    [100, 0, 0],  # Red
    [0, 100, 0],  # Green
    [0, 0, 100],  # Blue
    [100, 100, 0],  # Yellow
    [0, 100, 100],  # Cyan
    [100, 0, 100],  # Magenta
    [100, 100, 100],  # Gray
]

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
    filename: str, layer_data: List[FullLayerData], internal_shapes: bool = False
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
    internal_shapes : bool
        Determines if the shapes layer are saved in the tmap file (True) or if the tmap
        file references an external json file (False).
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
    layers, layer_filters, layer_opacities, layer_visibilities = [], {}, {}, {}
    default_filters = [
        {"name": "Brightness", "value": "0"},
        {"name": "Contrast", "value": "1"},
    ]
    regions = {}
    idx = 0  # Image index
    # We need to keep track of how many colors have been used for the labels, which
    # is different from `idx`. Using `idx` would make the app skip colors everytime
    # there is an image.
    used_colors = 0
    # Each image gets a unique `idx` value, as well as each label in each Napari label
    # layer.
    for data, meta, layer_type in layer_data:
        if layer_type == "image":
            layers.append(
                {"name": meta["name"], "tileSource": f"images/{meta['name']}.tif.dzi"}
            )
            layer_filters[str(idx)] = default_filters.copy()
            layer_filters[str(idx)].append({"name": "Color", "value": "0"})
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
                color = ",".join(map(str, TMAP_COLORS[used_colors % len(TMAP_COLORS)]))
                layer_filters[str(idx)] = default_filters.copy()
                layer_filters[str(idx)].append({"name": "Color", "value": color})
                layer_opacities[str(idx)] = str(meta["opacity"])
                layer_visibilities[str(idx)] = str(meta["visible"])
                idx += 1
                used_colors += 1
        elif layer_type == "shapes":
            regions.update(generate_shapes_dict(data, meta))

    # The final configuration to be returned, combining all the lists and dictionaries
    # generated above.
    config = {
        "compositeMode": "lighter",
        "filename": filename,
        "layers": layers,
        "filters": ["Brightness", "Contrast", "Color"],
        "layerFilters": layer_filters,
        "layerOpacities": layer_opacities,
        "layerVisibilities": layer_visibilities,
        "markerFiles": markers,
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
    if internal_shapes:
        config["regions"] = regions
    else:
        config["regionFile"] = "regions/regions.json"

    return config


def generate_shapes_dict(data: FullLayerData, meta: Dict[str, Any]) -> Dict[str, Any]:
    """Generates a dictionary containing the info to plot shapes in Tissuumaps.
    The dict can later on be exported as a json file or added to the .tmap project
    file.

    Parameters
    ----------
    data : FullLayerData
        The Shapes layer data (A list of shapes, which are lists of points) as provided
        by Napari.
    meta : Dict[str, Any]
        The metadata of the shapes layer containing the name and colors of the shapes.

    Returns
    -------
    Dict[str, Any]
        A dictionary containing the information to draw the shapes in Tissuumaps.
    """
    shape_dict = {}
    for i, shape in enumerate(data):
        shape_name = meta["name"] + f"_{i+1}"
        # We enumerate each shapes that appear in the layer
        subshape_dict = {}
        subshape_dict["id"] = shape_name
        # Points with pixel positions
        points_array = []
        _xmin, _xmax, _ymin, _ymax = np.inf, -np.inf, np.inf, -np.inf
        dimensions = current_viewer().dims.range
        width, height = dimensions[0][1], dimensions[1][1]
        for _points in shape:
            assert isinstance(_points, np.ndarray)
            points = [_points[1] / height, _points[0] / width]
            points_array.append({"x": points[0], "y": points[1]})
            _xmin = _xmin if points[0] > _xmin else points[0]
            _xmax = _xmax if points[0] < _xmax else points[0]
            _ymin = _ymin if points[1] > _ymin else points[1]
            _ymax = _ymax if points[1] < _ymax else points[1]
        subshape_dict["points"] = [[points_array]]
        # Points with normalized positions (in [0,1])
        global_points_array = []
        _gxmin, _gxmax, _gymin, _gymax = np.inf, -np.inf, np.inf, -np.inf
        for _points in shape:
            assert isinstance(_points, np.ndarray)
            points = [_points[1], _points[0]]
            global_points_array.append({"x": points[0], "y": points[1]})
            _gxmin = _gxmin if points[0] > _gxmin else points[0]
            _gxmax = _gxmax if points[0] < _gxmax else points[0]
            _gymin = _gymin if points[1] > _gymin else points[1]
            _gymax = _gymax if points[1] < _gymax else points[1]
        subshape_dict["globalPoints"] = [[global_points_array]]
        shape_color = rgb2hex(meta["face_color"][i])
        shape_settings = {
            "regionName": shape_name,
            "regionClass": None,
            "barcodeHistogram": [],
            "len": 1,
            "_xmin": _xmin,
            "_xmax": _xmax,
            "_ymin": _ymin,
            "_ymax": _ymax,
            "_gxmin": _gxmin,
            "_gxmax": _gxmax,
            "_gymin": _gymin,
            "_gymax": _gymax,
            "polycolor": shape_color,
            "associatedPoints": [],
            "filled": True,
        }
        subshape_dict.update(shape_settings)
        # We add it to the full dict
        shape_dict[shape_name] = subshape_dict
    return shape_dict


def rgb2hex(color_vec: np.ndarray) -> str:
    """Transforms an array of floats into a hex color string (#xxxxxx).

    Parameters
    ----------
    color_vec : np.ndarray
        A numpy array of three rgb components.
    Returns
    -------
    str
        The color as a string in hex format.
    """
    return "#" + "".join([f"{int(c*255):02X}" for c in color_vec[:3]])


def tmap_writer(
    save_path: Union[Path, str], layer_data: List[FullLayerData]
) -> Optional[str]:
    """Creates a Tissuumaps project folder based on a Napari list of layers.

    Parameters
    ----------
    save_path : Union[Path, str]
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
    if not is_path_tissuumaps_filename(save_path):
        return None

    # The main tissuumaps project folder is created.
    save_path = Path(save_path)
    save_path.mkdir(parents=True, exist_ok=True)

    # Creation of the tmap file
    tmap_cfg = generate_tmap_config(save_path.stem, layer_data)
    tmap_file = open(save_path / "main.tmap", "w+")
    tmap_file.write(json.dumps(tmap_cfg, indent=4))
    tmap_file.close()

    # Shapes have to be combined in the same file
    regions = {}
    # Saving the files
    for data, meta, layer_type in layer_data:
        if layer_type == "image":
            # The Napari images can directly be saved to tif.
            image_folder = save_path / "images"
            image_folder.mkdir(exist_ok=True)
            path_image = image_folder / f"{meta['name']}.tif"
            imsave(str(path_image), data)
        elif layer_type == "points":
            # The Napari points are in a different coordinate system (y,x) that must be
            # converted to Tissuumaps which uses (x,y). The colors of the individual
            # points are extracted from the metadata.
            points_folder = save_path / "points"
            points_folder.mkdir(exist_ok=True)
            path_points = points_folder / f"{meta['name']}.csv"
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
            labels_folder = save_path / "labels"
            labels_folder.mkdir(exist_ok=True)
            for i, label in enumerate(np.unique(data)):
                if label == 0:
                    continue
                path_label = labels_folder / f"{meta['name']}_{i:02d}.tif"
                # Currently the colormap cycles when there are more labels than
                # available colors
                label_img = np.ones(data.shape + (3,))
                mask = data == label
                label_img[~mask] = 0
                label_img_uint8 = (label_img * 255.0).astype(np.uint8)
                imsave(str(path_label), label_img_uint8)
        elif layer_type == "shapes":
            regions.update(generate_shapes_dict(data, meta))
        else:
            logging.warning(
                f"Layer \"{meta['name']}\" cannot be saved. This type of layer "
                "({layer_type}) is not yet implemented."
            )

    # Saving the shapes
    if len(regions) > 0:
        shapes_folder = save_path / "regions"
        shapes_folder.mkdir(exist_ok=True)
        # Saving the json
        shapes_filename = "regions.json"
        shapes_file = open(shapes_folder / shapes_filename, "w+")
        shapes_file.write(json.dumps(regions, indent=4))
        shapes_file.close()

    return str(save_path)
