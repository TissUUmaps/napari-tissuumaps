import napari
from skimage.data import astronaut
import tempfile
import hashlib
from pathlib import Path


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
        tmp_dir = Path(tmp_dir) / "test_project.tmap"
        viewer.layers.save(str(tmp_dir), plugin="napari-tissuumaps")

        filehashes = {
            "main.tmap": "b1264dcf21e7b28d29ea849b6117cd14",
            "images/Image.tif": "ef2801501c0347091c17dc753f1a7360",
            "labels/Labels.tif": "d5d72094605e0cb30dffcd8e3f343f77",
            "points/Points.csv": "649f61a21544c974a7994aebe06ad3df",
            "regions/regions.json": "3dba01a0c05a772b0a347cd8fde0af99",
        }
        for (filename, true_hash) in filehashes.items():
            file = open(tmp_dir / filename, "rb")
            test_hash = hashlib.md5(file.read())
            file.close()
            assert test_hash.hexdigest() == true_hash
