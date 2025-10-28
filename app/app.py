import re

import xarray as xr
import xpublish
from fastapi.middleware.cors import CORSMiddleware
from xpublish_tiles.xpublish.tiles import TilesPlugin
from xpublish import hookimpl
from odc.geo.xr import assign_crs


def get_ds(branch: str, production_version: str | None = None):
    import icechunk
    import xarray as xr

    if production_version and branch == "production":
        prefix = f"output/fire-risk/tensor/{branch}/{production_version}/ocr.icechunk"
        dataset_id = f"production-{production_version}"
    else:
        prefix = f"output/fire-risk/tensor/{branch}/ocr.icechunk"
        dataset_id = branch

    storage = icechunk.s3_storage(
        bucket="carbonplan-ocr",
        prefix=prefix,
        region="us-west-2",
        anonymous=True,
    )
    repo = icechunk.Repository.open(storage)
    session = repo.readonly_session("main")

    ds = xr.open_zarr(session.store, consolidated=False)
    ds = ds.rename({"latitude": "lat", "longitude": "lon"})
    ds = assign_crs(ds, crs="EPSG:4326")

    ds.attrs["_xpublish_id"] = dataset_id
    return ds


def xpublish_app():
    datasets: dict[str, xr.Dataset] = {
        "qa": get_ds(branch="qa"),
        "staging": get_ds(branch="staging"),
    }

    class VersionedDatasetResolver:
        def __init__(self, store: dict[str, xr.Dataset]):
            self._store = store
            self._pattern = re.compile(r"^production-(?P<version>v\d+\.\d+\.\d+)$")

        @hookimpl
        def get_dataset(self, dataset_id: str):
            if dataset_id in self._store:
                return self._store[dataset_id]
            match = self._pattern.match(dataset_id)
            if match:
                version = match.group("version")
                ds = get_ds(branch="production", production_version=version)
                self._store[dataset_id] = ds
                return ds
            return None

    rest = xpublish.Rest(
        datasets,
        plugins={
            "tiles": TilesPlugin(),
            "versioned": VersionedDatasetResolver(datasets),
        },
    )

    rest.app.add_middleware(
        CORSMiddleware,
        allow_origin_regex=r"https?://(.*\.)?carbonplan\.org|http://(localhost|127\.0\.0\.1)(:\d+)?|https://.*\.vercel\.app",
    )

    return rest
