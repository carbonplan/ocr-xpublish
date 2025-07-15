## Serve USFS BP with Xpublish-WMS

### Usage

1. clone repo
2. install uv (<https://docs.astral.sh/uv/getting-started/installation/>)
3. In the repo run: `uv sync`
4. run `uv run python app/serve.py`
   or in a python session:

```python
from wms.app import xpublish_app
rest = xpublish_app()
rest.serve()
```

### Instrumentation via Logfire

```bash
uv add 'logfire[fastapi]' 
uv run logfire auth
uv run logfire projects new ocr --org carbonplan 
uv run logfire projects use ocr --org carbonplan
```
