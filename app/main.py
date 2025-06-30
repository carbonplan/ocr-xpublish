from app import xpublish_app
from mangum import Mangum

rest = xpublish_app()
handler = Mangum(rest.app)
