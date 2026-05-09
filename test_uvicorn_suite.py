import subprocess
import time
import requests

p = subprocess.Popen(["./path/to/venv/bin/uvicorn", "main:app", "--port", "8008"])
time.sleep(2)
try:
    for endpoint in ["/auth/login", "/analyzer/", "/ai-analysis/", "/"]:
        r = requests.get(f"http://localhost:8008{endpoint}")
        print(f"STATUS for {endpoint}:", r.status_code)
        if r.status_code != 200:
            print(f"ERROR content: {r.text[:500]}")
except Exception as e:
    print("Req err:", e)
finally:
    p.kill()
