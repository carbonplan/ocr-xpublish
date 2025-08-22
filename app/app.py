import os

os.environ["NUMBA_DISABLE_JIT"] = "1"  # fixes threading errors

import logfire
import xarray as xr
import xpublish
from fastapi.middleware.cors import CORSMiddleware
from xpublish_wms import CfWmsPlugin


def apply_time_horizon(ds: xr.Dataset, var: str) -> xr.Dataset:
    ds[f"{var}_horizon_1"] = ds[var] * 100
    ds[f"{var}_horizon_15"] = (1 - (1 - ds[var]) ** 15) * 100
    ds[f"{var}_horizon_30"] = (1 - (1 - ds[var]) ** 30) * 100
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


def get_ds(branch: str):
    with logfire.span(f"Loading dataset for branch: {branch}"):
        import icechunk
        import xarray as xr

        with logfire.span("opening icechunk repository"):
            storage = icechunk.s3_storage(
                bucket="carbonplan-ocr",
                prefix=f"output/fire-risk/tensor/{branch}/template.icechunk",
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

    rest = xpublish.Rest(
        {"prod": get_ds(branch="prod"), "QA": get_ds(branch="QA"), "RPS": get_rps_ds()},
        plugins={"wms": CfWmsPlugin()},
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
