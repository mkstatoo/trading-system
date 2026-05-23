"""اجرای سرور روی پورت تنظیم‌شده در .env (پیش‌فرض 7000).

Windows: run.bat  یا  venv\\Scripts\\python run.py
"""
try:
    import uvicorn
    from app.core.settings import settings
except ModuleNotFoundError as e:
    raise SystemExit(
        "وابستگی‌ها نصب نیست. از venv اجرا کنید:\n"
        "  python -m venv venv\n"
        "  venv\\Scripts\\activate\n"
        "  pip install -r requirements.txt\n"
        "  python run.py\n"
        f"\nخطا: {e}"
    ) from e
if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=False,
    )
