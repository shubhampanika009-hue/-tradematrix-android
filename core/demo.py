import threading
import time


def generate_payloads(secret, ticker="NIFTY", seed=1):
    return [
        {"secret": secret, "type": "bar", "ticker": ticker, "tf": "5", "o": 24000, "h": 24050, "l": 23980, "c": 24030},
        {"secret": secret, "type": "signal", "ticker": ticker, "tf": "5", "action": "BUY", "price": 24030, "sl": 23970, "tp": 24150, "tags": ["OB"]}
    ]


def run_demo(hub):
    def task():
        for p in generate_payloads(hub.cfg.secret):
            hub.handle_payload(p)
            time.sleep(1.0)
    t = threading.Thread(target=task, daemon=True)
    t.start()
    return t
