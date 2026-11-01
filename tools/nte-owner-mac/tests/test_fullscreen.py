from types import SimpleNamespace
import os
import pytest
from nte_owner import macos


def test_picker_lists_other_spaces_but_runtime_only_visible(monkeypatch):
    calls=[]
    q=SimpleNamespace(kCGWindowListOptionAll=0,kCGWindowListOptionOnScreenOnly=1,
        kCGWindowListExcludeDesktopElements=16,
        CGWindowListCopyWindowInfo=lambda flag,_: calls.append(flag) or [])
    monkeypatch.setattr(macos,'api',lambda:(q,None))
    macos.windows(include_hidden=True)
    macos.windows()
    assert calls==[16,17]


def test_fullscreen_pick_is_foreground_pid_and_largest_surface(monkeypatch):
    front=SimpleNamespace(processIdentifier=lambda:123456)
    app=SimpleNamespace(NSWorkspace=SimpleNamespace(sharedWorkspace=lambda:SimpleNamespace(frontmostApplication=lambda:front)))
    monkeypatch.setattr(macos,'api',lambda:(None,app))
    monkeypatch.setattr(macos,'windows',lambda:[
        dict(id=1,pid=123456,bounds=(0,0,400,300)),
        dict(id=2,pid=123456,bounds=(0,0,1512,945)),
        dict(id=3,pid=777,bounds=(0,0,3000,2000))])
    assert macos.foreground_window()['id']==2
    front.processIdentifier=lambda:os.getpid()
    with pytest.raises(RuntimeError,match='切回遊戲'):
        macos.foreground_window()


def test_rebind_ignores_stale_id_and_waits_for_geometry(monkeypatch):
    seen=[]
    samples=iter([
        dict(id=200,pid=999,bounds=(0,0,1400,900)),
        *[dict(id=201,pid=999,bounds=(0,0,1512,945)) for _ in range(4)]])
    def current(bundle):
        seen.append(bundle)
        return next(samples)
    monkeypatch.setattr(macos,'foreground_window',current)
    stop=SimpleNamespace(is_set=lambda:False,wait=lambda _:False)
    result=macos.resolve_game_window({'window_id':1575},stop)
    assert result['id']==201
    assert seen==['com.hottagames.nte']*5


def test_rebind_cancelled_without_input(monkeypatch):
    stop=SimpleNamespace(is_set=lambda:True)
    with pytest.raises(InterruptedError):
        macos.resolve_game_window({},stop)


def test_wrong_front_application_is_rejected(monkeypatch):
    front=SimpleNamespace(processIdentifier=lambda:123456,bundleIdentifier=lambda:'com.apple.finder')
    app=SimpleNamespace(NSWorkspace=SimpleNamespace(sharedWorkspace=lambda:SimpleNamespace(frontmostApplication=lambda:front)))
    monkeypatch.setattr(macos,'api',lambda:(None,app))
    with pytest.raises(RuntimeError,match='不是指定的遊戲'):
        macos.foreground_window('com.hottagames.nte')


def test_missing_window_list_has_actionable_error(monkeypatch):
    q=SimpleNamespace(kCGWindowListOptionAll=0,kCGWindowListOptionOnScreenOnly=1,
        kCGWindowListExcludeDesktopElements=16,CGWindowListCopyWindowInfo=lambda *_:None)
    monkeypatch.setattr(macos,'api',lambda:(q,None))
    with pytest.raises(RuntimeError,match='螢幕錄製權限'):
        macos.windows()
