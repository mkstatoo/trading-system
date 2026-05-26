"""
بررسی خودکار معیارهای اطمینان از استراتژی بر اساس آخرین گزارش walk-forward.

  python scripts/validate_confidence.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPORT_JSON = ROOT / "reports" / "backtest_real_signals.json"


def main():
    if not REPORT_JSON.exists():
        print("ابتدا اجرا کنید: python scripts/backtest_real.py --walk-forward")
        sys.exit(1)

    data = json.loads(REPORT_JSON.read_text(encoding="utf-8"))
    agg = data.get("aggregate", {})
    h12 = agg.get("h12", {})
    n = h12.get("n", 0)
    win = h12.get("win_pct", 0)
    avg = h12.get("avg", 0)
    ci_low = h12.get("ci_low", 0)

    checks = [
        ("حداقل ۴۰ سیگنال", n >= 40, f"{n} سیگنال"),
        ("نرخ برد ۱۲h > ۵۵٪", win > 55, f"{win}%"),
        ("CI95% پایین > ۴۵٪", ci_low > 45, f"{ci_low}%"),
        ("میانگین ret12h مثبت", avg > 0, f"{avg}%"),
    ]

    print("=== اعتبارسنجی اطمینان Bull Hunter ===\n")
    passed = 0
    for name, ok, detail in checks:
        status = "PASS" if ok else "FAIL"
        print(f"  [{status}] {name} ({detail})")
        if ok:
            passed += 1

    print(f"\nنتیجه: {passed}/{len(checks)} معیار")
    if passed == len(checks):
        print("استراتژی از نظر آماری در بک‌تست قابل قبول است — paper trading ۳۰ روز را ادامه دهید.")
    else:
        print(
            "هنوز نمی‌توان ۱۰۰٪ به نرخ برد مطمئن شد. "
            "paper trading زنده و بهینه‌سازی محتاطانه ادامه یابد."
        )


if __name__ == "__main__":
    main()
