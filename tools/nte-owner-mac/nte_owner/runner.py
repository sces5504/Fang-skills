import json
import time
import random
from datetime import datetime
from pathlib import Path
import cv2
from . import __version__
from .config import validate
from .engine import Engine
from .vision import Vision, crop, normalize, prepare, FrameNotReady
from .macos import MacSession, resolve_game_window

ASPECT_GRACE_SECONDS = 10.0
NO_ORDER_SNAPSHOT_SECONDS = 3.0
NO_ORDER_SNAPSHOT_LIMIT = 5


def run(config, root, stop, notify, dry_run=False, session_factory=MacSession, window_resolver=resolve_game_window):
    validate(config, root)
    vision = Vision(config, root)
    log_dir = Path(root) / 'logs'
    log_dir.mkdir(exist_ok=True)
    stamp = datetime.now().strftime('%Y%m%d-%H%M%S-%f')
    frame = None
    session = None
    engine = Engine(config, time.monotonic())
    started_at = time.monotonic()
    with (log_dir / (stamp + '.jsonl')).open('w') as log:
        def report(message, **data):
            log.write(json.dumps(dict(message=message, elapsed=round(time.monotonic()-started_at,3), **data), ensure_ascii=False) + '\n')
            log.flush()
            notify(message)
        try:
            report('執行版本 ' + __version__)
            report('等待前景 NTE 與全螢幕畫面穩定…')
            window = window_resolver(config, stop)
            session = session_factory(window['id'], stop)
            session.click_jitter_points = config.get('click_jitter_points', 1.0)
            session.time_jitter_seconds = config.get('time_jitter_seconds', .004)
            jitter = min(.004, max(0, config.get('time_jitter_seconds', .004)))
            cv2.setNumThreads(2)
            engine = Engine(config, time.monotonic())
            report('已自動鎖定目前的 NTE 視窗', window_id=window['id'], bounds=window['bounds'])
            last_diagnostic = 0
            waiting_since = None
            waiting_note = 0
            aspect_mismatch_since = None
            # Diagnostic frames for long gaps with no detected order while playing.
            no_order_since = None
            no_order_saved = 0
            def wait_for_screen(reason, began):
                nonlocal waiting_since, waiting_note
                now = time.monotonic()
                if waiting_since is None:
                    waiting_since = began
                    waiting_note = now
                    report(f'{engine.state}：{reason}；等待畫面恢復，暫不操作')
                elif now-waiting_note >= 5:
                    report(f'仍在等待畫面恢復（{now-waiting_since:.0f} 秒）；可隨時按停止')
                    waiting_note = now
                return stop.wait(.05)
            while not stop.is_set():
                capture_started = time.monotonic()
                frame = session.capture()
                try:
                    frame, input_viewport = prepare(frame, config)
                except FrameNotReady as exc:
                    if wait_for_screen(str(exc), capture_started):
                        break
                    continue
                if getattr(session, 'capture_warning', None):
                    report('快速擷取不可用，暫用舊擷取：' + session.capture_warning)
                    session.capture_warning = None
                capture_ms = round((time.monotonic()-capture_started)*1000)
                vision_started = time.monotonic()
                # Fullscreen/loading transitions briefly resize the window; only a lasting mismatch is fatal.
                if config.get('expected_aspect') and abs(frame.shape[1]/frame.shape[0] - config['expected_aspect']) > .035:
                    if aspect_mismatch_since is None:
                        aspect_mismatch_since = capture_started
                    if capture_started-aspect_mismatch_since > ASPECT_GRACE_SECONDS:
                        raise ValueError('畫面比例與模板不符；請重新校準或載入相同比例的設定')
                    if wait_for_screen('畫面比例暫時改變（轉場中）', capture_started):
                        break
                    continue
                aspect_mismatch_since = None
                observation = vision.observe(frame, context=None if dry_run else engine.state)
                now = time.monotonic()
                usable = {'ready': {'stage_list','stage_ready'},
                          'starting': {'playing'},
                          'playing': {'playing'},
                          'settling': {'result','result_failed','confirm','settle_menu','stage_list','stage_ready'}}
                if not dry_run and not (observation.visible & usable.get(engine.state, set())):
                    if wait_for_screen('尚未看到可操作的遊戲畫面', capture_started):
                        break
                    continue
                if waiting_since is not None:
                    engine.suspend_time(now-waiting_since)
                    report('遊戲畫面已恢復，繼續原流程', waited_seconds=round(now-waiting_since,3))
                    waiting_since = None
                vision_ms = round((now-vision_started)*1000)
                if dry_run:
                    if now - last_diagnostic >= 1:
                        report('僅辨識：' + ', '.join(sorted(observation.visible)) +
                               ' 訂單=' + str(observation.orders) + ' 活力=' + str(observation.energy), scores=observation.scores)
                        last_diagnostic = now
                else:
                    if now-last_diagnostic >= 2:
                        report(f'{engine.state}：畫面={sorted(observation.visible)} 訂單={observation.orders} 已確認出餐={engine.delivered} 等待={engine.busy}', scores=observation.scores)
                        last_diagnostic = now
                    if engine.state == 'playing' and not engine.busy and all(o == 'absent' for o in observation.orders):
                        if no_order_since is None:
                            no_order_since = now
                        elif now-no_order_since >= NO_ORDER_SNAPSHOT_SECONDS*(no_order_saved+1) and no_order_saved < NO_ORDER_SNAPSHOT_LIMIT:
                            no_order_saved += 1
                            cv2.imwrite(str(log_dir / f'{stamp}-noorder-{no_order_saved}.png'), frame)
                            report(f'無訂單已 {now-no_order_since:.1f} 秒，已存診斷截圖 {no_order_saved}')
                    else:
                        no_order_since = None
                    actions = engine.step(observation, now)
                    for action_index, action in enumerate(actions):
                        if action.name == "material" and action_index > 0 and actions[action_index-1].name == "cup":
                            if stop.wait(max(0, config["click_gap"] + random.uniform(-jitter,jitter))):
                                break
                        # Allow a game frame after material before reusing the cup or Esc.
                        if action_index > 0 and actions[action_index-1].name == 'material':
                            if stop.wait(.08 + random.uniform(-jitter,jitter)):
                                break
                        if stop.is_set():
                            break
                        if action.kind == 'click':
                            session.click(config['points'][action.name], input_viewport)
                        elif action.kind == 'match':
                            session.click(observation.locations[action.name], input_viewport)
                        elif action.kind == 'scroll':
                            session.scroll_to_top(config['points']['scroll'], input_viewport, config['scroll_amount'], config.get('scroll_burst', 4))
                        else:
                            session.key(action.name)
                        actions.extend(engine.action_completed(action, time.monotonic()))
                        report(f'{engine.state} → {action.kind} {action.name}', capture_ms=capture_ms, vision_ms=vision_ms, capture_backend=getattr(session,'capture_backend','test'), scores=observation.scores)
                    if engine.stopped:
                        report(f'{engine.reason}；完成 {engine.completed} 局，兩單 {engine.two_order_rounds}，三星 {engine.success}，提前 {engine.early}')
                        if engine.reason != '已完成指定次數':
                            cv2.imwrite(str(log_dir / (stamp + '-stopped.png')), frame)
                        break
                if stop.wait(0.02):
                    break
        except InterruptedError as exc:
            report(str(exc))
        except Exception as exc:
            if frame is not None:
                cv2.imwrite(str(log_dir / (stamp + '-error.png')), frame)
            report('已停止：' + str(exc))
        finally:
            stop.set()
            if session is not None and hasattr(session, 'close'):
                session.close()
