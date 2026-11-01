import copy
import sys
import threading
from pathlib import Path
import cv2
from PySide6.QtCore import Qt, QRect, Signal, QObject, QTimer
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import (QApplication, QWidget, QLabel, QPushButton, QVBoxLayout,
    QHBoxLayout, QComboBox, QSpinBox, QDoubleSpinBox, QPlainTextEdit, QDialog,
    QDialogButtonBox, QFileDialog, QMessageBox, QInputDialog)
from .config import defaults, load, save, validate, load_with_preset, TEMPLATES, POINTS, KEYS
from .vision import normalize, crop, Vision, prepare
from .macos import windows, permissions, MacSession, foreground_window, resolve_game_window
from .runner import run
from .storage import clear_run_screenshots


def pixmap(frame):
    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    return QPixmap.fromImage(QImage(rgb.data, rgb.shape[1], rgb.shape[0], rgb.strides[0], QImage.Format_RGB888).copy())


class Selection(QLabel):
    def __init__(self, frame, point=False):
        super().__init__()
        self.point = point
        self.selection = None
        self.origin = None
        self.setPixmap(pixmap(frame).scaled(1000, 600, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        self.setFixedSize(self.pixmap().size())

    def mousePressEvent(self, event):
        self.origin = event.position().toPoint()
        self.selection = None

    def mouseReleaseEvent(self, event):
        if self.origin is None:
            return
        end = event.position().toPoint()
        x, y = max(0, min(self.width()-1, end.x())), max(0, min(self.height()-1, end.y()))
        if self.point:
            self.selection = [x / self.width(), y / self.height()]
        else:
            rect = QRect(self.origin, end).normalized().intersected(self.rect())
            if rect.width() >= 4 and rect.height() >= 4:
                self.selection = [rect.x()/self.width(), rect.y()/self.height(),
                                  (rect.x()+rect.width())/self.width(), (rect.y()+rect.height())/self.height()]
        self.update()

    def paintEvent(self, event):
        super().paintEvent(event)
        if self.selection:
            from PySide6.QtGui import QPainter, QPen
            p = QPainter(self)
            p.setPen(QPen(Qt.green, 2))
            s = self.selection
            if self.point:
                p.drawEllipse(int(s[0]*self.width())-5, int(s[1]*self.height())-5, 10, 10)
            else:
                p.drawRect(int(s[0]*self.width()), int(s[1]*self.height()),
                           int((s[2]-s[0])*self.width()), int((s[3]-s[1])*self.height()))
            p.end()


def select(parent, frame, title, point=False):
    dialog = QDialog(parent)
    dialog.setWindowTitle(title)
    layout = QVBoxLayout(dialog)
    layout.addWidget(QLabel('點擊目標後按 OK' if point else '拖曳框選區域後按 OK'))
    view = Selection(frame, point)
    layout.addWidget(view)
    buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
    buttons.accepted.connect(dialog.accept)
    buttons.rejected.connect(dialog.reject)
    layout.addWidget(buttons)
    return view.selection if dialog.exec() and view.selection else None


class Bus(QObject):
    message = Signal(str)
    captured = Signal(object)
    window_selected = Signal(object)
    done = Signal()


class MainWindow(QWidget):
    def __init__(self, data_dir=None):
        super().__init__()
        self.setWindowTitle('NTE 店長特供 1-1 · Mac')
        self.resize(760, 750)
        self.root = Path(data_dir) if data_dir else Path.home() / 'Library/Application Support/NTEOwnerMac'
        self.root.mkdir(parents=True, exist_ok=True)
        (self.root / 'templates').mkdir(exist_ok=True)
        self.path = self.root / 'profile.json'
        self.preset_loaded = False
        try:
            self.config, self.preset_loaded = load_with_preset(self.root, Path(__file__).resolve().parent/'assets/preset')
        except Exception:
            self.config = defaults()
        self.frame = None
        self.stop_event = threading.Event()
        self.thread = None
        self.bus = Bus()
        self.bus.message.connect(self.message)
        self.bus.captured.connect(self.on_capture)
        self.bus.done.connect(self.on_done)
        self.bus.window_selected.connect(self.on_window_selected)
        layout = QVBoxLayout(self)
        intro = QLabel('先手動進入店長精選清單；工具會向上捲動尋找 1-1。開始會自動鎖定 NTE，通常不需選視窗或框選位置。\n'
                       '開始後 5 秒內切回遊戲；切換到其他 App 或遮擋會停止。\n'
                       '緊急停止：滑鼠移到遊戲視窗左上角，或切換回此工具按停止。')
        intro.setWordWrap(True)
        layout.addWidget(intro)
        row = QHBoxLayout()
        self.window_box = QComboBox()
        row.addWidget(self.window_box, 1)
        self.refresh_button = QPushButton('重新列出視窗')
        self.refresh_button.clicked.connect(self.refresh)
        row.addWidget(self.refresh_button)
        permission = QPushButton('授予螢幕錄製／輔助使用權限')
        permission.clicked.connect(self.request_permissions)
        row.addWidget(permission)
        layout.addLayout(row)
        self.fullscreen_button = QPushButton('全螢幕：5 秒後鎖定前景遊戲')
        self.fullscreen_button.clicked.connect(self.select_fullscreen)
        layout.addWidget(self.fullscreen_button)
        self.settings = QWidget()
        settings = QVBoxLayout(self.settings)
        row = QHBoxLayout()
        self.rounds = QSpinBox()
        self.rounds.setRange(0, 100000)
        self.rounds.setValue(self.config['rounds'])
        row.addWidget(QLabel('局數（0=無限）'))
        row.addWidget(self.rounds)
        self.key = QComboBox()
        self.key.addItems(KEYS)
        self.key.setCurrentText(self.config['settle_key'])
        row.addWidget(QLabel('結算鍵'))
        row.addWidget(self.key)
        self.threshold = QDoubleSpinBox()
        self.threshold.setRange(0.6, 0.999)
        self.threshold.setDecimals(3)
        self.threshold.setSingleStep(0.01)
        self.threshold.setValue(self.config['threshold'])
        row.addWidget(QLabel('辨識門檻'))
        row.addWidget(self.threshold)
        settings.addLayout(row)
        self.calibration = QWidget()
        toggle = QPushButton('進階辨識校準（通常不需要）')
        toggle.setCheckable(True)
        toggle.toggled.connect(self.calibration.setVisible)
        settings.addWidget(toggle)
        settings.addWidget(self.calibration)
        settings = QVBoxLayout(self.calibration)
        self.calibration.setVisible(False)
        row = QHBoxLayout()
        for label, callback in [('載入附圖預設', self.use_preset), ('5 秒後擷取遊戲', self.capture), ('載入截圖', self.import_image),
                                ('框選遊戲內容', self.viewport), ('新增顧客訂單區域', self.slot),
                                ('清除訂單區域', self.clear_slots)]:
            button = QPushButton(label)
            button.clicked.connect(callback)
            row.addWidget(button)
        settings.addLayout(row)
        self.template = QComboBox()
        for key, label in TEMPLATES.items():
            self.template.addItem(label, key)
        row = QHBoxLayout()
        row.addWidget(self.template, 1)
        button = QPushButton('框選辨識模板')
        button.clicked.connect(self.template_select)
        row.addWidget(button)
        button = QPushButton('移除此模板')
        button.clicked.connect(self.remove_template)
        row.addWidget(button)
        settings.addLayout(row)
        row = QHBoxLayout()
        self.point = QComboBox()
        for key, label in POINTS.items():
            self.point.addItem(label, key)
        row.addWidget(self.point, 1)
        button = QPushButton('校準點擊位置')
        button.clicked.connect(self.point_select)
        row.addWidget(button)
        button = QPushButton('測試本張截圖辨識')
        button.clicked.connect(self.inspect)
        row.addWidget(button)
        settings.addLayout(row)
        row = QHBoxLayout()
        for label, callback in [('校準三顆星', self.calibrate_stars), ('校準活力數字／0', self.calibrate_energy)]:
            button = QPushButton(label)
            button.clicked.connect(callback)
            row.addWidget(button)
        row.addWidget(QLabel('向上捲動量（方向相反改負數）'))
        self.scroll_amount = QSpinBox()
        self.scroll_amount.setRange(-30,30)
        self.scroll_amount.setValue(self.config['scroll_amount'])
        row.addWidget(self.scroll_amount)
        settings.addLayout(row)
        self.summary = QLabel()
        self.summary.setWordWrap(True)
        settings.addWidget(self.summary)
        layout.addWidget(self.settings)
        row = QHBoxLayout()
        self.preview_button = QPushButton('只辨識，不操作')
        self.preview_button.clicked.connect(lambda: self.start(True))
        self.start_button = QPushButton('開始刷關（5 秒倒數）')
        self.start_button.clicked.connect(lambda: self.start(False))
        stop = QPushButton('停止')
        stop.clicked.connect(self.stop)
        row.addWidget(self.preview_button)
        row.addWidget(self.start_button)
        row.addWidget(stop)
        self.clear_screenshots_button = QPushButton('清除執行截圖')
        self.clear_screenshots_button.clicked.connect(self.clear_screenshots)
        row.addWidget(self.clear_screenshots_button)
        layout.addLayout(row)
        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setMaximumBlockCount(500)
        layout.addWidget(self.log)
        self.message('設定與錯誤截圖僅存於本機：' + str(self.root))
        self.refresh()
        self.update_summary()
        if self.preset_loaded:
            self.message('已自動載入你的截圖辨識預設與操作位置；不必逐項框選。請先鎖定遊戲，再用「只辨識」確認。')

    def clear_screenshots(self):
        try:
            count, size, failures = clear_run_screenshots(self.root)
            self.message(f'已清除 {count} 張執行截圖，釋放 {size/1024/1024:.2f} MB；設定、模板與文字記錄保留。')
            if failures:
                self.message(f'{len(failures)} 張無法刪除：' + '; '.join(failures))
        except Exception as exc:
            self.message('清除截圖失敗：' + str(exc))

    def use_preset(self):
        import shutil
        import json
        resource = Path(__file__).resolve().parent / 'assets' / 'preset'
        if self.path.exists() and QMessageBox.question(self, '載入附圖預設', '以附圖建立的預設取代目前校準設定？') != QMessageBox.Yes:
            return
        self.config = defaults()
        self.config.update(json.loads((resource/'profile.json').read_text()))
        for source in (resource/'templates').glob('*.png'):
            shutil.copy2(source, self.root/'templates'/source.name)
        self.rounds.setValue(self.config['rounds'])
        self.threshold.setValue(self.config['threshold'])
        self.key.setCurrentText(self.config['settle_key'])
        self.scroll_amount.setValue(self.config['scroll_amount'])
        self.persist()
        self.message('已載入附圖預設。先用「只辨識」檢查；視窗比例或 UI 大小不同時請重新校準。')

    def message(self, text):
        self.log.appendPlainText(text)

    def refresh(self):
        try:
            self.window_box.clear()
            for w in windows(include_hidden=True):
                self.window_box.addItem(w['name'], w['id'])
                if w['id'] == self.config['window_id']:
                    self.window_box.setCurrentIndex(self.window_box.count()-1)
        except Exception as exc:
            self.message(str(exc))

    def select_fullscreen(self):
        self.stop_event = threading.Event()
        self.busy(True)
        self.message('請在 5 秒內用 Command-Tab 或切換桌面回到全螢幕 NTE；這一步只選取，不操作遊戲。')
        def work():
            try:
                if not self.stop_event.wait(5):
                    window = foreground_window()
                    if not self.stop_event.is_set():
                        self.bus.window_selected.emit(window)
            except Exception as exc:
                self.bus.message.emit(str(exc))
            finally:
                self.bus.done.emit()
        self.thread = threading.Thread(target=work, daemon=True)
        self.thread.start()

    def on_window_selected(self, window):
        index = self.window_box.findData(window['id'])
        if index < 0:
            self.window_box.addItem(window['name'], window['id'])
            index = self.window_box.count()-1
        self.window_box.setCurrentIndex(index)
        self.persist()
        self.message('已鎖定：' + window['name'] + '。請回工具確認名稱，再按「只辨識」或「開始刷關」。')

    def request_permissions(self):
        try:
            capture, access = permissions(True)
            self.message(f'目前權限：螢幕錄製={capture}，輔助使用={access}。授權後可能需重新開啟工具。')
        except Exception as exc:
            self.message(str(exc))

    def persist(self):
        self.config.update(window_id=self.window_box.currentData() or 0, rounds=self.rounds.value(),
                           settle_key=self.key.currentText(), threshold=self.threshold.value(), scroll_amount=self.scroll_amount.value())
        save(self.path, self.config)
        self.update_summary()

    def update_summary(self):
        self.summary.setText('已校準模板：' + ', '.join(self.config['templates']) + '\n'
                             '操作點：' + ', '.join(self.config['points']) +
                             ("；訂單：全顧客區域自動追蹤" if self.config.get('order_search_roi') else f"；訂單區域：{len(self.config['slots'])}"))

    def busy(self, enabled):
        self.settings.setEnabled(not enabled)
        self.window_box.setEnabled(not enabled)
        self.refresh_button.setEnabled(not enabled)
        self.fullscreen_button.setEnabled(not enabled)
        self.start_button.setEnabled(not enabled)
        self.preview_button.setEnabled(not enabled)

    def capture(self):
        self.persist()
        self.stop_event = threading.Event()
        self.busy(True)
        self.message('5 秒後擷取。請切回遊戲，且不要移動視窗。')
        capture_config = copy.deepcopy(self.config)
        def work():
            try:
                if not self.stop_event.wait(5):
                    window = resolve_game_window(capture_config, self.stop_event)
                    self.bus.captured.emit(MacSession(window['id'], self.stop_event).capture())
            except Exception as exc:
                self.bus.message.emit(str(exc))
            finally:
                self.bus.done.emit()
        self.thread = threading.Thread(target=work, daemon=True)
        self.thread.start()

    def on_capture(self, frame):
        self.frame = frame
        self.message('已取得視窗截圖，可切回工具框選；所有座標以視窗內的遊戲內容為準。')

    def import_image(self):
        name, _ = QFileDialog.getOpenFileName(self, '載入完整遊戲視窗截圖', '', 'Images (*.png *.jpg *.jpeg)')
        if name:
            image = cv2.imread(name)
            if image is not None:
                self.on_capture(image)

    def game_frame(self):
        if self.frame is None:
            raise ValueError('請先擷取或載入截圖')
        return prepare(self.frame, self.config)[0]

    def viewport(self):
        try:
            if self.frame is None:
                raise ValueError('請先擷取截圖')
            r = select(self, self.frame, '只框遊戲內容，排除標題列與黑邊')
            if r:
                normalize(crop(self.frame, r))
                self.config['viewport'] = r
                self.config['auto_trim'] = False
                self.config['expected_aspect'] = crop(self.frame,r).shape[1]/crop(self.frame,r).shape[0]
                self.config['star_rois'] = []
                self.config['order_search_roi'] = None
                self.config['energy_roi'] = None
                self.config['energy_zero'] = None
                # Coordinates/templates belong to the previous viewport.
                self.config['templates'], self.config['points'], self.config['slots'] = {}, {}, []
                self.persist()
                self.message('已更新遊戲內容範圍；請重新校準模板、訂單區域及操作點。')
        except Exception as exc:
            self.message(str(exc))

    def slot(self):
        try:
            r = select(self, self.game_frame(), '框一位顧客的完整訂單氣泡及可能移動範圍')
            if r:
                self.config['order_search_roi'] = None
                self.config['slots'].append(r)
                self.persist()
        except Exception as exc:
            self.message(str(exc))

    def clear_slots(self):
        self.config['slots'] = []
        self.persist()

    def calibrate_stars(self):
        try:
            frame = self.game_frame()
            rois = []
            for i in range(3):
                r = select(self, frame, f'框選右上第 {i+1} 顆星，緊貼星星外框')
                if not r:
                    return
                rois.append(r)
            self.config['star_rois'] = rois
            self.config['templates'].pop('three_stars', None)
            self.persist()
        except Exception as exc:
            self.message(str(exc))

    def calibrate_energy(self):
        try:
            frame = self.game_frame()
            r = select(self, frame, '框目前活力數字範圍，預留三位數寬度，不含 /700')
            if not r:
                return
            z = select(self, frame, '緊框分母 700 其中一個白色 0 字形，勿含邊框')
            if not z:
                return
            patch = cv2.inRange(crop(frame,z), (210,210,210), (255,255,255))
            coords = cv2.findNonZero(patch)
            if coords is None:
                raise ValueError('未找到白色數字')
            x,y,w,h = cv2.boundingRect(coords)
            file = 'templates/energy_zero.png'
            cv2.imwrite(str(self.root/file),patch[y:y+h,x:x+w])
            self.config['energy_roi'], self.config['energy_zero'] = r, file
            self.persist()
            self.message('活力數字已設定；請同時校準「活力分母 /700」模板。')
        except Exception as exc:
            self.message(str(exc))

    def template_select(self):
        try:
            frame = self.game_frame()
            key = self.template.currentData()
            r = select(self, frame, TEMPLATES[key])
            if r:
                patch = crop(frame, r)
                if min(patch.shape[:2]) < 4 or patch.std() < 3:
                    raise ValueError('區域太小或沒有足夠影像細節')
                file = 'templates/' + key + '.png'
                if not cv2.imwrite(str(self.root / file), patch):
                    raise OSError('無法寫入模板')
                # Search around the original region; target/marker use customer slots.
                roi = [max(0, r[0]-.025), max(0, r[1]-.025), min(1, r[2]+.025), min(1, r[3]+.025)]
                self.config['templates'][key] = dict(file=file, roi=roi)
                if key == 'energy_anchor':
                    self.config['energy_anchor_center'] = [(r[0]+r[2])/2,(r[1]+r[3])/2]
                self.persist()
        except Exception as exc:
            self.message(str(exc))

    def remove_template(self):
        self.config['templates'].pop(self.template.currentData(), None)
        self.persist()

    def point_select(self):
        try:
            p = select(self, self.game_frame(), POINTS[self.point.currentData()], point=True)
            if p:
                self.config['points'][self.point.currentData()] = p
                self.persist()
        except Exception as exc:
            self.message(str(exc))

    def inspect(self):
        try:
            self.persist()
            o = Vision(self.config, self.root).observe(self.game_frame())
            self.message(f'辨識：{sorted(o.visible)}；訂單：{o.orders}\n分數：' +
                         ', '.join(f'{k}={v:.3f}' for k, v in o.scores.items()))
        except Exception as exc:
            self.message(str(exc))

    def start(self, dry):
        try:
            self.persist()
            validate(self.config, self.root)
            capture, access = permissions()
            if not capture or (not dry and not access):
                raise ValueError('請先授予螢幕錄製與輔助使用權限')
            config = copy.deepcopy(self.config)
            self.stop_event = threading.Event()
            self.busy(True)
            self.message('5 秒後開始。請切回店長精選清單。' if not dry else '5 秒後開始純辨識，請切回遊戲。')
            def work():
                try:
                    if not self.stop_event.wait(5):
                        run(config, self.root, self.stop_event, self.bus.message.emit, dry)
                except Exception as exc:
                    self.bus.message.emit('已停止：' + str(exc))
                finally:
                    self.bus.done.emit()
            self.thread = threading.Thread(target=work, daemon=True)
            self.thread.start()
        except Exception as exc:
            self.message(str(exc))

    def stop(self):
        self.stop_event.set()
        self.message('停止已請求，不再發出下一個操作。')

    def on_done(self):
        self.busy(False)
        self.message('執行緒已結束。')

    def closeEvent(self, event):
        self.stop_event.set()
        if self.thread and self.thread.is_alive():
            event.ignore()
            QTimer.singleShot(100, self.close)
        else:
            event.accept()


def main():
    app = QApplication(sys.argv)
    app.setApplicationName('NTEOwnerMac')
    window = MainWindow()
    window.show()
    return app.exec()
