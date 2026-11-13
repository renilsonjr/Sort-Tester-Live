"""Headers a real browser sends, for tests that drive the API like one.

Writes are refused without an `Origin` (see `backend/origin_guard.py`), so
a TestClient that posts must state one, exactly as a browser does. The
host matches TestClient's default base URL, `http://testserver`.
"""

BROWSER = {"Origin": "http://testserver"}
