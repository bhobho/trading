import subprocess
import time
import requests

p = subprocess.Popen(["./path/to/venv/bin/uvicorn", "main:app", "--port", "8005"])
time.sleep(2)
try:
    r = requests.get("http://localhost:8005/auth/login")
    print("STATUS:", r.status_code)
    if r.status_code == 500:
        print("UVICORN return 500")
except Exception as e:
    print("Req err:", e)
finally:
    p.kill()
