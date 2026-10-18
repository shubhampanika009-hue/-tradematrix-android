"""
main.py - TradeMatrix KivyMD app.

Threads:  webhook server (asyncio) / relay poller  ->  Hub  ->  SMC engine + Voice
UI thread: polls hub.bus every 250 ms and updates widgets (Kivy widgets are touched ONLY here).
"""
import os
import queue
import socket

from kivy.base import ExceptionHandler, ExceptionManager
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.lang import Builder
from kivy.utils import platform
from kivymd.app import MDApp
from kivymd.uix.list import TwoLineListItem

from core import demo
from core.config import Config
from core.hub import Hub
from core.logger import log, setup as setup_logging
from core.relay_poller import RelayPoller
from core.voice import Voice
from core.webhook_server import WebhookServer

if platform == "android":
    from android.runnable import run_on_ui_thread
else:
    Window.size = (400, 780)

    def run_on_ui_thread(f):
        return f

GREEN = (0.18, 0.90, 0.55, 1)
RED = (1.0, 0.25, 0.40, 1)
CYAN = (0.0, 1.0, 0.85, 1)
AMBER = (1.0, 0.75, 0.2, 1)

KV = """
MDScreen:
    md_bg_color: 0.02, 0.02, 0.06, 1
    MDBoxLayout:
        orientation: "vertical"
        padding: dp(12)
        spacing: dp(10)

        MDBoxLayout:
            size_hint_y: None
            height: dp(36)
            MDLabel:
                text: "TRADEMATRIX"
                font_style: "H5"
                bold: True
                theme_text_color: "Custom"
                text_color: 0, 1, 0.85, 1
            MDLabel:
                id: status
                text: "starting..."
                halign: "right"
                font_style: "Caption"
                theme_text_color: "Custom"
                text_color: 0.6, 0.65, 0.75, 1

        MDLabel:
            id: url_label
            text: ""
            font_style: "Caption"
            size_hint_y: None
            height: dp(44)
            theme_text_color: "Custom"
            text_color: 0.6, 0.65, 0.75, 1

        MDCard:
            orientation: "vertical"
            padding: dp(14)
            spacing: dp(4)
            size_hint_y: None
            height: dp(250)
            radius: [dp(14)]
            md_bg_color: 0.07, 0.08, 0.14, 1
            MDLabel:
                id: sig_title
                text: "Waiting for signal"
                font_style: "H5"
                bold: True
                size_hint_y: None
                height: dp(34)
                theme_text_color: "Custom"
                text_color: 0.6, 0.65, 0.75, 1
            MDLabel:
                id: sig_levels
                text: ""
                size_hint_y: None
                height: dp(24)
            MDLabel:
                id: sig_meta
                text: ""
                font_style: "Caption"
                size_hint_y: None
                height: dp(20)
                theme_text_color: "Custom"
                text_color: 0.6, 0.65, 0.75, 1
            MDProgressBar:
                id: conf_bar
                value: 0
                color: 0, 1, 0.85, 1
                size_hint_y: None
                height: dp(6)
            MDLabel:
                id: sig_reasons
                text: ""
                font_style: "Caption"
                valign: "top"

        MDBoxLayout:
            size_hint_y: None
            height: dp(48)
            spacing: dp(8)
            MDLabel:
                text: "Voice"
                size_hint_x: None
                width: dp(48)
            MDSwitch:
                id: voice_sw
                active: True
                pos_hint: {"center_y": .5}
                on_active: app.set_voice(self.active)
            MDFlatButton:
                id: lang_btn
                text: "HI"
                on_release: app.toggle_lang()
            MDRaisedButton:
                text: "Test"
                on_release: app.test_voice()
            MDRaisedButton:
                text: "Demo"
                on_release: app.run_demo()

        MDScrollView:
            MDList:
                id: feed
"""


class SafeHandler(ExceptionHandler):
    """An exception inside a Kivy callback is logged and swallowed instead of killing the app."""

    def handle_exception(self, inst):
        log.error("UI exception (app kept alive)", exc_info=inst)
        return ExceptionManager.PASS


def local_ip() -> str:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("10.255.255.255", 1))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


