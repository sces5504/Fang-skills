import threading
import numpy as np
from nte_owner import runner
from nte_owner.config import defaults
from nte_owner.vision import Observation


def test_runner_cup_and_material_share_one_capture_and_stop_is_checked(tmp_path,monkeypatch):
    for stop_between in (False,True):
        stop=threading.Event();events=[];count=[0]
        class Session:
            def __init__(self,*_):pass
            def capture(self):
                count[0]+=1
                return np.zeros((1080,1920,3),np.uint8)
            def click(self,point,viewport):
                events.append((point,count[0]))
                if point==c['points']['material'] or (stop_between and point==c['points']['cup']):stop.set()
        class Vision:
            def __init__(self,*_):pass
            def observe(self,frame,context=None):
                if context=='ready':return Observation(frozenset({'stage_ready'}),(),{})
                return Observation(frozenset({'playing'}),('target',),{})
        c=defaults();c['points']={'start':(.8,.8),'cup':(.9,.9),'material':(.8,.7)}
        monkeypatch.setattr(runner,'validate',lambda *_:None)
        monkeypatch.setattr(runner,'Vision',Vision)
        monkeypatch.setattr(runner,'prepare',lambda f,c:(f,[0,0,1,1]))
        runner.run(c,tmp_path,stop,lambda _:None,session_factory=Session,
                   window_resolver=lambda *_:{'id':1,'bounds':(0,0,1920,1080)})
        assert events[1][0]==c['points']['cup']
        if stop_between:assert len(events)==2
        else:
            assert events[2][0]==c['points']['material']
            assert events[1][1]==events[2][1] # No screenshot/recognition between recipe clicks.


def test_runner_two_orders_and_escape_without_intermediate_capture(tmp_path,monkeypatch):
    stop=threading.Event();events=[];count=[0]
    class Session:
        def __init__(self,*_):pass
        def capture(self):
            count[0]+=1
            return np.zeros((1080,1920,3),np.uint8)
        def click(self,point,viewport):events.append((point,count[0]))
        def key(self,key):
            events.append((key,count[0]));stop.set()
    class Vision:
        def __init__(self,*_):pass
        def observe(self,frame,context=None):
            if context=='ready':return Observation(frozenset({'stage_ready'}),(),{})
            return Observation(frozenset({'playing'}),('target','target'),{})
    c=defaults();c['points']={'start':(.8,.8),'cup':(.9,.9),'material':(.8,.7)}
    monkeypatch.setattr(runner,'validate',lambda *_:None)
    monkeypatch.setattr(runner,'Vision',Vision)
    monkeypatch.setattr(runner,'prepare',lambda f,c:(f,[0,0,1,1]))
    runner.run(c,tmp_path,stop,lambda _:None,session_factory=Session,
               window_resolver=lambda *_:{'id':1,'bounds':(0,0,1920,1080)})
    assert [p for p,_ in events]==[c['points'][k] for k in ('start','cup','material','cup','material')]+['escape']
    assert len({n for _,n in events[1:]})==1


def test_runner_waits_through_transient_aspect_change_then_fails_if_it_persists(tmp_path,monkeypatch):
    for persistent in (False,True):
        stop=threading.Event();events=[];messages=[];count=[0]
        class Session:
            def __init__(self,*_):pass
            def capture(self):
                count[0]+=1
                if persistent or count[0] in (2,3):return np.zeros((1167,1920,3),np.uint8)
                return np.zeros((1205,1920,3),np.uint8)
            def click(self,point,viewport):
                events.append(point)
                if point==c['points']['cup']:stop.set()
        class Vision:
            def __init__(self,*_):pass
            def observe(self,frame,context=None):
                if context=='ready':return Observation(frozenset({'stage_ready'}),(),{})
                return Observation(frozenset({'playing'}),('target',),{})
        c=defaults();c['points']={'start':(.8,.8),'cup':(.9,.9),'material':(.8,.7)};c['expected_aspect']=1920/1205
        monkeypatch.setattr(runner,'validate',lambda *_:None)
        monkeypatch.setattr(runner,'Vision',Vision)
        monkeypatch.setattr(runner,'prepare',lambda f,c:(f,[0,0,1,1]))
        monkeypatch.setattr(runner,'ASPECT_GRACE_SECONDS',0.2 if persistent else 60)
        runner.run(c,tmp_path,stop,messages.append,session_factory=Session,
                   window_resolver=lambda *_:{'id':1,'bounds':(0,0,1512,949)})
        if persistent:
            assert events==[] and messages[-1]=='已停止：畫面比例與模板不符；請重新校準或載入相同比例的設定'
        else:
            assert events[:2]==[c['points']['start'],c['points']['cup']]
            assert any('畫面比例暫時改變' in m for m in messages)
