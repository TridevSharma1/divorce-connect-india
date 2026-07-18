import sys
sys.path.append(r"d:\Software Setup\C\Django_Projects\PROJECT99\divorce-connect-india\divorce_connect")

from fastapi.testclient import TestClient
from fastapi_app.main import app

client = TestClient(app)
for p in ["/privacy-policy", "/terms-of-service", "/refund-policy", "/privacy_policy", "/terms_of_service", "/refund_policy"]:
    r = client.get(p)
    print(f"{p} -> status {r.status_code}, redirect to {r.headers.get('location') if r.status_code in (302, 303, 307) else 'none'}")
