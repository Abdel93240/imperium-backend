import getpass
import json
import urllib.request
import urllib.error
from pathlib import Path

API = "http://127.0.0.1:8000"

password = getpass.getpass("Imperium password: ")

body = {
    "email": "abderrahman0011@hotmail.fr",
    "password": password,
    "device_label": "vps-smoke-test-2o",
}

raw = json.dumps(body).encode()

req = urllib.request.Request(
    API + "/api/auth/login",
    data=raw,
    method="POST",
    headers={"Content-Type": "application/json"},
)

try:
    with urllib.request.urlopen(req, timeout=10) as r:
        txt = r.read().decode()
        data = json.loads(txt)
        token = data["access_token"]
        Path("/tmp/imperium_access_token").write_text(token)
        print("STATUS", r.status)
        print("TOKEN length:", len(token))
        print("token_saved /tmp/imperium_access_token")
except urllib.error.HTTPError as e:
    print("HTTP_ERROR", e.code)
    print(e.read().decode())
    raise
