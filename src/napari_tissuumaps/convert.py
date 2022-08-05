"""This module implements an exporter from the Napari layers to TissUUmaps.
The functions are implemented such that the module can be reused in other
context by generating pythonic versions of the data first, then saving them.
"""
import json
from logging import getLogger
from pathlib import Path
from typing import Any, Dict, List, Union

import numpy as np
from napari.layers.labels.labels import Labels
from napari.types import FullLayerData
from napari.utils.io import imsave

logger = getLogger(__name__)


def filter_type(
    layer_data: List[FullLayerData], type_filter: Union[str, List[str]]
) -> List[FullLayerData]:
    """Filters a list of layers provided by Napari by layer type.
    Only the layers that corresponds to `type_filter` are returned.

    Parameters
    ----------
    layer_data : List[FullLayerData]
        The list of layers provided by Napari. Must contain tuples, with the
        third one corresponding to the layer type as a string.
    type_filter : Union[str, List[str]]
        The filter to use a string. It is possible to use multiple filters by
        providing a list of strings.
    Returns
    -------
    List[FullLayerData]
        The list of layers in the same format as the one in `layer_data` where
        the layer types *not* corresponding to `type_filter` are discarded.
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
    filename: str,
    layer_data: List[FullLayerData],
    internal_shapes: bool = False,
) -> Dict[str, Any]:
    """Generates the tissumaps config of the napari layers to be saved.

    Parameters
    ----------
    filename : str
        The filename to use in Tissuumaps.
    layer_data : List[FullLayerData]
        The layers to be saved as provided by the Napari plugin manager. It
        contains a list of layers, which are themselves dictionary containing
        the data, the metadata and the type of layer.
    internal_shapes : bool
        Determines if the shapes layer are saved in the tmap file (True) or if
        the tmap file references an external json file (False).
    Returns
    -------
    Dict[str, Any]
        The Tissuumaps configuration as a dictionary. The aim is to later save
        a json file with a .tmap extension.
    """
    # This function first create nested lists and dictionary to add the the
    # final dictionary in the latter part of the function.

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
        {"name": "Color", "value": "0"},
    ]
    regions = {}
    idx = (
        0  # Image index, keeps track of images and labels to get a consistent
    )
    # indexing in the tmap project file.
    for data, meta, layer_type in layer_data:
        if layer_type == "image":
            layers.append(
                {
                    "name": meta["name"],
                    "tileSource": f"images/{meta['name']}.tif.dzi",
                }
            )
            layer_filters[str(idx)] = default_filters.copy()
            layer_opacities[str(idx)] = "{:.3f}".format(meta["opacity"])
            layer_visibilities[str(idx)] = bool(meta["visible"])
            idx += 1
        elif layer_type == "labels":
            layers.append(
                {
                    "name": meta["name"],
                    "tileSource": f"labels/{meta['name']}.tif.dzi",
                }
            )
            layer_filters[str(idx)] = default_filters.copy()
            layer_opacities[str(idx)] = "{:.3f}".format(meta["opacity"])
            layer_visibilities[str(idx)] = bool(meta["visible"])
            idx += 1
        elif layer_type == "shapes":
            regions.update(generate_shapes_dict(data, meta))

    # The final configuration to be returned, combining all the lists and
    # dictionaries generated above.
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
            {"function": "_autoLoadCSV", "module": "dataUtils", "value": True},
            {
                "function": "_globalMarkerScale",
                "module": "glUtils",
                "value": 7.5,
            },
        ],
    }
    if not regions:
        config["regions"] = {}
    elif internal_shapes:
        config["regions"] = regions
    else:
        config["regionFile"] = "regions/regions.json"

    return config


def generate_shapes_dict(
    data: FullLayerData, meta: Dict[str, Any]
) -> Dict[str, Any]:
    """Generates a dictionary containing the info to plot shapes in Tissuumaps.
    The dict can later on be exported as a geoJson file or added to the .tmap
    project file.

    Parameters
    ----------
    data : FullLayerData
        The Shapes layer data (A list of shapes, which are lists of points) as
        provided by Napari.
    meta : Dict[str, Any]
        The metadata of the shapes layer containing the name and colors of the
        shapes.

    Returns
    -------
    Dict[str, Any]
        A dictionary containing the information to draw the shapes in
        Tissuumaps.
    """
    shape_dict = {"type": "FeatureCollection", "features": []}
    for i, shape in enumerate(data):
        shape_type = meta["shape_type"][i]
        shape_name = meta["name"] + f"_{shape_type}_{i+1}"
        shape_color = (255 * meta["face_color"][i, :3]).astype(int).tolist()
        # We enumerate each shapes that appear in the layer
        subshape_dict = {
            "type": "Feature",
            "geometry": {"type": "MultiPolygon"},
            "properties": {
                "name": shape_name,
                "classification": {"name": ""},
                "color": shape_color,
                "isLocked": False,
            },
        }
        # Different shapes have different points to draw
        points_to_draw = []
        if shape_type == "ellipse":
            assert isinstance(shape, np.ndarray)
            ellipse_center = (
                (shape[0][0] + shape[2][0]) / 2.0,
                (shape[0][1] + shape[1][1]) / 2.0,
            )
            # `a` represents the vector from the center of the ellipse to the
            # right hand side, while `b` is the up vector.
            ellipse_a = shape[1][0] - ellipse_center[0]
            ellipse_b = shape[1][1] - ellipse_center[1]

            # Minimum arc distance is the the length of a single arc as a
            # function of the ellipse's radii. The purpose is such that the
            # resolution (number of points) grows with the ellipse. The formula
            # is approximated and compute the arc based on a circle with the
            # radius being equal to the longest axis of the ellipse.
            minimum_arc_distance = 3.0
            max_axis = np.maximum(np.abs(ellipse_a), np.abs(ellipse_b))
            N = np.maximum(
                int(np.ceil(2.0 * np.pi * max_axis / minimum_arc_distance)), 10
            )
            thetas = np.linspace(0, 2 * np.pi, N + 1)
            points_to_draw = np.stack(
                [
                    ellipse_a * np.cos(thetas) + ellipse_center[0],
                    ellipse_b * np.sin(thetas) + ellipse_center[1],
                ],
                axis=-1,
            )
        elif shape_type == "line" or shape_type == "path":
            assert isinstance(shape, np.ndarray)
            points_to_draw = np.vstack([shape, shape[-2::-1]])
        else:  # shape_type == "polygon" or shape_type == "rectangle"
            assert isinstance(shape, np.ndarray)
            points_to_draw = shape

        # The columns are swapped due to conventional differences between
        # Napari (y, x) and TissUUmaps (x, y)
        coordinates = points_to_draw[:, [1, 0]].tolist()
        subshape_dict["geometry"]["coordinates"] = [[coordinates]]
        # Adding the properties, if there are any
        properties = meta.get("properties", {}).copy()
        for prop in properties:
            if isinstance(properties[prop], np.ndarray):
                properties[prop] = properties[prop].tolist()[i]
        subshape_dict["properties"]["extra"] = properties
        # We add it to the full dict
        shape_dict["features"].append(subshape_dict)
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
) -> List[str]:
    """Creates a Tissuumaps project folder based on a Napari list of layers.

    Parameters
    ----------
    save_path : Union[Path, str]
        The path to save the Tissuumaps project to. Must contain the name of
        the tissumap project file, including the .tmap extension.
    layer_data : List[FullLayerData]
        The list of layers to save as provided by Napari.
    Returns
    -------
    List[str]
        A list of string containing each of the filenames that were written.
    """
    savedfilenames = []
    # The main tissuumaps project folder is created.
    save_path = Path(save_path)
    save_path.mkdir(parents=True, exist_ok=True)

    # Creation of the tmap file
    tmap_cfg = generate_tmap_config(save_path.stem, layer_data)
    tmap_file = open(save_path / "main.tmap", "w+")
    savedfilenames.append(tmap_file.name)
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
            savedfilenames.append(path_image)
        elif layer_type == "points":
            # The Napari points are in a different coordinate system (y,x)
            # that must be converted to Tissuumaps which uses (x,y). The colors
            # of the individual points are extracted from the metadata.
            points_folder = save_path / "points"
            points_folder.mkdir(exist_ok=True)
            path_points = points_folder / f"{meta['name']}.csv"
            # Constructing the columns
            y, x = data[:, 0:1], data[:, 1:2]
            color = np.array(
                [[rgb2hex(color)] for color in meta["face_color"]]
            )
            symbol = np.array([[meta["symbol"]]] * x.shape[0])
            points = np.block([x, y, color, symbol])
            # Extract the properties
            properties = meta.get("properties")
            # Saving the csv file manually.
            points_file = open(path_points, "w+")
            savedfilenames.append(path_points.name)
            prop_keys = "," + ",".join(properties.keys()) if properties else ""
            points_file.write(f"name,x,y,color,symbol{prop_keys}\n")
            for i, (_x, _y, _color, _symbol) in enumerate(points):
                points_file.write(
                    f"{meta['name']},{_x},{_y},{_color},{_symbol}"
                )
                if properties:
                    for prop in properties.keys():
                        points_file.write(f",{properties[prop][i]}")
                points_file.write("\n")
            points_file.close()
        elif layer_type == "labels":
            # The labels layers may have multiple sub-labels that must be
            # separated in different images for Tissuumaps to read. Each label
            # gets a color given by a random colormap from Napari.
            labels_folder = save_path / "labels"
            labels_folder.mkdir(exist_ok=True)
            path_label = labels_folder / f"{meta['name']}.tif"
            # Recreating the colored image
            label_layer = Labels(data, **meta)
            label_img = label_layer.colormap.map(
                label_layer._raw_to_displayed(data)
            )
            label_img_uint8 = (label_img * 255.0).astype(np.uint8)
            imsave(str(path_label), label_img_uint8)
            savedfilenames.append(path_label)
        elif layer_type == "shapes":
            regions.update(generate_shapes_dict(data, meta))
        else:
            logger.warning(
                f"Layer \"{meta['name']}\" cannot be saved. This type of layer"
                " ({layer_type}) is not yet implemented."
            )

    # Saving the shapes
    if len(regions) > 0:
        shapes_folder = save_path / "regions"
        shapes_folder.mkdir(exist_ok=True)
        # Saving the json
        shapes_filename = "regions.json"
        shapes_file = open(shapes_folder / shapes_filename, "w+")
        savedfilenames.append(shapes_file.name)
        shapes_file.write(json.dumps(regions, indent=4))
        shapes_file.close()

    # Convertion from Path to str
    savedfilenames = list(map(str, savedfilenames))
    return savedfilenames
