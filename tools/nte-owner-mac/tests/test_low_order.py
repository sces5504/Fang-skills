import json
from pathlib import Path
import cv2
import numpy as np
from nte_owner.config import load
from nte_owner.vision import Vision
from nte_owner.engine import Engine


def test_real_low_customer_order_triggers_recipe_once():
    root=Path(__file__).resolve().parents[1]/'nte_owner/assets/preset'
    fixtures=Path(__file__).parent/'fixtures'
    meta=json.loads((fixtures/'low_order.json').read_text())
    frame=np.zeros(meta['shape'],np.uint8)
    for key,file in [('bubble','low_order_bubble.png'),('hud','playing_hud.png')]:
        patch=cv2.imread(str(fixtures/file));x,y=meta[key]
        frame[y:y+patch.shape[0],x:x+patch.shape[1]]=patch
    c=load(root/'profile.json');o=Vision(c,root).observe(frame,context='playing')
    assert o.orders.count('target')==1 and o.orders.count('other')==0
    c['assume_target_drink']=False;c['click_gap']=.45
    e=Engine(c);e.enter('starting',0);actions=[]
    for i in range(12):
        actions+=e.step(o,i*.2)
    assert [(a.kind,a.name) for a in actions]==[('click','cup'),('click','material')]


def dynamic_fixture():
    root=Path(__file__).resolve().parents[1]/'nte_owner/assets/preset'
    fixtures=Path(__file__).parent/'fixtures'
    meta=json.loads((fixtures/'low_order.json').read_text())
    frame=np.zeros(meta['shape'],np.uint8)
    hud=cv2.imread(str(fixtures/'playing_hud.png'));x,y=meta['hud']
    frame[y:y+hud.shape[0],x:x+hud.shape[1]]=hud
    return load(root/'profile.json'),root,frame,cv2.imread(str(fixtures/'low_order_bubble.png'))


def place(frame,patch,x,y):
    frame=frame.copy()
    frame[y:y+patch.shape[0],x:x+patch.shape[1]]=patch
    return frame


def test_detects_orders_across_full_customer_area():
    c,root,base,bubble=dynamic_fixture()
    for x,y in [(30,80),(550,160),(1000,350),(1760,520)]:
        o=Vision(c,root).observe(place(base,bubble,x,y),context='playing')
        assert o.orders.count('target')==1, (x,y,o)
        assert o.orders.count('other')==0


def test_multiple_orders_keep_identity_when_one_disappears():
    c,root,base,bubble=dynamic_fixture();v=Vision(c,root)
    both=place(place(base,bubble,300,220),bubble,1250,400)
    a=v.observe(both,context='playing')
    assert a.orders.count('target')==2
    right=next(int(k.split('_')[1]) for k,p in a.locations.items() if k.startswith('order_') and p[0]>.5)
    b=v.observe(place(base,bubble,1290,420),context='playing')
    assert b.orders[right]=='target' and b.orders.count('target')==1


def test_unknown_drink_is_classified_locally_not_by_nearby_target():
    c,root,base,bubble=dynamic_fixture();c['assume_target_drink']=False;v=Vision(c,root)
    unknown=bubble.copy();unknown[:100]=0
    frame=place(place(base,bubble,300,220),unknown,1250,400)
    o=v.observe(frame,context='playing')
    assert o.orders.count('target')==1
    assert o.orders.count('other')==1


def test_drinks_on_counter_outside_customer_area_are_ignored():
    c,root,base,bubble=dynamic_fixture()
    o=Vision(c,root).observe(place(base,bubble,1200,800),context='playing')
    assert set(o.orders)=={'absent'}


def test_default_serves_even_when_drink_icon_is_unrecognized():
    c,root,base,bubble=dynamic_fixture()
    bubble[:100]=0
    o=Vision(c,root).observe(place(base,bubble,300,220),context='playing')
    assert o.orders.count('target')==1 and 'other' not in o.orders


def test_three_real_orders_from_failed_run_are_all_served_candidates():
    c,root,frame,_=dynamic_fixture()
    fixtures=Path(__file__).parent/'fixtures'
    for name,x,y in [('left',610,245),('middle',895,245),('right',1200,225)]:
        frame=place(frame,cv2.imread(str(fixtures/('three_orders_'+name+'.png'))),x,y)
    o=Vision(c,root).observe(frame,context='playing')
    assert o.orders.count('target')==3 and 'other' not in o.orders


def test_faint_bubble_over_busy_background_is_detected_but_combo_icon_is_not():
    # Real frame: the bubble scored .872 against the old .88 threshold and was skipped.
    c,root,frame,_=dynamic_fixture()
    bubble=cv2.imread(str(Path(__file__).parent/'fixtures'/'faint_order_bubble.png'))
    orders,_,_=Vision(c,root).dynamic_orders(place(frame,bubble,890,300))
    assert orders.count('target')==1
    assert Vision(c,root).dynamic_orders(frame)[0].count('target')==0


def test_profile_revision_8_lowers_only_default_order_threshold():
    from nte_owner.config import defaults, upgrade_profile
    c=defaults();c['profile_revision']=7;c['order_marker_threshold']=.88
    assert upgrade_profile(c) and c['order_marker_threshold']==.84 and c['profile_revision']==8
    custom=defaults();custom['profile_revision']=7;custom['order_marker_threshold']=.9
    upgrade_profile(custom)
    assert custom['order_marker_threshold']==.9
