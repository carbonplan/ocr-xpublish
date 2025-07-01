import os

os.environ["NUMBA_DISABLE_JIT"] = "1"  # fixes threading errors

import xpublish
from xpublish_wms import CfWmsPlugin
import xarray as xr
from fastapi.middleware.cors import CORSMiddleware


def apply_time_horizon(ds: xr.Dataset, var: str) -> xr.Dataset:
    ds[var + "_horizon_1"] = ds[var] * 100.0
    ds[var + "_horizon_15"] = (1 - (1 - ds[var]) ** 15) * 100
    ds[var + "_horizon_30"] = (1 - (1 - ds[var]) ** 30) * 100
    return ds


def get_ds(branch: str):
    import icechunk
    import xarray as xr 
    storage = icechunk.s3_storage(
        bucket="carbonplan-ocr",
        prefix=f"intermediate/fire-risk/tensor/{branch}/template.icechunk",
        region="us-west-2",
        anonymous=True,
    )
    repo = icechunk.Repository.open_or_create(storage)
    session = repo.readonly_session("main")

    ds = xr.open_zarr(session.store, consolidated=False)
    for var in list(ds):
        ds = apply_time_horizon(ds, var)
    return ds


def xpublish_app():
    rest = xpublish.Rest(
        {"prod": get_ds(branch="prod"), "QA": get_ds(branch="QA")},
        plugins={"wms": CfWmsPlugin()},
        cache_kws=dict(available_bytes=1e9),
    )

    # allow cors for carbonplan.org, localhost, and vercel
    rest.app.add_middleware(
        CORSMiddleware,
        allow_origin_regex=r"https?://(.*\.)?carbonplan\.org|http://(localhost|127\.0\.0\.1)(:\d+)?|https://.*\.vercel\.app",
    )

    return rest
