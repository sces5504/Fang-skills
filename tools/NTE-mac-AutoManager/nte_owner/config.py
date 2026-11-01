import json
import math
from pathlib import Path

TEMPLATES = {
    'stage_list': '關卡清單標題（店長精選）',
    'stage_entry': '左側清單的 1-1 新品練習 I 文字',
    'energy_anchor': '活力分母 /700（啟用活力檢查時）',
    'stage_ready': '1-1 已選取（含關卡名稱，勿只框開始按鈕）',
    'playing': '營業中固定 HUD（避開數字、星星與訂單）',
    'target': '目標飲料圖示（只框飲料本身）',
    'order_marker': '訂單氣泡的固定邊框或底部指標（不含飲料）',
    'three_stars': '三星皆亮的星星區域',
    'settle_menu': 'Esc 後結算選單的固定標誌',
    'confirm': '結算確認對話框（可選）',
    'result': '結算結果畫面的固定標誌（可選）',
    'result_failed': '挑戰失敗畫面的「失敗」標題（可選）',
}
POINTS = {'start': '開始營業', 'cup': '右下杯子', 'material': '紅色材料包',
          'settle': '選單內結算', 'confirm': '確認結算', 'close': '結果畫面領取／退出', 'failed_exit': '挑戰失敗畫面的退出', 'scroll': '左側清單捲動位置'}
KEYS = {'escape': 53, 'tab': 48, 'return': 36, 'space': 49, 'f': 3}


def defaults():
    return dict(version=1, target_bundle_id='com.hottagames.nte', window_id=0, viewport=[0, 0, 1, 1], rounds=1,
                settle_key='escape', threshold=0.90, stable_frames=3,
                unknown_seconds=1.5, state_timeout=20.0, round_timeout=150.0,
                serve_timeout=12.0, delivery_timeout=1.0, delivery_confirm_frames=1,
                assume_target_drink=True, order_marker_threshold=0.84, click_gap=0.12, click_jitter_points=1.0, time_jitter_seconds=.004, scroll_amount=30, scroll_burst=4, scroll_limit=30,
                scroll_interval=0.8, energy_roi=None, energy_zero=None, expected_aspect=None,
                templates={}, points={}, slots=[], star_rois=[], order_search_roi=None)


def load(path):
    config = defaults()
    if Path(path).exists():
        config.update(json.loads(Path(path).read_text()))
    return config


def save(path, config):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix('.tmp')
    tmp.write_text(json.dumps(config, ensure_ascii=False, indent=2))
    tmp.replace(path)


def valid_rect(r):
    return (len(r) == 4 and all(math.isfinite(v) for v in r)
            and 0 <= r[0] < r[2] <= 1 and 0 <= r[1] < r[3] <= 1)


def validate(c, root):
    if c['version'] != 1:
        raise ValueError('不支援此設定版本')
    if c['settle_key'] not in KEYS or not 0 <= c['rounds'] <= 100000:
        raise ValueError('無效按鍵或次數')
    if not 0.6 <= c['threshold'] <= 0.999 or not 2 <= c['stable_frames'] <= 20:
        raise ValueError('無效辨識門檻／穩定幀數')
    if not 0 <= c.get('click_jitter_points', 1.0) <= 1.0 or not 0 <= c.get('time_jitter_seconds', .004) <= .004:
        raise ValueError('點擊偏移限 0～1 點；時間變化限 0～0.004 秒')
    for key in ('unknown_seconds', 'state_timeout', 'round_timeout', 'serve_timeout', 'delivery_timeout', 'click_gap'):
        if not math.isfinite(c[key]) or c[key] <= 0:
            raise ValueError(f'無效時間：{key}')
    if not valid_rect(c['viewport']) or (not c['slots'] and not c.get('order_search_roi')) or not all(valid_rect(r) for r in c['slots']):
        raise ValueError('請先框選遊戲內容與每位顧客的訂單區域')
    if c.get('order_search_roi') and not valid_rect(c['order_search_roi']):
        raise ValueError('顧客搜尋區域無效')
    required = {'stage_list', 'stage_entry', 'stage_ready', 'playing', 'target', 'order_marker'}
    if not c.get('star_rois'):
        required.add('three_stars')
    if not ({'settle_menu', 'confirm', 'result'} & c['templates'].keys()):
        raise ValueError('至少需要一種結算畫面模板')
    if c.get('star_rois') and (len(c['star_rois']) != 3 or not all(valid_rect(r) for r in c['star_rois'])):
        raise ValueError('必須設定三個星星區域')
    if c.get('energy_roi'):
        required.add('energy_anchor')
        if not valid_rect(c['energy_roi']) or not c.get('energy_zero') or not (Path(root)/c['energy_zero']).is_file():
            raise ValueError('活力辨識設定不完整')
    if not required <= c['templates'].keys():
        raise ValueError('尚未完成必要辨識模板：' + ', '.join(sorted(required - c['templates'].keys())))
    needed = {'start', 'cup', 'material', 'scroll'}
    if 'settle_menu' in c['templates']:
        needed.add('settle')
    if 'confirm' in c['templates']:
        needed.add('confirm')
    if 'result' in c['templates']:
        needed.add('close')
    if 'result_failed' in c['templates']:
        needed.add('failed_exit')
    if not needed <= c['points'].keys():
        raise ValueError('尚未校準操作點：' + ', '.join(sorted(needed - c['points'].keys())))
    for p in c['points'].values():
        if len(p) != 2 or not all(math.isfinite(v) and 0 <= v <= 1 for v in p):
            raise ValueError('操作點超出畫面')
    if not .75 <= c.get('order_marker_threshold', .88) <= .99 or not 1 <= c.get('delivery_confirm_frames', 2) <= 10:
        raise ValueError('訂單辨識／出餐確認設定無效')
    if not isinstance(c.get('scroll_burst', 4), int) or not 1 <= c.get('scroll_burst', 4) <= 8:
        raise ValueError('連續捲動次數無效')
    if not 1 <= abs(c['scroll_amount']) <= 30 or not 1 <= c['scroll_limit'] <= 100 or c['scroll_interval'] < .3:
        raise ValueError('捲動設定無效')
    for spec in c['templates'].values():
        if not valid_rect(spec['roi']) or not (Path(root) / spec['file']).is_file():
            raise ValueError('模板區域或檔案無效')


