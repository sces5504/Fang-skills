import cv2
import numpy as np
import pytest
from nte_owner.config import defaults
from nte_owner.vision import Vision, normalize, crop


def test_presence_is_required_and_slots_are_independent(tmp_path):
    rng = np.random.default_rng(9)
    target = rng.integers(0, 255, (25, 25, 3), dtype=np.uint8)
    marker = rng.integers(0, 255, (12, 20, 3), dtype=np.uint8)
    cv2.imwrite(str(tmp_path / 'target.png'), target)
    cv2.imwrite(str(tmp_path / 'marker.png'), marker)
    c = defaults()
    c['templates'] = {k: dict(file=f, roi=[0,0,1,1]) for k, f in [('target', 'target.png'), ('order_marker', 'marker.png')]}
    c['slots'] = [[0,0,.5,1], [.5,0,1,1]]
    c['assume_target_drink'] = False
    vision = Vision(c, tmp_path)
    frame = np.zeros((150,300,3), np.uint8)
    frame[30:55,30:55] = target
    assert vision.observe(frame).orders == ('absent', 'absent')
    frame[65:77,30:50] = marker
    frame[65:77,200:220] = marker
    assert vision.observe(frame).orders == ('target', 'other')
    frame[30:55,200:225] = target
    assert vision.observe(frame).orders == ('target', 'target')


def test_retina_normalization_and_wrong_aspect():
    assert normalize(np.zeros((1800,3200,3), np.uint8)).shape == (1080,1920,3)
    with pytest.raises(ValueError, match='16:9'):
        normalize(np.zeros((1000,1000,3), np.uint8))


def test_blank_template_rejected(tmp_path):
    cv2.imwrite(str(tmp_path/'blank.png'), np.zeros((20,20,3), np.uint8))
    c = defaults()
    c['templates'] = {'target': dict(file='blank.png', roi=[0,0,1,1])}
    with pytest.raises(ValueError):
        Vision(c, tmp_path)
