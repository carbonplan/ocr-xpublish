import os

os.environ["NUMBA_CACHE_DIR"] = "/tmp"
os.environ["NUMBA_NUM_THREADS"] = "1"
os.environ["XPUBLISH_TILES_ASYNC_LOAD"] = "true"
os.environ["XPUBLISH_TILES_NUM_THREADS"] = "2"
os.environ["XPUBLISH_TILES_DETECT_APPROX_RECTILINEAR"] = "true"

from .app import xpublish_app as xpublish_app
