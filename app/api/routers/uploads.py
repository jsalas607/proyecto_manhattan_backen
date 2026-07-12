import os
import uuid

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile

from app.core.config import settings
from app.deps import get_current_user
from app.models.organization import User
from app.schemas.base import CamelModel

router = APIRouter(prefix="/uploads", tags=["uploads"])

ALLOWED = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp", "image/gif": ".gif"}


class UploadOut(CamelModel):
    url: str


@router.post("", response_model=UploadOut, status_code=201)
async def upload_image(
    request: Request,
    file: UploadFile = File(...),
    _: User = Depends(get_current_user),
):
    if file.content_type not in ALLOWED:
        raise HTTPException(status_code=400, detail="Tipo de imagen no soportado (jpg/png/webp/gif)")

    data = await file.read()
    if len(data) > settings.MAX_UPLOAD_MB * 1024 * 1024:
        raise HTTPException(status_code=413, detail=f"Máximo {settings.MAX_UPLOAD_MB} MB")

    ext = ALLOWED[file.content_type]
    name = f"{uuid.uuid4().hex}{ext}"
    os.makedirs(settings.UPLOADS_DIR, exist_ok=True)
    path = os.path.join(settings.UPLOADS_DIR, name)
    with open(path, "wb") as f:
        f.write(data)

    url = str(request.base_url).rstrip("/") + f"/uploads/{name}"
    return UploadOut(url=url)
