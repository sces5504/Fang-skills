"""Native screen capture utility + public Quartz input/window APIs only."""
import subprocess
import tempfile
import threading
import time
import random
from pathlib import Path
import cv2
from .config import KEYS
from .capture import NativeCapture, CaptureError


def api():
    import Quartz
    import AppKit
    return Quartz, AppKit


def accessibility():
    import ApplicationServices
    return ApplicationServices


def windows(include_hidden=False):
    q, _ = api()
    result = []
    scope = q.kCGWindowListOptionAll if include_hidden else q.kCGWindowListOptionOnScreenOnly
    listing = q.CGWindowListCopyWindowInfo(scope | q.kCGWindowListExcludeDesktopElements, 0)
    if listing is None:
        raise RuntimeError('系統無法讀取視窗清單，請確認此版本的螢幕錄製權限並重新開啟工具')
    for w in listing:
        b = w['kCGWindowBounds']
        if w.get('kCGWindowLayer', 0) == 0 and b['Width'] >= 300 and b['Height'] >= 200:
            result.append(dict(id=int(w['kCGWindowNumber']), pid=int(w['kCGWindowOwnerPID']),
                               name=f"{w.get('kCGWindowOwnerName', '')} — {w.get('kCGWindowName', '')}",
                               bounds=tuple(float(b[k]) for k in ('X', 'Y', 'Width', 'Height'))))
    return result


def foreground_window(expected_bundle=None):
    import os
    _, app = api()
    front = app.NSWorkspace.sharedWorkspace().frontmostApplication()
    if front is None or int(front.processIdentifier()) == os.getpid():
        raise RuntimeError('尚未切回遊戲，請再試一次並在倒數內切換至 NTE')
    if expected_bundle and str(front.bundleIdentifier()) != expected_bundle:
        raise RuntimeError('請切回 NTE，現在前景不是指定的遊戲')
    pid = int(front.processIdentifier())
    candidates = [w for w in windows() if w['pid'] == pid]
    if not candidates:
        raise RuntimeError('目前前景 App 沒有可擷取的遊戲視窗；請確認螢幕錄製權限後重開工具')
    # Prefer the main fullscreen surface over smaller utility windows.
    return max(candidates, key=lambda w: w['bounds'][2] * w['bounds'][3])


def resolve_game_window(config, stop, timeout=12.0):
    """Rebind each run by application identity, never by a persisted window ID.

    Wait for the fullscreen Space transition to settle before locking geometry.
    No input is emitted during acquisition.
    """
    deadline = time.monotonic() + timeout
    previous, stable = None, 0
    reason = '尚未找到前景 NTE'
    while time.monotonic() < deadline:
        if stop.is_set():
            raise InterruptedError('已停止')
        try:
            window = foreground_window(config.get('target_bundle_id', 'com.hottagames.nte'))
            identity = (window['id'], window['pid'], window['bounds'])
            stable = stable + 1 if identity == previous else 1
            previous = identity
            if stable >= 4:
                return window
        except RuntimeError as exc:
            reason = str(exc)
            previous, stable = None, 0
        if stop.wait(.3):
            raise InterruptedError('已停止')
    raise RuntimeError('等待 NTE 全螢幕穩定逾時：' + reason)


def permissions(request=False):
    q, _ = api()
    capture = bool(q.CGPreflightScreenCaptureAccess())
    access = bool(accessibility().AXIsProcessTrusted())
    if request:
        if not capture:
            q.CGRequestScreenCaptureAccess()
        if not access:
            accessibility().AXIsProcessTrustedWithOptions({accessibility().kAXTrustedCheckOptionPrompt: True})
    return capture, access


class GeometryChanged(RuntimeError):
    pass


