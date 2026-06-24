from __future__ import annotations
import time
import base64
import ctypes
import datetime as dt
import json
import os
import threading
from pathlib import Path

from PySide6.QtCore import QEvent, QObject, QPoint, QRect, Qt, QTimer, QUrl, Signal, Slot
from PySide6.QtGui import QFont, QSurfaceFormat
from PySide6.QtWebChannel import QWebChannel
from PySide6.QtWebEngineCore import QWebEngineSettings
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWidgets import QApplication, QHBoxLayout, QLabel, QMainWindow, QMenu, QVBoxLayout, QWidget

try:
    import pyttsx3
except Exception:  # pragma: no cover - optional dependency
    pyttsx3 = None

try:
    import vlc
except Exception:  # pragma: no cover - optional dependency
    vlc = None

try:
    import speech_recognition as sr
except Exception:  # pragma: no cover - optional dependency
    sr = None


APP_DIR = Path(__file__).resolve().parent
COUNTDOWN_TARGET = dt.datetime(2025, 7, 11, 0, 0, 0)
POSE_FILES = ["pose.json", "pose1.json", "pose2.json"]
MOTIVATION_FILE = APP_DIR / "勵志小語.txt"

GWL_STYLE = -16
WS_CAPTION = 0x00C00000
WS_THICKFRAME = 0x00040000
GCL_STYLE = -26
CS_DROPSHADOW = 0x00020000


class AudioManager:
    def __init__(self) -> None:
        self.engine = None
        self.voices = []
        self.voice_index = 0
        self._speak_lock = threading.Lock()
        self._speaking = threading.Event()
        self.player = None

        if pyttsx3 is not None:
            try:
                self.engine = pyttsx3.init()
                self.voices = list(self.engine.getProperty("voices") or [])
                if self.voices:
                    self.engine.setProperty("voice", self.voices[0].id)
            except Exception:
                self.engine = None
                self.voices = []

    def speak(self, text: str) -> None:
        if not text or self.engine is None:
            return

        def _run() -> None:
            with self._speak_lock:
                try:
                    self._speaking.set()
                    self.engine.say(text)
                    self.engine.runAndWait()
                    self.engine.stop()
                except Exception:
                    pass
                finally:
                    self._speaking.clear()

        threading.Thread(target=_run, daemon=True).start()

    def is_speaking(self) -> bool:
        return self._speaking.is_set()

    def switch_voice(self) -> int:
        if self.engine is None or not self.voices:
            return 0
        self.voice_index = (self.voice_index + 1) % len(self.voices)
        try:
            self.engine.setProperty("voice", self.voices[self.voice_index].id)
        except Exception:
            pass
        return self.voice_index

    def play(self, path: Path) -> bool:
        if vlc is None:
            return False
        try:
            if self.player is not None:
                self.player.stop()
            self.player = vlc.MediaPlayer(str(path))
            self.player.play()
            return True
        except Exception:
            return False

    def pause(self) -> bool:
        if self.player is None:
            return False
        try:
            if self.player.can_pause():
                self.player.pause()
            return True
        except Exception:
            return False

    def stop(self) -> bool:
        if self.player is None:
            return False
        try:
            self.player.stop()
            return True
        except Exception:
            return False


