"""
hub.py - Central event bus and signal router for TradeMatrix.
"""
import queue
from core.logger import log


class Hub:
    def __init__(self, cfg, voice):
        self.cfg = cfg
        self.voice = voice
        self.bus = queue.Queue()

    def emit(self, kind: str, obj):
        try:
            self.bus.put_nowait((kind, obj))
        except Exception:
            log.exception("hub emit failed")

    def handle_payload(self, payload: dict):
        """Handle incoming webhook payload from TradingView/relay."""
        log.info("Received payload: %r", payload)
        self.emit("log", f"Payload received: {payload.get('ticker', 'UNKNOWN')}")
        
        # Basic processing and decision broadcasting demo
        ticker = payload.get("ticker", "NIFTY")
        action = payload.get("action", "BUY")
        price = float(payload.get("price", 0.0))
        
        self.emit("event", type('Event', (), {'kind': 'WEBHOOK', 'side': action, 'ticker': ticker, 'price': price})())
        return 200, "OK"
