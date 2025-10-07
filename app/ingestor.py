import time, random
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

SESSION = None

def _session():
    global SESSION
    if SESSION is None:
        s = requests.Session()
        retry = Retry(
            total=5,
            connect=3,
            read=3,
            backoff_factor=0.7,               # exponencial (0.7, 1.4, 2.8, …)
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET", "POST"],
            respect_retry_after_header=True,
        )
        s.headers.update({
            "User-Agent": "CryptoPulse/1.0 (+https://github.com/<seu-usuario>/<repo>)"
        })
        s.mount("https://", HTTPAdapter(max_retries=retry))
        s.mount("http://", HTTPAdapter(max_retries=retry))
        SESSION = s
    return SESSION

def fetch_btc_price(timeout=12):
    url = "https://api.coingecko.com/api/v3/simple/price"
    params = {"ids": "bitcoin", "vs_currencies": "usd"}
    s = _session()
    r = s.get(url, params=params, timeout=timeout)
    r.raise_for_status()
    data = r.json()
    price = float(data["bitcoin"]["usd"])
    return price

def polite_sleep(delay_s: float, jitter: float = 0.25):
    # Pequeno jitter para evitar sincronizar com janelas de rate limit
    time.sleep(max(0, delay_s + random.uniform(-jitter, jitter)))
