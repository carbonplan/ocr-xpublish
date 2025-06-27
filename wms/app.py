import os
os.environ['NUMBA_DISABLE_JIT'] = '1' # fixes threading errors

import xpublish
from xpublish_wms import CfWmsPlugin
import xarray as xr
from fastapi.middleware.cors import CORSMiddleware

def apply_time_horizon(ds:xr.Dataset, var:str) -> xr.Dataset:
    ds[var+'_horizon_1'] = ds[var] * 100.0
    ds[var+'_horizon_15'] = (1 - (1 - ds[var]) ** 15) * 100
    ds[var+'_horizon_30'] = (1 - (1 - ds[var]) ** 30) * 100
    return ds

def get_ds():
    import icechunk
    storage = icechunk.s3_storage(
        bucket="carbonplan-ocr",
        prefix="intermediate/fire-risk/tensor/QA/template.icechunk",
        region="us-west-2",
        anonymous=True,
    )
    repo = icechunk.Repository.open_or_create(storage)
    session = repo.readonly_session("main")

    ds = xr.open_zarr(session.store, consolidated=False)
    for var in list(ds):
        ds = apply_time_horizon(ds,var)
    return ds

def xpublish_app():
    ds = get_ds()
    rest = xpublish.Rest({"fire": ds}, plugins={"wms": CfWmsPlugin()})

    # allow cors for carbonplan.org and localhost only
    rest.app.add_middleware(
        CORSMiddleware,
        allow_origin_regex=r"https?://(.*\.)?carbonplan\.org|http://(localhost|127\.0\.0\.1)(:\d+)?",
    )

    return rest
