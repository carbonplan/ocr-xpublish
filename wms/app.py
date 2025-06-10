import xpublish
from xpublish_wms import CfWmsPlugin
import xarray as xr


def get_ds():
    import icechunk

    storage = icechunk.s3_storage(
        bucket="carbonplan-ocr",
        prefix="input/fire-risk/tensor/USFS/RDS-2022-0016-02_EPSG_4326_icechunk_all_vars",
        region="us-west-2",
    )
    repo = icechunk.Repository.open_or_create(storage)
    session = repo.readonly_session("main")

    ds = xr.open_zarr(session.store, consolidated=False)
    # subsetting to a single var and seattle + the I90 corridor
    seattle_nb_bbox = (-122.412415, 47.303215, -121.563721, 47.641278)
    return ds[["RPS"]].sel(
        latitude=slice(seattle_nb_bbox[3], seattle_nb_bbox[1]),
        longitude=slice(seattle_nb_bbox[0], seattle_nb_bbox[2]),
    )


def xpublish_app():
    ds = get_ds()
    rest = xpublish.Rest({"risk": ds}, plugins={"wms": CfWmsPlugin()})
    return rest
