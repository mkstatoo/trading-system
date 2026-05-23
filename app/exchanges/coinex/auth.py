import time
import hmac
import hashlib


class CoinExAuth:

    def __init__(self, access_id: str, secret_key: str):
        self.access_id = access_id
        self.secret_key = secret_key

    def timestamp(self) -> str:
        return str(int(time.time() * 1000))

    def sign(self, method: str, path: str, body: str, timestamp: str) -> str:
        payload = f"{method}{path}{body}{timestamp}"
        return hmac.new(
            self.secret_key.encode(),
            payload.encode(),
            hashlib.sha256,
        ).hexdigest().lower()

    def headers(self, method: str, path: str, body: str = "") -> dict:
        ts = self.timestamp()
        return {
            "X-COINEX-KEY": self.access_id,
            "X-COINEX-SIGN": self.sign(method, path, body, ts),
            "X-COINEX-TIMESTAMP": ts,
            "Content-Type": "application/json",
        }
