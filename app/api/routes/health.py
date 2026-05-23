from fastapi import APIRouter

from app.core.settings import settings

router = APIRouter(tags=["health"])


@router.get("/health")
async def health():
    from app.main import trading_engine

    return {
        "status": "ok",
        "paper_trading": settings.PAPER_TRADING,
        "auto_trading": settings.AUTO_TRADING,
        "engine": trading_engine.status(),
    }
