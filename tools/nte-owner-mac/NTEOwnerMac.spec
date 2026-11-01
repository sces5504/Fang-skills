# Build on Apple Silicon with an arm64 Python.
from pathlib import Path
root = Path(SPECPATH)
a = Analysis([str(root / 'main.py')], pathex=[str(root)],
             datas=[(str(root / 'LICENSE'), '.'), (str(root / 'NOTICE.md'), '.'), (str(root / 'nte_owner' / 'assets' / 'preset'), 'nte_owner/assets/preset')],
             hiddenimports=['Quartz', 'AppKit', 'ApplicationServices', 'ScreenCaptureKit', 'CoreMedia'],
             excludes=['tkinter', 'matplotlib', 'PyQt5', 'PyQt6'], noarchive=False)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name='NTEOwnerMac',
          debug=False, strip=False, upx=False, console=False, target_arch='arm64',
          codesign_identity=None, entitlements_file=None)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name='NTEOwnerMac')
app = BUNDLE(coll, name='NTEOwnerMac.app', bundle_identifier='org.local.nte-owner-mac',
             info_plist={'CFBundleDisplayName': 'NTE 店長特供',
                         'CFBundleShortVersionString': '0.1.12',
                         'LSMinimumSystemVersion': '14.0',
                         'NSHighResolutionCapable': True,
                         'NSScreenCaptureUsageDescription': '辨識使用者選取的遊戲視窗與訂單。',
                         'NSAccessibilityUsageDescription': '依辨識結果發送一般鍵盤與滑鼠操作。'})
