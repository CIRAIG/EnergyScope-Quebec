from importlib.metadata import version, PackageNotFoundError

try:
    __version__ = version("energyscope-quebec-shared")
except PackageNotFoundError:
    # Package not installed (e.g. running directly from source without pip install -e)
    __version__ = "unknown"