class TradeMatrixApp(MDApp):
    def build(self):
        setup_logging(os.path.join(self.user_data_dir, "logs"))
        ExceptionManager.add_handler(SafeHandler())
        log.info("TradeMatrix starting (platform=%s)", platform)
        self.theme_cls.theme_style = "Dark"
        self.theme_cls.primary_palette = "Cyan"
        self.cfg = Config.load(os.path.join(self.user_data_dir, "config.json"))
        self.voice = Voice(self.cfg.lang, self.cfg.voice_enabled)
        self.hub = Hub(self.cfg, self.voice)
        self.server = None
        self.poller = None
        self._demo = None
        self._ip = "127.0.0.1"
        return Builder.load_string(KV)

    def on_start(self):
        ids = self.root.ids
        self.keep_screen_on()
        self.voice.start()                       # must run on the UI thread (Android TTS)
        ids.voice_sw.active = self.cfg.voice_enabled
        ids.lang_btn.text = self.cfg.lang.upper()
        self._ip = local_ip()

        self.server = WebhookServer(self.cfg.host, self.cfg.port, self.hub.handle_payload,
                                    on_status=lambda m: self.hub.emit("status", m))
        self.server.start()
        if self.cfg.relay_url:
            self.poller = RelayPoller(self.cfg.relay_url, self.cfg.relay_key,
                                      self.hub.handle_payload,
                                      notify=lambda m: self.hub.emit("log", m))
            self.poller.start()
        self.refresh_info()
        Clock.schedule_interval(self.pump, 0.25)

    def on_pause(self):
        return True            # Android: keep the process alive instead of restarting on resume

    def on_resume(self):
        self.keep_screen_on()
        self.refresh_info()

    def on_stop(self):
        log.info("TradeMatrix stopping")
        for part in (self.server, self.poller):
            try:
                if part:
                    part.stop()
            except Exception:
                log.exception("stop failed")
        self.voice.stop()

    @run_on_ui_thread
    def keep_screen_on(self):
        if platform != "android":
            return
        try:
            from jnius import autoclass
            act = autoclass("org.kivy.android.PythonActivity").mActivity
            flags = autoclass("android.view.WindowManager$LayoutParams")
            act.getWindow().addFlags(flags.FLAG_KEEP_SCREEN_ON)
        except Exception:
            log.exception("keep_screen_on failed")

    def refresh_info(self):
        if self.cfg.relay_url:
            where = f"relay: {self.cfg.relay_url}"
        else:
            port = self.server.port if self.server else self.cfg.port
            where = f"http://{self._ip}:{port}/webhook"
        self.root.ids.url_label.text = f"{where}\nsecret: {self.cfg.secret}"

    # ---- UI <- hub.bus ----------------------------------------------------
    def pump(self, dt):
        for _ in range(30):                      # bounded work per frame keeps the UI smooth
            try:
                kind, obj = self.hub.bus.get_nowait()
            except queue.Empty:
                return
            try:
                if kind == "decision":
                    self.show_decision(obj)
                elif kind == "event":
                    self.add_feed(f"{obj.kind} ({obj.side})  {obj.ticker}", f"price {obj.price:g}")
                elif kind == "status":
                    self.root.ids.status.text = str(obj)[:40]
                    self.refresh_info()
                else:
                    self.add_feed("log", str(obj))
            except Exception:
                log.exception("pump item failed: %s", kind)

    def show_decision(self, d):
        ids = self.root.ids
        color = GREEN if d.action == "BUY" else RED
        ids.sig_title.text = f"{d.action}  {d.ticker}"
        ids.sig_title.text_color = color
        ids.sig_levels.text = f"Entry {d.entry:g}   SL {d.sl:g}   TP {d.tp:g}   R:R {d.rr:g}"
        ids.sig_meta.text = (f"{d.verdict} | setup {d.setup} | confidence {d.confidence}% | "
                             f"qty {d.qty} | risk {d.risk_cash:g}")
        ids.conf_bar.value = d.confidence
        ids.conf_bar.color = GREEN if d.confidence >= 70 else AMBER if d.confidence >= 50 else RED
        ids.sig_reasons.text = "\n".join(["+ " + r for r in d.reasons] + ["! " + r for r in d.risks])
        self.add_feed(f"{d.action} {d.ticker}  {d.confidence}%  {d.verdict}",
                      f"entry {d.entry:g}  sl {d.sl:g}  tp {d.tp:g}")

    def add_feed(self, title: str, subtitle: str):
        feed = self.root.ids.feed
        feed.add_widget(TwoLineListItem(text=title, secondary_text=subtitle),
                        index=len(feed.children))          # newest on top
        if len(feed.children) > 60:
            feed.remove_widget(feed.children[0])

    # ---- controls ---------------------------------------------------------
    def set_voice(self, active: bool):
        self.voice.enabled = self.cfg.voice_enabled = bool(active)
        self.cfg.save()

    def toggle_lang(self):
        want = "en" if self.cfg.lang == "hi" else "hi"
        got = self.voice.set_lang(want)
        self.cfg.lang = got
        self.cfg.save()
        self.root.ids.lang_btn.text = got.upper()
        if got != want:
            self.add_feed("Hindi voice not installed", "Install it in Android TTS settings")

    def test_voice(self):
        text = ("ट्रेडमैट्रिक्स वॉइस चालू है।" if self.voice.lang == "hi"
                else "Trade
