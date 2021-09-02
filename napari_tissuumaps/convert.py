import json
from logging import getLogger
import logging
import os
from typing import Any, Dict, List, Optional
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


def generate_tmap_config(
    filename: str, layer_data: List[FullLayerData]
) -> Dict[str, Any]:
    def filter_type(arr, file_type):
        # Making sure file_type is a list
        if not isinstance(file_type, list):
            file_type = [file_type]

        return [
            (data, meta, layer_type)
            for (data, meta, layer_type) in arr
            if layer_type in file_type
        ]

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

    layers, layer_opacities, layer_visibilities = [], {}, {}
    idx = 0  # Image index
    for data, meta, layer_type in filter_type(layer_data, ["image", "labels"]):
        if layer_type == "image":
            layers.append(
                {"name": meta["name"], "tileSource": f"images/{meta['name']}.tif.dzi"}
            )
            layer_opacities[str(idx)] = str(meta["opacity"])
            layer_visibilities[str(idx)] = str(meta["visible"])
            idx += 1
        elif layer_type == "labels":
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
    """ """
    if not is_path_tissuumaps_filename(path):
        return None

    create_folder_if_not_exist(path)

    filename = os.path.basename(path)  # Extracting filename from path
    filename = filename[: filename.find(".")]  # Removing the extensions from the name
    # Creation of the tmap file
    tmap_cfg = generate_tmap_config(filename, layer_data)
    tmap_file = open(f"{path}/main.tmap", "w+")
    tmap_file.write(json.dumps(tmap_cfg, indent=4))
    tmap_file.close()
    # Saving the files
    for data, meta, layer_type in layer_data:
        if layer_type == "image":
            image_folder = create_folder_if_not_exist(path, "images")
            path_image = os.path.join(image_folder, f"{meta['name']}.tif")
            imsave(path_image, data)
        elif layer_type == "points":
            points_folder = create_folder_if_not_exist(path, "points")
            path_points = os.path.join(points_folder, f"{meta['name']}.csv")
            # Constructing the columns
            y, x = data[:, 0:1], data[:, 1:2]
            color = np.array([[rgb2hex(color)] for color in meta["face_color"]])
            points = np.block([x, y, color])
            # np.savetxt(path_points, points, delimiter=",", header="x,y", comments="")
            points_file = open(path_points, "w+")
            points_file.write("name,x,y,color\n")
            for _x, _y, _color in points:
                points_file.write(f"{meta['name']},{_x},{_y},{_color}\n")
            points_file.close()
        elif layer_type == "labels":
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
            logging.warning("Shape layers are not yet supported.")
        else:
            logging.warning(
                f"Layer \"{meta['name']}\" cannot be saved. This type of layer "
                "({layer_type}) is not yet implemented."
            )
    return path
