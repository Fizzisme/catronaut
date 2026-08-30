from fastapi import APIRouter

from app.api import ui_ux

# No version or `/api` prefix here: this service runs behind the Go API gateway,
# which owns public routing, versioning and JWT. Paths are domain-relative.
api_router = APIRouter()
api_router.include_router(ui_ux.router, prefix="/ui-ux", tags=["ui-ux"])