class VRMHost(QObject):
    def __init__(self, window: "TransparentWindow"):
        super().__init__()
        self.window = window

    @Slot(int, int)
    def dragWindowBy(self, dx: int, dy: int) -> None:
        pos = self.window.pos()
        self.window.move(pos.x() + dx, pos.y() + dy)

    @Slot(int, int)
    def fitWindowToModel(self, width: int, height: int) -> None:
        self.window.resize(max(100, width), max(100, height))

    @Slot(str, result=str)
    def readTextFile(self, filename: str) -> str:
        path = APP_DIR / filename
        try:
            if path.exists():
                return path.read_text(encoding="utf-8")
        except Exception as exc:
            print(f"Error reading text file {filename}: {exc}")
        return ""

    @Slot(str, result=str)
    def readBinaryFile(self, filename: str) -> str:
        path = APP_DIR / filename
        try:
            if path.exists():
                return base64.b64encode(path.read_bytes()).decode("utf-8")
        except Exception as exc:
            print(f"Error reading binary file {filename}: {exc}")
        return ""

    @Slot()
    def closeWindow(self) -> None:
        QApplication.quit()

    @Slot()
    def triggerNextPose(self) -> None:
        self.window.cyclePose()

    @Slot(str)
    def updatePose(self, json_data: str) -> None:
        if isinstance(json_data, str) and not json_data.startswith("{"):
            path = APP_DIR / json_data
            if path.exists():
                try:
                    json_data = path.read_text(encoding="utf-8")
                except Exception as exc:
                    print(f"Error reading pose file {path}: {exc}")
                    return

        safe_content = json.dumps(json_data)
        js = (
            "if(window.applyPoseData) { "
            f"window.applyPoseData({safe_content}); 'OK'; "
            "} else { 'ERROR_JS_NOT_READY'; }"
        )
        self.window.browser.page().runJavaScript(js)


class VoiceBridge(QObject):
    recognized = Signal(str)
    status = Signal(str)
    error = Signal(str)


class TransparentWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.pose_index = -1
        self.pose_files = [p for p in POSE_FILES if (APP_DIR / p).exists()]
        self.audio = AudioManager()
        self.voice_bridge = VoiceBridge()
        self.voice_bridge.recognized.connect(self.handle_voice_text)
        self.voice_bridge.status.connect(lambda text: self.show_message(text, duration_ms=2000, speak=False))
        self.voice_bridge.error.connect(lambda text: print(text))
        self.voice_stop_event = threading.Event()
        self.voice_pause_event = threading.Event()
        self.voice_thread: threading.Thread | None = None
        self.quotes = self._load_quotes()
        self.quote_index = 0

        self.setWindowTitle("桌面小幫手 VRM 版")
        self.setWindowFlags(
            Qt.FramelessWindowHint
            | Qt.WindowStaysOnTopHint
            | Qt.Tool
            | Qt.NoDropShadowWindowHint
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_NoSystemBackground)

        self.root = QWidget(self)
        self.setCentralWidget(self.root)

        layout = QHBoxLayout(self.root)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.browser = QWebEngineView(self.root)
        self.browser.setStyleSheet("background: transparent; border: none;")
        self.browser.setAttribute(Qt.WA_TranslucentBackground)
        self.browser.page().setBackgroundColor(Qt.transparent)
        layout.addWidget(self.browser)
        self.browser.lower()

        self.overlay = QWidget(self.root)
        self.overlay.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.overlay.setStyleSheet("background: transparent;")
        self.overlay.raise_()

        self.text_panel = QWidget(self.overlay)
        self.text_panel.setStyleSheet(
            "background: transparent;"
            "border: none;"
            "border-radius: 14px;"
        )

        self.panel_layout = QVBoxLayout(self.text_panel)
        self.panel_layout.setContentsMargins(14, 14, 14, 14)
        self.panel_layout.setSpacing(12)

        self.countdown_label = QLabel(self.text_panel)
        self.countdown_label.setStyleSheet(
            "color: #fff3f3; background: rgba(180, 20, 20, 180);"
            "border-radius: 10px; padding: 8px 12px; font-size: 18px;"
            "font-weight: 700;"
        )
        self.countdown_label.setFont(QFont("Microsoft JhengHei", 18, QFont.Bold))
        self.countdown_label.setTextInteractionFlags(Qt.NoTextInteraction)
        self.countdown_label.setWordWrap(True)
        self.panel_layout.addWidget(self.countdown_label)

        self.message_label = QLabel(self.text_panel)
        self.message_label.setStyleSheet(
            "color: #222; background: rgba(255, 248, 255, 220);"
            "border-radius: 12px; padding: 10px 14px; font-size: 22px;"
        )
        self.message_label.setFont(QFont("Microsoft JhengHei", 22))
        self.message_label.setAlignment(Qt.AlignCenter)
        self.message_label.setWordWrap(True)
        self.panel_layout.addWidget(self.message_label)
        self.message_label.hide()

        self.panel_layout.addStretch(1)

        self.hint_label = QLabel(self.text_panel)
        self.hint_label.setStyleSheet(
            "color: #f5f5f5; background: rgba(0, 0, 0, 120);"
            "border-radius: 8px; padding: 5px 8px; font-size: 12px;"
        )
        self.hint_label.setFont(QFont("Segoe UI", 12))
        self.hint_label.setText("左鍵拖曳移動，雙擊換姿勢，右鍵開選單")
        self.hint_label.setWordWrap(True)
        self.panel_layout.addWidget(self.hint_label)

        self.channel = QWebChannel(self.browser.page())
        self.host_obj = VRMHost(self)
        self.channel.registerObject("vrmHost", self.host_obj)
        self.browser.page().setWebChannel(self.channel)

        settings = self.browser.settings()
        settings.setAttribute(QWebEngineSettings.LocalContentCanAccessRemoteUrls, True)
        settings.setAttribute(QWebEngineSettings.LocalContentCanAccessFileUrls, True)
        settings.setAttribute(QWebEngineSettings.ShowScrollBars, False)
        settings.setAttribute(QWebEngineSettings.JavascriptEnabled, True)

        self.browser.installEventFilter(self)
        self.root.installEventFilter(self)

        index_path = APP_DIR / "index.html"
        self.browser.setUrl(QUrl.fromLocalFile(str(index_path)))

        self.countdown_timer = QTimer(self)
        self.countdown_timer.timeout.connect(self.update_countdown)
        self.countdown_timer.start(1000)
        self.update_countdown()

        self.message_clear_timer = QTimer(self)
        self.message_clear_timer.setSingleShot(True)
        self.message_clear_timer.timeout.connect(self.hide_message)

        self.resize(520, 820)
        QTimer.singleShot(0, self.start_voice_input)

    def _load_quotes(self) -> list[str]:
        try:
            if MOTIVATION_FILE.exists():
                return [line.strip() for line in MOTIVATION_FILE.read_text(encoding="utf-8").splitlines() if line.strip()]
        except Exception as exc:
            print(f"Error loading quotes: {exc}")
        return ["今天也一起加油吧！"]

    def resizeEvent(self, event):  # noqa: N802
        super().resizeEvent(event)
        self.layout_overlays()

    def layout_overlays(self) -> None:
        self.overlay.setGeometry(self.rect())
        panel_width = min(max(360, self.width() // 3 + 100), self.width())
        panel_x = max(0, self.width() - panel_width + 150)
        self.text_panel.setGeometry(
            panel_x,
            0,
            panel_width,
            self.height(),
        )
        content_width = max(200, panel_width - 28)
        self.countdown_label.setMaximumWidth(content_width)
        self.message_label.setMaximumWidth(content_width)
        self.hint_label.setMaximumWidth(content_width)
        self.countdown_label.adjustSize()
        self.message_label.adjustSize()
        self.hint_label.adjustSize()
        self.text_panel.raise_()
        self.countdown_label.raise_()
        self.message_label.raise_()
        self.hint_label.raise_()

    def showEvent(self, event):  # noqa: N802
        super().showEvent(event)
        self.apply_native_fixes()

    def apply_native_fixes(self) -> None:
        if os.name != "nt":
            return
        hwnd = int(self.winId())
        user32 = ctypes.windll.user32
        class_style = user32.GetClassLongW(hwnd, GCL_STYLE)
        if class_style & CS_DROPSHADOW:
            user32.SetClassLongW(hwnd, GCL_STYLE, class_style & ~CS_DROPSHADOW)
        style = user32.GetWindowLongW(hwnd, GWL_STYLE)
        style &= ~(WS_CAPTION | WS_THICKFRAME)
        user32.SetWindowLongW(hwnd, GWL_STYLE, style)
        user32.SetWindowPos(hwnd, 0, 0, 0, 0, 0, 0x0027)

    def eventFilter(self, obj, event):  # noqa: N802
        if event.type() == QEvent.MouseButtonDblClick and event.button() == Qt.LeftButton:
            self.cyclePose()
            return True
        if event.type() == QEvent.ContextMenu:
            self.show_context_menu(event.globalPos())
            return True
        return super().eventFilter(obj, event)

    def show_context_menu(self, global_pos: QPoint) -> None:
        menu = QMenu(self)
        if self.voice_thread is None or not self.voice_thread.is_alive():
            menu.addAction("開始語音監聽", self.start_voice_input)
        else:
            menu.addAction("停止語音監聽", self.stop_voice_input)
        menu.addSeparator()
        menu.addAction("勵志小語", self.next_quote)
        menu.addAction("切換聲音", self.switch_voice)
        menu.addSeparator()
        menu.addAction("暫停音樂", self.pause_music)
        menu.addAction("繼續音樂", self.resume_music)
        menu.addAction("結束音樂", self.stop_music)
        menu.addSeparator()
        menu.addAction("退出", QApplication.quit)
        menu.exec(global_pos)

    def update_countdown(self) -> None:
        text = self._countdown_text()
        self.countdown_label.setText(text)
        self.countdown_label.adjustSize()

    def next_quote(self) -> None:
        if not self.quotes:
            return
        quote = self.quotes[self.quote_index % len(self.quotes)]
        self.quote_index += 1
        self.show_message(quote)

    def show_message(self, text: str, duration_ms: int = 5000, speak: bool = True) -> None:
        self.message_label.setText(text)
        self.message_label.adjustSize()
        self.message_label.show()
        self.layout_overlays()
        self.message_clear_timer.start(duration_ms)
        if speak and text:
            self.audio.speak(text)

    def hide_message(self) -> None:
        self.message_label.hide()

    def switch_voice(self) -> None:
        idx = self.audio.switch_voice()
        self.show_message(f"切換聲音... #{idx + 1}", duration_ms=2000)

    def _countdown_text(self) -> str:
        now = dt.datetime.now()
        diff = COUNTDOWN_TARGET - now
        if diff.total_seconds() >= 0:
            days = diff.days
            hours, remainder = divmod(diff.seconds, 3600)
            minutes, seconds = divmod(remainder, 60)
            return f"分科倒數:\n{days}天 {hours}時 {minutes}分 {seconds}秒"
        overdue = now - COUNTDOWN_TARGET
        return f"分科倒數:\n已超過 {overdue.days} 天"

    def _find_music_file(self, keyword: str) -> Path | None:
        candidates: list[Path] = []
        for folder in [APP_DIR, APP_DIR / "mp3"]:
            if not folder.exists():
                continue
            for path in folder.glob("*.mp3"):
                if keyword in path.stem:
                    candidates.append(path)
        return candidates[0] if candidates else None

    def play_music(self, keyword: str) -> None:
        path = self._find_music_file(keyword)
        if path is None:
            self.show_message(f"找不到音樂：{keyword}", duration_ms=2500)
            return
        if self.audio.play(path):
            self.show_message(f"播放：{path.stem}", duration_ms=2000)
        else:
            self.show_message("目前沒有可用的 VLC 播放器", duration_ms=2500)

    def pause_music(self) -> None:
        if self.audio.pause():
            self.show_message("暫停音樂", duration_ms=1500, speak=False)

    def resume_music(self) -> None:
        if self.audio.player is not None:
            try:
                self.audio.player.play()
                self.show_message("繼續音樂", duration_ms=1500, speak=False)
            except Exception:
                pass

    def stop_music(self) -> None:
        if self.audio.stop():
            self.show_message("結束音樂", duration_ms=1500, speak=False)

    def handle_voice_text(self, text: str) -> None:
        text = (text or "").strip()
        if not text:
            return

        print(f"語音辨識：{text}")
        self.voice_pause_event.set()
        try:
            if "你好" in text:
                self.show_message("你好，有什麼需要我幫忙？", duration_ms=3500)
                return
            if "勵志" in text or "小語" in text:
                self.next_quote()
                return
            if "切換聲音" in text:
                self.switch_voice()
                return
            if "暫停音樂" in text:
                self.pause_music()
                return
            if "繼續音樂" in text:
                self.resume_music()
                return
            if "結束音樂" in text or "停止音樂" in text:
                self.stop_music()
                return
            if "播放" in text:
                keyword = text.split("播放", 1)[1].strip()
                if keyword:
                    self.play_music(keyword)
                    return
            if "倒數" in text:
                self.show_message(self._countdown_text(), duration_ms=4500, speak=False)
                return
            if "退出" in text or "關閉" in text:
                QApplication.quit()
                return

            self.show_message("不清楚您的問題", duration_ms=2500)
        finally:
            QTimer.singleShot(1200, self.clear_voice_pause)

    def clear_voice_pause(self) -> None:
        self.voice_pause_event.clear()

    def start_voice_input(self) -> None:
        if sr is None:
            self.show_message("語音辨識模組未安裝", duration_ms=2500, speak=False)
            return
        if self.voice_thread is not None and self.voice_thread.is_alive():
            return
        self.voice_stop_event.clear()
        self.voice_pause_event.clear()
        self.voice_thread = threading.Thread(target=self._voice_loop, daemon=True)
        self.voice_thread.start()
        self.show_message("語音監聽已啟動", duration_ms=1800, speak=False)

    def stop_voice_input(self) -> None:
        self.voice_stop_event.set()
        self.voice_pause_event.set()
        self.show_message("語音監聽已停止", duration_ms=1800, speak=False)

    def _voice_loop(self) -> None:
        if sr is None:
            return

        recognizer = sr.Recognizer()
        recognizer.pause_threshold = 0.5
        recognizer.dynamic_energy_threshold = True

        try:
            with sr.Microphone() as source:
                self.voice_bridge.status.emit("正在調整環境噪音...")
                recognizer.adjust_for_ambient_noise(source, duration=0.5)
                self.voice_bridge.status.emit("請開始說話...")

                while not self.voice_stop_event.is_set():
                    if self.voice_pause_event.is_set() or self.audio.is_speaking():
                        time.sleep(0.1)
                        continue

                    try:
                        audio = recognizer.listen(source, timeout=5, phrase_time_limit=10)
                    except sr.WaitTimeoutError:
                        continue

                    try:
                        result = recognizer.recognize_google(audio, language="zh-TW")
                    except sr.UnknownValueError:
                        continue
                    except sr.RequestError as exc:
                        self.voice_bridge.error.emit(f"語音辨識服務錯誤：{exc}")
                        continue

                    self.voice_pause_event.set()
                    self.voice_bridge.recognized.emit(result)
                    while (self.audio.is_speaking() or self.voice_pause_event.is_set()) and not self.voice_stop_event.is_set():
                        time.sleep(0.1)
        except Exception as exc:
            self.voice_bridge.error.emit(f"語音監聽失敗：{exc}")

    def cyclePose(self) -> None:
        if not self.pose_files:
            return
        self.pose_index = (self.pose_index + 1) % len(self.pose_files)
        target_pose = self.pose_files[self.pose_index]
        print(f"Switching to pose: {target_pose}")
        self.host_obj.updatePose(target_pose)

    def closeEvent(self, event):  # noqa: N802
        self.stop_voice_input()
        super().closeEvent(event)


def main() -> int:
    os.environ.setdefault("QTWEBENGINE_WIDGETS_LOG_LEVEL", "1")

    fmt = QSurfaceFormat()
    fmt.setAlphaBufferSize(8)
    fmt.setSamples(4)
    QSurfaceFormat.setDefaultFormat(fmt)

    app = QApplication.instance() or QApplication([])
    app.setStyle("Fusion")

    window = TransparentWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
