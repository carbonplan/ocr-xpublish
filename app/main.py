from mangum import Mangum

from app import xpublish_app

rest = xpublish_app()
handler = Mangum(rest.app)