class MacSession:
    def __init__(self, window_id, stop=None):
        self.native_capture = None
        self.capture_backend = "ScreenCaptureKit"
        self.capture_warning = None
        self.click_jitter_points = 1.0
        self.time_jitter_seconds = .004
        self.window_id = window_id
        self.stop_event = stop or threading.Event()
        candidates = [w for w in windows() if w['id'] == window_id]
        if not candidates:
            raise RuntimeError('找不到選取的視窗；請重新選擇')
        self.window = candidates[0]

    def guard(self, input_action=False, allow_resize=False):
        if self.stop_event.is_set():
            raise InterruptedError('已停止')
        q, app = api()
        current = next((w for w in windows() if w['id'] == self.window_id), None)
        if current is None or current['pid'] != self.window['pid']:
            raise RuntimeError('遊戲視窗已關閉或被替換')
        front = app.NSWorkspace.sharedWorkspace().frontmostApplication()
        if front is None or int(front.processIdentifier()) != current['pid']:
            raise RuntimeError('遊戲不在前景；已停止')
        # Also reject another normal window above this one, even from the same app.
        listing = q.CGWindowListCopyWindowInfo(q.kCGWindowListOptionOnScreenOnly | q.kCGWindowListExcludeDesktopElements, 0)
        x, y, width, height = current['bounds']
        for w in listing:
            if int(w['kCGWindowNumber']) == self.window_id:
                break
            b = w['kCGWindowBounds']
            if float(w.get('kCGWindowAlpha', 1)) == 0:
                continue
            if (b['X'] < x + width and b['X'] + b['Width'] > x and
                    b['Y'] < y + height and b['Y'] + b['Height'] > y):
                raise RuntimeError('其他視窗／浮動面板遮住遊戲；已停止')
        # Top-left of the game's window is an emergency stop corner.
        loc = q.CGEventGetLocation(q.CGEventCreate(None))
        if abs(loc.x - x) < 10 and abs(loc.y - y) < 10:
            raise InterruptedError('滑鼠移至視窗左上角，緊急停止')
        if current['bounds'] != self.window['bounds']:
            if not allow_resize:
                raise GeometryChanged(f"視窗已移動或縮放：{self.window['bounds']} → {current['bounds']}，請重新擷取")
            self.window = current
        if input_action and not accessibility().AXIsProcessTrusted():
            raise RuntimeError('尚未授予輔助使用權限')

    def capture(self):
        for attempt in range(3):
            try:
                return self._capture_once()
            except GeometryChanged:
                if self.stop_event.wait(.2):
                    raise InterruptedError('已停止')
        raise RuntimeError('視窗尺寸持續變動，無法取得穩定畫面')

    def _capture_once(self):
        self.guard(allow_resize=True)
        x, y, w, h = self.window['bounds']
        if getattr(self, 'capture_backend', 'ScreenCaptureKit') == 'ScreenCaptureKit':
            try:
                if self.native_capture is None:
                    self.native_capture = NativeCapture(self.window_id, self.stop_event)
                frame = self.native_capture.capture(self.window['bounds'])
            except (CaptureError, ImportError, AttributeError) as exc:
                self.capture_warning = str(exc)
                self.capture_backend = 'screencapture fallback'
                if self.native_capture is not None:
                    self.native_capture.close()
                    self.native_capture = None
            else:
                self.guard()
                return frame
        with tempfile.TemporaryDirectory(prefix='nte-capture-') as directory:
            path = Path(directory) / 'frame.png'
            # -R uses global display points; PNG pixels can be Retina-scaled.
            subprocess.run(['/usr/sbin/screencapture', '-x', '-t', 'png',
                            '-R' + ','.join(str(round(v)) for v in (x, y, w, h)), str(path)],
                           check=True, timeout=4, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
            frame = cv2.imread(str(path))
        self.guard()
        if frame is None or frame.size == 0:
            raise RuntimeError('螢幕擷取失敗；請檢查螢幕錄製權限')
        return frame

    def close(self):
        if self.native_capture is not None:
            self.native_capture.close()
            self.native_capture = None

    def click(self, point, viewport):
        self.guard(input_action=True)
        q, _ = api()
        x, y, w, h = self.window['bounds']
        vx1, vy1, vx2, vy2 = viewport
        position = (x + w * (vx1 + point[0] * (vx2-vx1)),
                    y + h * (vy1 + point[1] * (vy2-vy1)))
        radius = min(1.0, max(0.0, getattr(self, 'click_jitter_points', 0)))
        position = (min(x+w*vx2-1, max(x+w*vx1+1, position[0]+random.uniform(-radius,radius))),
                    min(y+h*vy2-1, max(y+h*vy1+1, position[1]+random.uniform(-radius,radius))))
        q.CGEventPost(q.kCGHIDEventTap, q.CGEventCreateMouseEvent(None, q.kCGEventMouseMoved, position, q.kCGMouseButtonLeft))
        self.guard(input_action=True)
        q.CGEventPost(q.kCGHIDEventTap, q.CGEventCreateMouseEvent(None, q.kCGEventLeftMouseDown, position, q.kCGMouseButtonLeft))
        try:
            self.stop_event.wait(.06 + random.uniform(-min(.004, max(0, getattr(self, 'time_jitter_seconds', 0))), min(.004, max(0, getattr(self, 'time_jitter_seconds', 0)))))
        finally:
            q.CGEventPost(q.kCGHIDEventTap, q.CGEventCreateMouseEvent(None, q.kCGEventLeftMouseUp, position, q.kCGMouseButtonLeft))

    def key(self, name):
        self.guard(input_action=True)
        q, _ = api()
        code = KEYS[name]
        q.CGEventPost(q.kCGHIDEventTap, q.CGEventCreateKeyboardEvent(None, code, True))
        try:
            self.stop_event.wait(.06 + random.uniform(-min(.004, max(0, getattr(self, 'time_jitter_seconds', 0))), min(.004, max(0, getattr(self, 'time_jitter_seconds', 0)))))
        finally:
            q.CGEventPost(q.kCGHIDEventTap, q.CGEventCreateKeyboardEvent(None, code, False))

    def scroll(self, point, viewport, amount):
        self.guard(input_action=True)
        q, _ = api()
        x, y, w, h = self.window['bounds']
        a,b,c,d = viewport
        position = (x+w*(a+point[0]*(c-a)), y+h*(b+point[1]*(d-b)))
        q.CGEventPost(q.kCGHIDEventTap, q.CGEventCreateMouseEvent(None, q.kCGEventMouseMoved, position, q.kCGMouseButtonLeft))
        self.guard(input_action=True)
        event = q.CGEventCreateScrollWheelEvent(None, q.kCGScrollEventUnitLine, 1, int(amount))
        q.CGEventPost(q.kCGHIDEventTap, event)

    def scroll_to_top(self, point, viewport, amount, burst=4):
        for i in range(burst):
            self.scroll(point, viewport, amount)
            if i+1 < burst and self.stop_event.wait(.08):
                raise InterruptedError('已停止')
