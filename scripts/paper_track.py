"""
ثبت و گزارش عملکرد Paper Trading برای اعتبارسنجی forward-test.

  python scripts/paper_track.py

خروجی: reports/paper_performance.txt
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.settings import settings
from app.storage.database import SessionLocal
from app.storage.database import SignalHistoryModel, TradeModel

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "reports" / "paper_performance.txt"


def main():
    db = SessionLocal()
    try:
        signals = db.query(SignalModel).order_by(SignalModel.created_at.desc()).limit(500).all()
        trades = db.query(TradeModel).order_by(TradeModel.created_at.desc()).limit(500).all()
    finally:
        db.close()

    lines = [
        "گزارش Paper Trading (داده واقعی زنده)",
        f"زمان: {datetime.now(timezone.utc).isoformat()}",
        f"استراتژی: Bull Hunter T0={settings.T0_MIN_PCT}-{settings.T0_MAX_PCT}%",
        f"MIN_FILTERS={settings.MIN_FILTERS_PASS}/{settings.TOTAL_FILTERS}",
        "",
        f"تعداد سیگنال ثبت‌شده: {len(signals)}",
        f"تعداد معامله paper: {len(trades)}",
        "",
    ]

    if signals:
        lines.append("آخرین سیگنال‌ها:")
        for s in signals[:20]:
            lines.append(f"  {s.market} @ {s.created_at}")

    lines.extend(
        [
            "",
            "برای اطمینان از win rate:",
            "  - حداقل ۳۰ روز paper بدون تغییر پارامتر",
            "  - مقایسه win rate با backtest_real.py",
            "  - http://127.0.0.1:7000/status",
        ]
    )

    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))
    print(f"\nSaved: {REPORT}")


if __name__ == "__main__":
    main()
