import json
from pathlib import Path
import cv2
import numpy as np
from nte_owner.config import load, load_with_preset, validate
from nte_owner.engine import Action, Engine
from nte_owner.vision import Observation, Vision

ROOT = Path(__file__).resolve().parents[1]/'nte_owner/assets/preset'
NO_ORDERS = ('absent',)*8


def settling_engine():
    c = load(ROOT/'profile.json')
    c['rounds'] = 0
    e = Engine(c)
    e.settle(0, '已送出兩單')
    return e


def seen(*visible, energy='unreadable'):
    return Observation(frozenset(visible), NO_ORDERS, {}, {}, energy)


def test_real_failed_title_is_recognized_only_on_failure_screen():
    c = load(ROOT/'profile.json')
    frame = np.zeros((1205, 1920, 3), np.uint8)
    assert 'result_failed' not in Vision(c, ROOT).observe(frame, context='settling').visible
    patch = cv2.imread(str(Path(__file__).parent/'fixtures/failed_title.png'))
    frame[180:180+patch.shape[0], 768:768+patch.shape[1]] = patch
    assert 'result_failed' in Vision(c, ROOT).observe(frame, context='settling').visible


def test_failed_screen_clicks_exit_without_energy_then_continues():
    e = settling_engine()
    assert e.step(seen('result', 'result_failed'), 1) == [Action('click', 'failed_exit')]
    assert e.step(seen('stage_list'), 2) == []
    assert e.completed == 1 and e.state == 'ready'


def test_failed_exit_retries_while_screen_remains():
    e = settling_engine()
    assert e.step(seen('result_failed'), 1) == [Action('click', 'failed_exit')]
    assert e.step(seen('result_failed'), 2) == []
    assert e.step(seen('result_failed'), 3) == [Action('click', 'failed_exit')]
    assert e.step(seen('result_failed'), 30) == [Action('click', 'failed_exit')]
    assert e.state == 'settling'
    # Retries do not extend the screen timeout, so a stuck screen still stops.
    assert e.step(seen('result_failed'), 50) == [] and e.stopped


def test_normal_result_still_waits_for_energy_and_uses_close():
    e = settling_engine()
    assert e.step(seen('result'), 1) == []
    assert e.step(seen('result', 'energy_anchor', energy='positive'), 2) == [Action('click', 'close')]


def test_existing_profile_gains_failed_screen_and_keeps_its_values(tmp_path):
    c = load(ROOT/'profile.json')
    del c['templates']['result_failed'], c['points']['failed_exit']
    c['rounds'] = 7
    (tmp_path/'profile.json').write_text(json.dumps(c))
    (tmp_path/'templates').mkdir()
    for source in (ROOT/'templates').glob('*.png'):
        if source.name != 'result_failed.png':
            (tmp_path/'templates'/source.name).write_bytes(source.read_bytes())
    loaded, installed = load_with_preset(tmp_path, ROOT)
    assert not installed and loaded['rounds'] == 7
    assert loaded['points']['failed_exit'] == [.3955, .746]
    assert json.loads((tmp_path/'profile.json').read_text())['templates']['result_failed']['threshold'] == .85
    validate(loaded, tmp_path)
