from fastapi import FastAPI, Request
from fastapi.templating import Jinja2Templates
from fastapi.testclient import TestClient

app = FastAPI()
templates = Jinja2Templates(directory="templates")

@app.get("/login1")
async def login1(request: Request):
    return templates.TemplateResponse(request, "login.html", {"request": request, "error": None})

client = TestClient(app)
try:
    print("Testing /login1 with request in both args and context")
    r1 = client.get("/login1")
    print(r1.status_code)
except Exception as e:
    print("FAILED /login1", type(e), e)