def load_with_preset(root, resource):
    """Install the screenshot preset only for new/unconfigured profiles."""
    import shutil
    root, resource = Path(root), Path(resource)
    path = root/'profile.json'
    config = load(path)
    if config['templates']:
        changed = upgrade_profile(config)
        if 'result_failed' not in config['templates']:
            # Existing profiles predate failure-screen handling; add only this template.
            bundled = load(resource/'profile.json')
            (root/'templates').mkdir(parents=True, exist_ok=True)
            shutil.copy2(resource/bundled['templates']['result_failed']['file'], root/bundled['templates']['result_failed']['file'])
            config['templates']['result_failed'] = bundled['templates']['result_failed']
            config['points']['failed_exit'] = bundled['points']['failed_exit']
            changed = True
        if changed:
            save(path,config)
        return config, False
    preset = load(resource/'profile.json')
    if path.exists():
        for key in ('window_id', 'rounds', 'settle_key'):
            preset[key] = config[key]
    (root/'templates').mkdir(parents=True, exist_ok=True)
    for source in (resource/'templates').glob('*.png'):
        shutil.copy2(source,root/'templates'/source.name)
    save(path,preset)
    return preset, True


def upgrade_profile(config):
    """Migrate known bundled defaults only; retain manual calibration."""
    revision = config.get('profile_revision', 0)
    if revision >= 8:
        return False
    if revision < 7:
        if config.get('slots') == [[0.11574074074074074, 0.09694415173867228, 0.3472222222222222, 0.2602739726027397], [0.3869047619047619, 0.09694415173867228, 0.5985449735449735, 0.2602739726027397], [0.6382275132275133, 0.09694415173867228, 0.7837301587301587, 0.2602739726027397]]:
            config['slots'] = [[0.12, 0.07, 0.38, 0.48], [0.38, 0.07, 0.6, 0.48], [0.6, 0.07, 0.78, 0.48]]
        if config.get('scroll_amount') == 6:
            config['scroll_amount'] = 30
        config.setdefault('scroll_burst', 4)
        if config.get('slots') == [[0.12, 0.07, 0.38, 0.48], [0.38, 0.07, 0.6, 0.48], [0.6, 0.07, 0.78, 0.48]]:
            config['order_search_roi'] = [0.01, 0.04, 0.99, 0.56]
        config['assume_target_drink'] = True
        config['delivery_timeout'] = 1.0
        config['delivery_confirm_frames'] = 1
        config['order_marker_threshold'] = .84
        if config.get('click_gap') == .45:
            config['click_gap'] = .12
    # Real bubbles over busy backgrounds score ~.87; the combo icon peaks at ~.82.
    if config.get('order_marker_threshold') == .88:
        config['order_marker_threshold'] = .84
    config['profile_revision'] = 8
    return True
