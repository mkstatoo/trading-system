# trading-system

ربات معاملاتی async برای صرافی CoinEx با استراتژی **Bull Hunter** (مومنتوم).

## قابلیت‌ها

- اتصال REST CoinEx + WebSocket
- معاملات کاغذی (Paper) با قیمت‌های زنده بازار
- موتور ریسک (حد ضرر روزانه، حد پوزیشن باز)
- اسکنر بازار و اجرای خودکار سیگنال
- FastAPI + WebSocket برای مانیتورینگ
- SQLite / PostgreSQL
- Docker

## نصب سریع

```bash
python -m venv venv
venv\Scripts\activate          # Windows
pip install -r requirements.txt
copy .env.example .env         # کلید API را وارد کنید
uvicorn app.main:app --host 127.0.0.1 --port 7000 --reload
```

- داشبورد: http://127.0.0.1:7000  
- مستندات: http://127.0.0.1:7000/docs  

## اندپوینت‌های مهم

| مسیر | توضیح |
|------|--------|
| `GET /health` | وضعیت سیستم و موتور معاملات |
| `GET /status` | آمار اسکن و ترید |
| `GET /paper/balance` | موجودی Paper |
| `GET /trading/positions` | پوزیشن‌های باز |
| `POST /trading/order` | سفارش دستی Paper |

## بازارها (Top 300)

پیش‌فرض: **`SYMBOL_MODE=top300`** — ربات هر دور، **۳۰۰ جفت USDT** با بیشترین حجم ۲۴ساعته CoinEx را اسکن می‌کند (نه فقط BTC/ETH).  
لیست هر `TOP_MARKETS_REFRESH_HOURS` ساعت به‌روز می‌شود.  
برای لیست دستی: `SYMBOL_MODE=manual` و `TRADING_SYMBOLS=BTCUSDT,ETHUSDT,...`

## استراتژی Bull Hunter (T1–T8)

اسکن **Top 300** آلت‌کوین USDT؛ ورود **محتاطانه**: **۶ از ۸** فیلتر + **T1 و T2 اجباری**

| فیلتر | شرط |
|--------|------|
| T1 | حجم ≥ **۴×** میانگین (اجباری PASS) |
| T2 | RSI ۴۵–۷۰؛ ۷۰–۸۵ WARN مجاز |
| T3–T8 | MACD+, BB breakout, VWAP, cooldown, EMA20 صعودی ۵روزه, squeeze |

تست یک نماد: `GET /strategy/evaluate/BTCUSDT`

## متغیرهای محیطی

نمونه کامل در `.env.example`.

## Docker

```bash
docker compose up --build
```

## امنیت (قبل از Live)

- IP whitelist روی API CoinEx
- غیرفعال کردن برداشت
- شروع با `PAPER_TRADING=true`
- `RISK_PER_TRADE` محافظه‌کارانه (مثلاً ۰.۰۰۵)

## مخزن

https://github.com/mkstatoo/trading-system
