"""Minimal reference receiver for `fast-chimera shift` (your platform's side of the contract).

    pip install fastapi uvicorn
    SHIFT_API_TOKEN=change-me uvicorn shift_receiver:app --port 9000

Client side (.env of the project being fingerprinted):
    SHIFT_SERVER_URL=http://localhost:9000/api/shift
    SHIFT_API_TOKEN=change-me
"""

import hmac
import os

from fastapi import Depends, FastAPI, Header, HTTPException, Request

app = FastAPI(title="Shift receiver")
TOKEN = os.environ.get("SHIFT_API_TOKEN", "")
STORE: dict[str, dict] = {}  # replace with your database


def check_token(authorization: str = Header(default="")) -> None:
    if TOKEN and not hmac.compare_digest(authorization, f"Bearer {TOKEN}"):
        raise HTTPException(status_code=401, detail="invalid token")


@app.post("/api/shift", status_code=201, dependencies=[Depends(check_token)])
async def receive(request: Request) -> dict:
    data = await request.json()
    if data.get("schema_version") != 1 or "tables" not in data or "endpoints" not in data:
        raise HTTPException(status_code=422, detail="not a fast-chimera fingerprint (schema_version 1)")
    fingerprint_id = data["content_sha256"][:16]  # same structure => same id, so retries are idempotent
    STORE[fingerprint_id] = data
    return {"id": fingerprint_id, "tables": len(data["tables"]), "endpoints": len(data["endpoints"])}


@app.get("/api/shift/{fingerprint_id}")
def read(fingerprint_id: str, _: None = Depends(check_token)) -> dict:
    if fingerprint_id not in STORE:
        raise HTTPException(status_code=404)
    return STORE[fingerprint_id]
