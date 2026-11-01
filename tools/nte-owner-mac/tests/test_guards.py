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


def test_overlay_stops(monkeypatch):
    s, q, w, front, listing = environment(monkeypatch)
    listing.insert(0, {'kCGWindowNumber': 2, 'kCGWindowBounds': dict(X=400,Y=300,Width=200,Height=50)})
    with pytest.raises(RuntimeError, match='遮住'):
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
