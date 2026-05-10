from fastapi import Request
from fastapi.templating import Jinja2Templates

templates = Jinja2Templates(directory="templates")

# dummy request
class DummyRequest:
    def __init__(self):
        self.scope = {"type": "http"}
    def keys(self): return []

req = DummyRequest()
try:
    resp = templates.TemplateResponse(req, "login.html", {"request": req})
    print("Success:", type(resp))
except Exception as e:
    import traceback
    traceback.print_exc()
