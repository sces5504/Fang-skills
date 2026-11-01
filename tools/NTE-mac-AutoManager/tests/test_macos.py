import threading
from types import SimpleNamespace
import pytest
from nte_owner import macos


class Quartz:
    kCGHIDEventTap = 0
    kCGMouseButtonLeft = 0
    kCGEventMouseMoved = 1
    kCGEventLeftMouseDown = 2
    kCGEventLeftMouseUp = 3
    def __init__(self):
        self.events = []
    def CGEventCreateMouseEvent(self, _, kind, point, button):
        return kind, point
    def CGEventPost(self, _, event):
        self.events.append(event)
    def CGEventCreateKeyboardEvent(self, _, key, down):
        return key, down


def session(monkeypatch):
    q = Quartz()
    monkeypatch.setattr(macos, 'api', lambda: (q, None))
    s = object.__new__(macos.MacSession)
    s.stop_event = threading.Event()
    s.window = {'bounds': (100, 200, 1600, 1000)}
    s.guard = lambda **kwargs: None
    return s, q


def test_click_uses_display_points_not_retina_pixels(monkeypatch):
    s, q = session(monkeypatch)
    s.click((.5,.5), [0,.1,1,1])
    assert q.events == [(1,(900,750)), (2,(900,750)), (3,(900,750))]


def test_stop_during_press_still_releases_button(monkeypatch):
    s, q = session(monkeypatch)
    def wait(_):
        raise InterruptedError()
    s.stop_event.wait = wait
    with pytest.raises(InterruptedError):
        s.click((.5,.5), [0,0,1,1])
    assert q.events[-1][0] == q.kCGEventLeftMouseUp


def test_guard_failure_never_posts_input(monkeypatch):
    s, q = session(monkeypatch)
    def fail(**kwargs):
        raise RuntimeError('focus lost')
    s.guard = fail
    with pytest.raises(RuntimeError):
        s.key('escape')
    assert q.events == []


def test_fast_scroll_is_bounded_and_cancelable(monkeypatch):
    s,q=session(monkeypatch)
    calls=[]
    s.scroll=lambda *args:calls.append(args)
    s.stop_event.wait=lambda _:False
    s.scroll_to_top((.1,.5),[0,0,1,1],30)
    assert len(calls)==4 and all(c[-1]==30 for c in calls)
    calls.clear()
    s.stop_event.wait=lambda _:True
    with pytest.raises(InterruptedError):
        s.scroll_to_top((.1,.5),[0,0,1,1],30)
    assert len(calls)==1


def test_small_jitter_stays_bounded_and_press_release_match(monkeypatch):
    s,q=session(monkeypatch);s.click_jitter_points=1;s.time_jitter_seconds=.004
    waits=[];s.stop_event.wait=lambda t:waits.append(t)
    # Exercise both endpoints deterministically, not a flaky random distribution test.
    for value in (-1,1):
        monkeypatch.setattr(macos.random,'uniform',lambda a,b:a if value==-1 else b)
        s.click((.5,.5),[0,.1,1,1])
        move,down,up=q.events[-3:]
        assert move[1]==down[1]==up[1]
        assert abs(down[1][0]-900)<=1 and abs(down[1][1]-750)<=1
        assert waits[-1] == pytest.approx(.056 if value == -1 else .064)
