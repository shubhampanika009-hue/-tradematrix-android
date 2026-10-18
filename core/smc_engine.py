import time
from .models import BarAlert, Decision, SignalAlert, StructureEvent


class SMCEngine:
    def __init__(self, cfg):
        self.cfg = cfg
        self.history = []
        self.last_signal_time = 0

    def process(self, alert):
        events = []
        decision = None

        if isinstance(alert, BarAlert):
            self.history.append(alert)
            if len(self.history) > 200:
                self.history.pop(0)
            # Simple structure detection simulation for demo/engine flow
            if len(self.history) >= 3:
                prev, curr = self.history[-2], self.history[-1]
                if curr.c > prev.h:
                    events.append(StructureEvent(curr.ticker, "CHOCH", "bull", curr.c, curr.time or time.time()))

        elif isinstance(alert, SignalAlert):
            now = time.time()
            if now - self.last_signal_time < 15:
                return events, None  # Rate limit duplicate signals
            self.last_signal_time = now

            entry = alert.price
            sl = alert.sl or (entry * 0.99 if alert.action == "BUY" else entry * 1.01)
            tp = alert.tp or (entry * 1.02 if alert.action == "BUY" else entry * 0.98)
            risk = abs(entry - sl)
            reward = abs(tp - entry)
            rr = reward / risk if risk > 0 else 1.0

            conf = 65
            verdict = "CAUTION"
            if rr >= 2.0:
                conf += 10
                verdict = "TAKE"

            decision = Decision(
                ticker=alert.ticker,
                action=alert.action,
                entry=entry,
                sl=sl,
                tp=tp,
                rr=round(rr, 2),
                confidence=conf,
                verdict=verdict,
                setup="OrderBlock + CHOCH",
                qty=1,
                risk_cash=100.0,
                reasons=["Valid structure sweep", f"R:R ratio is {round(rr, 2)}"],
                risks=["Monitor market volatility"]
            )

        return events, decision
