import threading
import numpy as np
import pytest
from nte_owner import runner
from nte_owner.config import defaults
from nte_owner.vision import Observation, prepare, FrameNotReady


def test_black_and_partial_fade_are_transient_not_invalid_calibration():
    c=defaults()
    with pytest.raises(FrameNotReady):prepare(np.zeros((1080,1920,3),np.uint8),c)
    partial=np.zeros((1080,1920,3),np.uint8);partial[500:550]=150
    with pytest.raises(FrameNotReady):prepare(partial,c)
    frame,viewport=prepare(np.full((1080,1920,3),150,np.uint8),c)
    assert frame.shape==(1080,1920,3) and viewport==[0,0,1,1]


@pytest.mark.parametrize("unknown_screen", [False, True])
def test_real_prepare_loading_then_first_order_runs_complete_recipe(tmp_path,monkeypatch,unknown_screen):
    stop=threading.Event();events=[];count=[0];seen=[];messages=[]
    good=np.full((1080,1920,3),150,np.uint8)
    black=np.zeros_like(good);partial=black.copy();partial[500:550]=150
    frames=[good,black,partial]+([good] if unknown_screen else [])+[good]
    class Session:
        def __init__(self,*_):pass
        def capture(self):
            f=frames[count[0]];count[0]+=1;return f
        def click(self,point,viewport):events.append((point,count[0]))
        def key(self,key):events.append((key,count[0]));stop.set()
    class Vision:
        def __init__(self,*_):pass
        def observe(self,frame,context=None):
            seen.append(count[0])
            if unknown_screen and count[0]==4:
                return Observation(frozenset(),(),{})
            if context=='ready':return Observation(frozenset({'stage_ready'}),(),{})
            return Observation(frozenset({'playing'}),('target','target'),{})
    c=defaults();c['points']={'start':(.8,.8),'cup':(.9,.9),'material':(.8,.7)}
    monkeypatch.setattr(runner,'validate',lambda *_:None)
    monkeypatch.setattr(runner,'Vision',Vision)
    runner.run(c,tmp_path,stop,messages.append,session_factory=Session,
               window_resolver=lambda *_:{'id':1,'bounds':(0,0,1920,1080)})
    assert seen==([1,4,5] if unknown_screen else [1,4])
    assert [p for p,_ in events]==[c['points'][k] for k in ('start','cup','material','cup','material')]+['escape']
    recovered=5 if unknown_screen else 4
    assert [n for _,n in events]==[1]+[recovered]*5
    assert any('已恢復' in m for m in messages)
    assert not list((tmp_path/'logs').glob('*-error.png'))


def test_persistent_black_waits_past_old_timeout_until_user_stop(tmp_path,monkeypatch):
    stop=threading.Event();clock=[0];count=[0];messages=[]
    class Session:
        def __init__(self,*_):pass
        def capture(self):
            clock[0]+=10;count[0]+=1
            if count[0] == 5:
                raise InterruptedError('使用者停止')
            return np.zeros((1080,1920,3),np.uint8)
        def click(self,*_):raise AssertionError('black frame must never click')
    monkeypatch.setattr(runner.time,'monotonic',lambda:clock[0])
    monkeypatch.setattr(runner,'validate',lambda *_:None)
    monkeypatch.setattr(runner,'Vision',lambda *_:None)
    c=defaults();c['state_timeout']=3
    runner.run(c,tmp_path,stop,messages.append,session_factory=Session,
               window_resolver=lambda *_:{'id':1,'bounds':(0,0,1920,1080)})
    assert count[0]==5 and stop.is_set()
    assert not any('逾時' in m for m in messages)
    assert any('使用者停止' in m for m in messages)


def test_waiting_excludes_network_delay_from_delivery_and_round_deadlines():
    from nte_owner.engine import Engine,Action
    e=Engine(defaults());e.enter('playing',0)
    o=Observation(frozenset({'playing'}),('target',),{})
    assert e.step(o,.1)==[Action('click','cup'),Action('click','material')]
    e.action_completed(Action('click','material'),.3)
    e.suspend_time(300)
    assert e.step(o,300.5)==[]  # Five minutes of loading must not cause a false timeout.
    assert e.step(o,301.31)==[Action('key','escape')] # Active one-second deadline still works.
