from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Annotated

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .auth import new_nonce, normalize_address, recover_signer, session_token, sign_in_message
from .chains import CHAINS
from .monitor import ChainMonitor
from .store import Store

ROOT = Path(__file__).resolve().parent
STATIC = ROOT / "static"

store = Store()
monitor = ChainMonitor(store)
app = FastAPI(title="EVM Watchtower", version="0.1.0")
app.mount("/static", StaticFiles(directory=STATIC), name="static")


class NonceRequest(BaseModel):
    address: str


class NonceResponse(BaseModel):
    nonce: str
    message: str


class VerifyRequest(BaseModel):
    address: str
    signature: str


class VerifyResponse(BaseModel):
    token: str
    wallet: str


class TelegramRequest(BaseModel):
    bot_token: str = Field(min_length=10)
    chat_id: str = Field(min_length=2)
    enabled: bool = True


class MonitorCreate(BaseModel):
    address: str
    label: str = ""
    chains: list[str]


class MonitorUpdate(BaseModel):
    active: bool = True
    chains: list[str]


def current_user(authorization: Annotated[str | None, Header()] = None) -> dict:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing bearer token")
    token = authorization.removeprefix("Bearer ").strip()
    user = store.session_user(token)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid session")
    return dict(user)


@app.on_event("startup")
async def startup() -> None:
    asyncio.create_task(monitor.run_forever())


@app.get("/", response_class=HTMLResponse)
def index() -> FileResponse:
    return FileResponse(STATIC / "index.html")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/chains")
def chains() -> list[dict]:
    return [
        {
            "key": chain.key,
            "name": chain.name,
            "chain_id": chain.chain_id,
            "native_symbol": chain.native_symbol,
            "explorer_url": chain.explorer_url,
        }
        for chain in CHAINS.values()
    ]


@app.post("/api/auth/nonce", response_model=NonceResponse)
def nonce(payload: NonceRequest) -> NonceResponse:
    address = normalize_address(payload.address)
    value = new_nonce()
    message = sign_in_message(address, value)
    store.set_nonce(address, value, message)
    return NonceResponse(nonce=value, message=message)


@app.post("/api/auth/verify", response_model=VerifyResponse)
def verify(payload: VerifyRequest) -> VerifyResponse:
    address = normalize_address(payload.address)
    row = store.get_nonce(address)
    if not row:
        raise HTTPException(status_code=400, detail="Nonce expired")
    signer = recover_signer(row["message"], payload.signature)
    if signer != address:
        raise HTTPException(status_code=401, detail="Signature does not match wallet")
    user_id = store.upsert_user(address)
    token = session_token()
    store.create_session(user_id, token)
    return VerifyResponse(token=token, wallet=address)


@app.get("/api/me")
def me(user: Annotated[dict, Depends(current_user)]) -> dict:
    return {"wallet": user["wallet"]}


@app.put("/api/telegram")
def set_telegram(payload: TelegramRequest, user: Annotated[dict, Depends(current_user)]) -> dict:
    store.set_telegram(user["id"], payload.bot_token, payload.chat_id, payload.enabled)
    return {"ok": True}


@app.get("/api/monitors")
def list_monitors(user: Annotated[dict, Depends(current_user)]) -> list[dict]:
    return store.list_monitors(user["id"])


@app.post("/api/monitors")
def create_monitor(payload: MonitorCreate, user: Annotated[dict, Depends(current_user)]) -> dict:
    chains = [chain for chain in payload.chains if chain in CHAINS]
    if not chains:
        raise HTTPException(status_code=400, detail="Select at least one chain")
    monitor_id = store.create_monitor(
        user_id=user["id"],
        address=normalize_address(payload.address),
        label=payload.label.strip(),
        chains=chains,
    )
    return {"id": monitor_id}


@app.put("/api/monitors/{monitor_id}")
def update_monitor(
    monitor_id: int,
    payload: MonitorUpdate,
    user: Annotated[dict, Depends(current_user)],
) -> dict:
    chains = [chain for chain in payload.chains if chain in CHAINS]
    if not chains:
        raise HTTPException(status_code=400, detail="Select at least one chain")
    store.update_monitor(user["id"], monitor_id, payload.active, chains)
    return {"ok": True}


@app.delete("/api/monitors/{monitor_id}")
def delete_monitor(monitor_id: int, user: Annotated[dict, Depends(current_user)]) -> dict:
    store.delete_monitor(user["id"], monitor_id)
    return {"ok": True}


@app.get("/api/events")
def events(user: Annotated[dict, Depends(current_user)], limit: int = 100) -> list[dict]:
    return store.list_events(user["id"], limit=min(limit, 300))

