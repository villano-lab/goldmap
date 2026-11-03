"""goldmap: lay out a processing in the browser.

A *survey* of the raw data (which series are on the disk, and what is known about each) ends in the two files a `goldsluice run` needs: the dataset
definition (`goldpan.dataset`) and the run-metadata CSV (`goldpan.runmeta`). The app is local: `python -m goldmap` starts a server on
127.0.0.1 and opens the page; the files are checked by goldpan and goldsluice themselves, so a file it writes is one they accept.

    catalog   what the page offers: the algorithms, the detectors of a registry, the series on a disk, the facts of a series list
    build     the form of the page -> the definition and the metadata table -> the files
    server    the local web server
    dialog    the computer's own window for choosing a folder
"""
__version__ = "0.1.0"
