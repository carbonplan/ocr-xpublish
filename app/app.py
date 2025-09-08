import os
import re

os.environ["NUMBA_DISABLE_JIT"] = "1"  # fixes threading errors

import logfire
import xarray as xr
import xpublish
from fastapi.middleware.cors import CORSMiddleware
from xpublish_wms import CfWmsPlugin
from xpublish import hookimpl


def apply_time_horizon(ds: xr.Dataset, var: str) -> xr.Dataset:
    ds[f"{var}_horizon_1"] = ds[var]
    ds[f"{var}_horizon_15"] = (1 - (1 - (ds[var] / 100.0)) ** 15) * 100
    ds[f"{var}_horizon_30"] = (1 - (1 - (ds[var] / 100.0)) ** 30) * 100
    return ds


def get_rps_ds():
    import icechunk
    import xarray as xr

    storage = icechunk.s3_storage(
        bucket="carbonplan-ocr",
        prefix="input/fire-risk/tensor/USFS/RDS-2022-0016-02_EPSG_4326_icechunk_all_vars",
        region="us-west-2",
        anonymous=True,
    )
    repo = icechunk.Repository.open(storage)
    session = repo.readonly_session("main")
    ds = xr.open_zarr(session.store, consolidated=False)[["RPS"]]
    for var in list(ds):
        logfire.info(f"Applying time horizon to variable: {var}")
        ds = apply_time_horizon(ds, var)

    return ds


def get_old_prod():
    import icechunk
    import xarray as xr

    storage = icechunk.s3_storage(
        bucket="carbonplan-ocr",
        prefix="output/fire-risk/tensor/prod/template.icechunk",
        region="us-west-2",
        anonymous=True,
    )
    repo = icechunk.Repository.open(storage)
    session = repo.readonly_session("main")
    ds = xr.open_zarr(session.store, consolidated=False)
    for var in list(ds):
        ds = apply_time_horizon(ds, var)
    return ds


def get_ds(branch: str, production_version: str | None = None):
    with logfire.span(f"Loading dataset for branch: {branch}"):
        import icechunk
        import xarray as xr

        if production_version and branch == "production":
            prefix = (
                f"output/fire-risk/tensor/{branch}/{production_version}/ocr.icechunk"
            )
        else:
            prefix = f"output/fire-risk/tensor/{branch}/ocr.icechunk"

        with logfire.span("opening icechunk repository"):
            storage = icechunk.s3_storage(
                bucket="carbonplan-ocr",
                prefix=prefix,
                region="us-west-2",
                anonymous=True,
            )
            repo = icechunk.Repository.open(storage)
            session = repo.readonly_session("main")

            with logfire.span("opening xarray dataset from icechunk repository"):
                ds = xr.open_zarr(session.store, consolidated=False)

                with logfire.span("applying time horizons"):
                    for var in list(ds):
                        logfire.info(f"Applying time horizon to variable: {var}")
                        ds = apply_time_horizon(ds, var)

                return ds


def request_attributes_mapper(request, attributes):
    if attributes["errors"]:
        # Only log validation errors, not valid arguments
        return {
            "errors": attributes["errors"],
            "my_custom_attribute": ...,
        }
    else:
        # Don't log anything for valid requests
        return {
            "method": request.method,
            "path": request.url.path,
            "query": dict(request.query_params),
        }
        # return None


def xpublish_app():
    logfire.configure()
    logfire.info("Starting xpublish app...")
    logfire.instrument_requests()
    logfire.instrument_system_metrics()

    datasets: dict[str, xr.Dataset] = {
        "qa": get_ds(branch="qa"),
        "staging": get_ds(branch="staging"),
        "prod": get_old_prod(),
        "RPS": get_rps_ds(),
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
            "wms": CfWmsPlugin(),
            "versioned": VersionedDatasetResolver(datasets),
        },
        cache_kws=dict(available_bytes=1e9),
    )

    logfire.instrument_fastapi(
        rest.app, request_attributes_mapper=request_attributes_mapper
    )

    # allow cors for carbonplan.org, localhost, and vercel
    rest.app.add_middleware(
        CORSMiddleware,
        allow_origin_regex=r"https?://(.*\.)?carbonplan\.org|http://(localhost|127\.0\.0\.1)(:\d+)?|https://.*\.vercel\.app",
    )

    return rest
