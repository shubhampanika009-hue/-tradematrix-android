import threading
from kivy.utils import platform
from .logger import log


class Voice:
    def __init__(self, lang="hi", enabled=True):
        self.lang = lang
        self.enabled = enabled
        self._tts = None
        self._lock = threading.Lock()

    def start(self):
        if platform != "android":
            return
        try:
            from jnius import autoclass
            PythonActivity = autoclass("org.kivy.android.PythonActivity")
            Locale = autoclass("java.util.Locale")
            TextToSpeech = autoclass("android.speech.tts.TextToSpeech")

            def init_tts(status):
                pass  # Initialization callback stub

            self._tts = TextToSpeech(PythonActivity.mActivity, init_tts)
            if self.lang == "hi":
                self._tts.setLanguage(Locale("hi", "IN"))
            else:
                self._tts.setLanguage(Locale.US)
        except Exception:
            log.exception("TTS initialization failed")

    def stop(self):
        if self._tts and platform == "android":
            try:
                self._tts.shutdown()
            except Exception:
                pass

    def set_lang(self, lang: str) -> str:
        self.lang = lang
        return lang

    def speak(self, text: str, flush=False):
        if not self.enabled or not text:
            return
        log.info("Voice speak: %s", text)
        if platform == "android" and self._tts:
            try:
                from android.runnable import run_on_ui_thread
                @run_on_ui_thread
                def _do():
                    QUEUE_FLUSH = 1
                    QUEUE_ADD = 0
                    qmode = QUEUE_FLUSH if flush else QUEUE_ADD
                    self._tts.speak(text, qmode, None, "tradematrix_tts")
                _do()
            except Exception:
                log.exception("TTS speak failed")

    def say_event(self, e):
        txt = f"Structure event {e.kind} on {e.ticker}"
        self.speak(txt)

    def say_decision(self, d):
        txt = f"{d.action} signal confirmed for {d.ticker} at entry {d.entry}"
        if self.lang == "hi":
            txt = f"{d.ticker} पर {d.action} सिग्नल कन्फर्म है। एंट्री {d.entry}"
        self.speak(txt, flush=True)
