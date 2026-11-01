import threading
import pytest
import numpy as np
from nte_owner.capture import await_result, CaptureError, image_to_bgr


def test_callback_errors_timeout_and_stop_never_return_a_frame():
    stop=threading.Event()
    assert await_result(lambda cb:cb('frame',None),stop)=='frame'
    with pytest.raises(CaptureError):await_result(lambda cb:cb(None,'denied'),stop)
    with pytest.raises(CaptureError):await_result(lambda cb:None,stop,timeout=.001)
    stop.set()
    with pytest.raises(InterruptedError):await_result(lambda cb:cb('frame',None),stop)


def test_native_pixel_conversion_preserves_color_and_orientation():
    q=pytest.importorskip('Quartz')
    raw=bytes([0,0,255,255,0,255,0,255,255,0,0,255,255,255,255,255])
    image=q.CGImageCreate(2,2,8,32,8,q.CGColorSpaceCreateWithName(q.kCGColorSpaceSRGB),
                          q.kCGImageAlphaPremultipliedFirst|q.kCGBitmapByteOrder32Little,
                          q.CGDataProviderCreateWithCFData(raw),None,False,q.kCGRenderingIntentDefault)
    assert image_to_bgr(image).tolist()==[[[0,0,255],[0,255,0]],[[255,0,0],[255,255,255]]]


def test_native_capture_retains_before_after_guards(monkeypatch):
    from nte_owner import macos
    from test_guards import environment
    s,*_=environment(monkeypatch);events=[]
    class Native:
        def __init__(self,*_):pass
        def capture(self,bounds):events.append('capture');return np.zeros((10,16,3),np.uint8)
    monkeypatch.setattr(macos,'NativeCapture',Native)
    s.guard=lambda **kw:events.append('guard')
    assert s.capture().shape==(10,16,3)
    assert events==['guard','capture','guard']
    # A failure in the post-capture guard must propagate, not use an old frame.
    def guard(**kw):
        if not kw:raise RuntimeError('focus lost')
    s.guard=guard
    with pytest.raises(RuntimeError,match='focus'):s.capture()
