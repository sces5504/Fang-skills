"""ScreenCaptureKit single-frame capture, in-process; no files or input events."""
import threading
import time
import numpy as np
import cv2


class CaptureError(RuntimeError):
    pass


def await_result(start, stop, timeout=4):
    done = threading.Event()
    result = []
    def complete(value, error):
        result.extend((value, error))
        done.set()
    start(complete)
    deadline = time.monotonic() + timeout
    while not done.wait(.01):
        if stop.is_set():
            raise InterruptedError('已停止')
        if time.monotonic() >= deadline:
            raise CaptureError('ScreenCaptureKit 擷取逾時')
    if stop.is_set():
        raise InterruptedError('已停止')
    value, error = result
    if error is not None or value is None:
        raise CaptureError(str(error or 'ScreenCaptureKit 未回傳畫面'))
    return value


def image_to_bgr(image):
    import Quartz as q
    width, height = q.CGImageGetWidth(image), q.CGImageGetHeight(image)
    if not (0 < width <= 8192 and 0 < height <= 8192):
        raise CaptureError('擷取尺寸無效')
    context = q.CGBitmapContextCreate(None, width, height, 8, width*4,
                                    q.CGColorSpaceCreateWithName(q.kCGColorSpaceSRGB),
                                    q.kCGImageAlphaPremultipliedFirst | q.kCGBitmapByteOrder32Little)
    if context is None:
        raise CaptureError('無法建立擷取緩衝區')
    q.CGContextDrawImage(context, q.CGRectMake(0,0,width,height), image)
    output = q.CGBitmapContextCreateImage(context)
    raw = q.CGDataProviderCopyData(q.CGImageGetDataProvider(output))
    return np.frombuffer(raw, np.uint8).reshape(height,width,4)[:,:,:3].copy()


class NativeCapture:
    def __init__(self, window_id, stop):
        import ScreenCaptureKit as sc
        self.sc, self.stop = sc, stop
        content = await_result(lambda cb: sc.SCShareableContent.getShareableContentExcludingDesktopWindows_onScreenWindowsOnly_completionHandler_(True, True, cb), stop)
        window = next((w for w in content.windows() if w.windowID() == window_id), None)
        if window is None:
            raise CaptureError('ScreenCaptureKit 找不到目前的遊戲視窗')
        self.filter = sc.SCContentFilter.alloc().initWithDesktopIndependentWindow_(window)

    def capture(self, bounds):
        config = self.sc.SCStreamConfiguration.alloc().init()
        # Capture at canonical width rather than encode a full Retina PNG.
        config.setWidth_(1920)
        config.setHeight_(round(1920*bounds[3]/bounds[2]))
        config.setShowsCursor_(False)
        config.setIgnoreShadowsSingleWindow_(True)
        config.setShouldBeOpaque_(True)
        config.setScalesToFit_(True)
        image = await_result(lambda cb: self.sc.SCScreenshotManager.captureImageWithFilter_configuration_completionHandler_(self.filter, config, cb), self.stop)
        return image_to_bgr(image)

    def close(self):
        self.filter = None
