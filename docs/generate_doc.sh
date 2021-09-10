#!/bin/bash

# Please install pdoc with `pip install pdoc` prior to running this script
if ! command -v pdoc &> /dev/null
then
    echo "pdoc could not be found."
    echo "Please make sure pdoc is installed (pip install pdoc)."
    exit
fi

pdoc \
    -o docs \
    -d numpy \
    --logo https://github.com/wahlby-lab/TissUUmaps/raw/master/misc/design/logo.png \
    --logo-link https://github.com/wahlby-lab/napari-tissuumaps/ \
    ../napari_tissuumaps

