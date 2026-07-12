from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect, status
from sqlalchemy import select

from app.core.database import AsyncSessionLocal
from app.core.security import decode_access_token
from app.models.organization import Membership, User

router = APIRouter(tags=["websockets"])


async def _authorize(token: str | None, restaurant_id: str) -> bool:
    """Valida el JWT (por query param) y el acceso al restaurante."""
    if not token:
        return False
    payload = decode_access_token(token)
    if payload is None or "sub" not in payload:
        return False
    async with AsyncSessionLocal() as db:
        user = await db.get(User, payload["sub"])
        if user is None:
            return False
        if user.is_admin:
            return True
        result = await db.execute(
            select(Membership).where(
                Membership.user_id == user.id, Membership.restaurant_id == restaurant_id
            )
        )
        return result.scalar_one_or_none() is not None


async def _handle(ws: WebSocket, rid: str, canal: str, token: str | None) -> None:
    if not await _authorize(token, rid):
        await ws.close(code=status.WS_1008_POLICY_VIOLATION)
        return
    from app.ws.manager import manager

    await manager.connect(rid, canal, ws)
    try:
        while True:
            # mantenemos viva la conexión; el cliente puede enviar pings
            await ws.receive_text()
    except WebSocketDisconnect:
        await manager.disconnect(rid, canal, ws)
    except Exception:
        await manager.disconnect(rid, canal, ws)


@router.websocket("/ws/restaurants/{rid}/pedidos")
async def ws_pedidos(ws: WebSocket, rid: str, token: str | None = Query(default=None)):
    await _handle(ws, rid, "pedidos", token)


@router.websocket("/ws/restaurants/{rid}/despacho")
async def ws_despacho(ws: WebSocket, rid: str, token: str | None = Query(default=None)):
    await _handle(ws, rid, "despacho", token)
