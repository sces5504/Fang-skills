from types import SimpleNamespace
import threading
import pytest
from nte_owner import macos


def environment(monkeypatch):
    w = {'id': 9, 'pid': 77, 'bounds': (10, 20, 1600, 900)}
    listing = [{'kCGWindowNumber': 9, 'kCGWindowBounds': dict(X=10,Y=20,Width=1600,Height=900)}]
    front = SimpleNamespace(processIdentifier=lambda: 77)
    q = SimpleNamespace(kCGWindowListOptionOnScreenOnly=1, kCGWindowListExcludeDesktopElements=2,
                        CGWindowListCopyWindowInfo=lambda *_: listing,
                        CGEventCreate=lambda _: None, CGEventGetLocation=lambda _: SimpleNamespace(x=500,y=500),
                        AXIsProcessTrusted=lambda: True)
    app = SimpleNamespace(NSWorkspace=SimpleNamespace(sharedWorkspace=lambda: SimpleNamespace(frontmostApplication=lambda: front)))
    monkeypatch.setattr(macos, 'api', lambda: (q,app))
    monkeypatch.setattr(macos, 'accessibility', lambda: q)
    monkeypatch.setattr(macos, 'windows', lambda: [w.copy()])
    s = macos.MacSession(9)
    return s, q, w, front, listing


def test_valid_front_window(monkeypatch):
    s, *_ = environment(monkeypatch)
    s.guard(True)


def test_focus_change_stops(monkeypatch):
    s, q, w, front, listing = environment(monkeypatch)
    front.processIdentifier = lambda: 99
    with pytest.raises(RuntimeError, match='前景'):
        s.guard(True)


def test_geometry_change_stops(monkeypatch):
    s, q, w, front, listing = environment(monkeypatch)
    w['bounds'] = (20,20,1600,900)
    with pytest.raises(RuntimeError, match='移動'):
        s.guard()


def overlay(owner='其他 App', pid=55):
    return {'kCGWindowNumber': 2, 'kCGWindowOwnerPID': pid, 'kCGWindowOwnerName': owner,
            'kCGWindowBounds': dict(X=0,Y=0,Width=1600,Height=900)}


def with_bundles(monkeypatch, bundles):
    def lookup(pid):
        return SimpleNamespace(bundleIdentifier=lambda: bundles[pid]) if pid in bundles else None
    _, app = macos.api()
    app.NSRunningApplication = SimpleNamespace(runningApplicationWithProcessIdentifier_=lookup)


def test_overlay_stops_and_names_owner(monkeypatch):
    s, q, w, front, listing = environment(monkeypatch)
    with_bundles(monkeypatch, {55: 'com.example.other'})
    monkeypatch.setattr(macos, 'OCCLUSION_GRACE_SECONDS', 0)
    listing.insert(0, overlay())
    with pytest.raises(RuntimeError, match='遮住遊戲（其他 App）'):
        s.guard()


def test_leftover_screenshot_overlay_is_ignored(monkeypatch):
    s, q, w, front, listing = environment(monkeypatch)
    with_bundles(monkeypatch, {55: 'com.apple.screencaptureui'})
    listing.insert(0, overlay('截圖'))
    s.guard(True)


def test_brief_overlay_waits_then_continues(monkeypatch):
    s, q, w, front, listing = environment(monkeypatch)
    with_bundles(monkeypatch, {55: 'com.example.other'})
    listing.insert(0, overlay())
    class Stop:
        def is_set(self):
            return False
        def wait(self, _):
            listing.pop(0)
            return False
    s.stop_event = Stop()
    s.guard(True)
    assert len(listing) == 1


def test_stop_during_overlay_wait(monkeypatch):
    s, q, w, front, listing = environment(monkeypatch)
    with_bundles(monkeypatch, {55: 'com.example.other'})
    listing.insert(0, overlay())
    s.stop_event = SimpleNamespace(is_set=lambda: False, wait=lambda _: True)
    with pytest.raises(InterruptedError):
        s.guard()


def test_emergency_corner_stops(monkeypatch):
    s, q, w, front, listing = environment(monkeypatch)
    q.CGEventGetLocation = lambda _: SimpleNamespace(x=11,y=21)
    with pytest.raises(InterruptedError):
        s.guard()


def test_stopped_session_never_captures(monkeypatch):
    s, *_ = environment(monkeypatch)
    s.stop_event.set()
    with pytest.raises(InterruptedError):
        s.capture()


def test_capture_can_adopt_same_foreground_window_geometry(monkeypatch):
    s,q,w,front,listing=environment(monkeypatch)
    w['bounds']=(10,20,1600,950)
    s.guard(allow_resize=True)
    assert s.window['bounds']==(10,20,1600,950)
    s.guard(input_action=True)


def test_resize_never_overrides_focus_protection(monkeypatch):
    s,q,w,front,listing=environment(monkeypatch)
    w['bounds']=(10,20,1600,950)
    front.processIdentifier=lambda:99
    with pytest.raises(RuntimeError,match='前景'):
        s.guard(allow_resize=True)
    assert s.window['bounds']==(10,20,1600,900)
