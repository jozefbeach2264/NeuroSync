from fastapi import APIRouter
from webhook_handler import router as webhook_router

router = APIRouter()
router.include_router(webhook_router)
