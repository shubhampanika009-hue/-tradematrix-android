from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class BarAlert:
    ticker: str
    tf: str
    o: float
    h: float
    l: float
    c: float
    time: Optional[float] = None


@dataclass
class SignalAlert:
    ticker: str
    tf: str
    action: str  # BUY / SELL
    price: float
    sl: Optional[float] = None
    tp: Optional[float] = None
    tags: List[str] = field(default_factory=list)
    time: Optional[float] = None


@dataclass
class StructureEvent:
    ticker: str
    kind: str  # CHOCH, MSB, SWEEP, OB
    side: str  # bull, bear
    price: float
    time: float


@dataclass
class Decision:
    ticker: str
    action: str  # BUY / SELL
    entry: float
    sl: float
    tp: float
    rr: float
    confidence: int
    verdict: str  # TAKE, CAUTION, SKIP
    setup: str
    qty: int
    risk_cash: float
    reasons: List[str] = field(default_factory=list)
    risks: List[str] = field(default_factory=list)


def parse_alert(d: dict):
    t = d.get("type")
    if t == "bar":
        return BarAlert(
            ticker=str(d.get("ticker", "UNKNOWN")),
            tf=str(d.get("tf", "1")),
            o=float(d["o"]), h=float(d["h"]), l=float(d["l"]), c=float(d["c"]),
            time=d.get("time")
        )
    elif t == "signal":
        return SignalAlert(
            ticker=str(d.get("ticker", "UNKNOWN")),
            tf=str(d.get("tf", "1")),
            action=str(d["action"]).upper(),
            price=float(d["price"]),
            sl=float(d["sl"]) if d.get("sl") is not None else None,
            tp=float(d["tp"]) if d.get("tp") is not None else None,
            tags=list(d.get("tags", [])),
            time=d.get("time")
        )
    raise ValueError(f"unknown alert type: {t}")
