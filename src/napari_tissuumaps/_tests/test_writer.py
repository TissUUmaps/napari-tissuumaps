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
        tmp_dir = Path(tmp_dir) / "test_project.tmap"
        viewer.layers.save(str(tmp_dir), plugin="napari-tissuumaps")

        # Images may differ between versions of libraries, so we just check if
        # they exist.
        for file in [
            "main.tmap",
            "points/Points.csv",
            "images/Image.tif",
            "labels/Labels.tif",
            "regions/regions.json",
        ]:
            assert (tmp_dir / file).exists()
