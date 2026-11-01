from pathlib import Path
import cv2
import numpy as np
from nte_owner.config import load, validate
from nte_owner.vision import Vision, prepare

ROOT = Path(__file__).resolve().parents[1] / 'nte_owner/assets/preset'


def test_shipped_profile_is_complete():
    c = load(ROOT/'profile.json')
    validate(c,ROOT)
    Vision(c,ROOT)
    assert c['rounds'] == 1
    assert len(c['star_rois']) == 3
    assert c['energy_roi']


def test_letterbox_input_transform():
    c = load(ROOT/'profile.json')
    raw = np.ones((1964,3024,3),np.uint8)*40
    raw[:66] = 0
    frame,viewport=prepare(raw,c)
    assert frame.shape[1] == 1920
    assert viewport == [0,66/1964,1,1]
    assert abs(frame.shape[1]/frame.shape[0] - 3024/1898) < .002


def test_first_launch_installs_preset_without_calibration(tmp_path):
    from nte_owner.config import load_with_preset, save
    c, installed = load_with_preset(tmp_path, ROOT)
    assert installed
    validate(c,tmp_path)
    assert c['points']['cup'] and c['points']['material']
    c['threshold']=.93
    save(tmp_path/'profile.json',c)
    again, installed=load_with_preset(tmp_path,ROOT)
    assert not installed
    assert again['threshold']==.93


def test_empty_old_profile_is_upgraded_without_losing_window(tmp_path):
    from nte_owner.config import load_with_preset, save, defaults
    c=defaults();c['window_id']=123
    save(tmp_path/'profile.json',c)
    c,installed=load_with_preset(tmp_path,ROOT)
    assert installed and c['window_id']==123
    validate(c,tmp_path)


def test_legacy_order_bounds_migrate_but_custom_regions_survive():
    from nte_owner.config import defaults, upgrade_profile
    c=defaults()
    c['slots']=[[x1/3024,184/1898,x2/3024,494/1898]
                for x1,x2 in [(350,1050),(1170,1810),(1930,2370)]]
    c['scroll_amount']=6
    assert upgrade_profile(c)
    assert c['slots'][2]==[.60,.07,.78,.48]
    assert c['scroll_amount']==30
    custom=defaults();custom['slots']=[[.2,.1,.4,.5]]
    upgrade_profile(custom)
    assert custom['slots']==[[.2,.1,.4,.5]]
