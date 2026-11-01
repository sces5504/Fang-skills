import sys

if __name__ == '__main__':
    if '--self-test' in sys.argv:
        import cv2
        import numpy as np
        import ScreenCaptureKit
        assert hasattr(ScreenCaptureKit, "SCScreenshotManager")
        import Quartz
        import AppKit
        import ApplicationServices
        assert hasattr(ApplicationServices, "AXIsProcessTrustedWithOptions")
        assert hasattr(Quartz, "CGEventCreateScrollWheelEvent")
        from PySide6.QtWidgets import QApplication
        from nte_owner.engine import Engine
        from nte_owner.config import defaults
        from nte_owner.vision import normalize
        assert normalize(np.zeros((1080,1920,3), np.uint8)).shape == (1080,1920,3)
        assert Engine(defaults()).state == 'ready'
        from pathlib import Path
        from nte_owner.config import load, validate
        from nte_owner.vision import Vision
        root = Path(__file__).resolve().parent / 'nte_owner/assets/preset'
        config = load(root/'profile.json')
        validate(config, root)
        Vision(config, root)
        import tempfile
        from nte_owner.gui import MainWindow
        app = QApplication(['NTEOwnerMac', '-platform', 'offscreen'])
        with tempfile.TemporaryDirectory(prefix='nte-self-test-') as directory:
            window = MainWindow(data_dir=directory)
            window.show()
            app.processEvents()
            assert window.start_button.isEnabled()
            log_dir = Path(directory)/'logs'
            log_dir.mkdir(exist_ok=True)
            shot = log_dir/'20261101-160331-963055-error.png'
            shot.write_bytes(b'test')
            window.clear_screenshots_button.click()
            assert not shot.exists() and (Path(directory)/'profile.json').exists()
            window.close()
        print('NTEOwnerMac imports, bundled preset, core and GUI self-test OK')
    else:
        from nte_owner.gui import main
        raise SystemExit(main())
