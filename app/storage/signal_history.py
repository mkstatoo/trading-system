import json
from datetime import datetime, timedelta, timezone

from app.core.settings import settings
from app.storage.database import SessionLocal, SignalHistoryModel, init_db

_db_ready = False


def _ensure_db() -> None:
    global _db_ready
    if not _db_ready:
        init_db()
        _db_ready = True


def has_recent_signal(market: str) -> bool:
    _ensure_db()
    db = SessionLocal()
    try:
        cutoff = datetime.now(timezone.utc) - timedelta(days=settings.T6_COOLDOWN_DAYS)
        row = (
            db.query(SignalHistoryModel)
            .filter(
                SignalHistoryModel.market == market,
                SignalHistoryModel.passed.is_(True),
                SignalHistoryModel.created_at >= cutoff,
            )
            .first()
        )
        return row is not None
    finally:
        db.close()


def record_signal(market: str, filters_report: dict) -> None:
    _ensure_db()
    db = SessionLocal()
    try:
        db.add(
            SignalHistoryModel(
                market=market,
                passed=True,
                filters_json=json.dumps(filters_report, ensure_ascii=False),
            )
        )
        db.commit()
    finally:
        db.close()
