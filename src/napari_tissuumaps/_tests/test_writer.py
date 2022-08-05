import hashlib
import tempfile
from pathlib import Path

import napari
from skimage.data import astronaut


def load_napari_test_project():
    assets_dir = Path(__file__).resolve().parent / "assets"
    # Loading an image
    viewer = napari.view_image(astronaut(), rgb=True)

    # Loading the labels
    viewer.open(
        assets_dir / "labels.tif",
        color={1: "red", 2: "green", 3: "blue"},
        name="Labels",
    )

    # Loading the points
    viewer.open(assets_dir / "points.csv", symbol="star", name="Points")

    # Loading the shapes
    viewer.open(assets_dir / "shapes.csv", name="Shapes")

    return viewer


def test_writer():
    viewer = load_napari_test_project()

    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_dir = Path("/Users/nicolas/Desktop") / "test_project.tmap"
        viewer.layers.save(str(tmp_dir), plugin="napari-tissuumaps")

        # Images may differ between versions of libraries, so we just check if
        # they exist.
        assert (tmp_dir / "images/Image.tif").exists()
        assert (tmp_dir / "labels/Labels.tif").exists()
        # Check the hashes of the remaining files
        filehashes = {
            "main.tmap": "72ef43b7e26c18665f4dda34c9c397b8",
            "points/Points.csv": "649f61a21544c974a7994aebe06ad3df",
            "regions/regions.json": "3dba01a0c05a772b0a347cd8fde0af99",
        }
        for (filename, true_hash) in filehashes.items():
            file = open(tmp_dir / filename, "rb")
            test_hash = hashlib.md5(file.read())
            file.close()
            assert test_hash.hexdigest() == true_hash
