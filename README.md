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
uvicorn app.main:app --reload
```

- API: http://127.0.0.1:8000  
- مستندات: http://127.0.0.1:8000/docs  

## اندپوینت‌های مهم

| مسیر | توضیح |
|------|--------|
| `GET /health` | وضعیت سیستم و موتور معاملات |
| `GET /status` | آمار اسکن و ترید |
| `GET /paper/balance` | موجودی Paper |
| `GET /trading/positions` | پوزیشن‌های باز |
| `POST /trading/order` | سفارش دستی Paper |

## استراتژی Bull Hunter

سیگنال **خرید** وقتی قیمت آخر بیش از `open` به اندازه `BULL_HUNTER_MOMENTUM_PCT` درصد رشد کند.  
حجم پوزیشن: `INITIAL_BALANCE × RISK_PER_TRADE / last_price`.

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
