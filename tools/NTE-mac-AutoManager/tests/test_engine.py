from nte_owner.config import defaults
from nte_owner.engine import Engine, Action
from nte_owner.vision import Observation


def obs(*visible, orders=('absent',)):
    return Observation(frozenset(visible), orders, {})


def tick(e, observation, start=0, count=3):
    actions = []
    for i in range(count):
        actions += e.step(observation, start + i * .2)
    return actions


def playing(rounds=1):
    c = defaults()
    c['rounds'] = rounds
    c['assume_target_drink'] = False
    c['click_gap'] = .45
    e = Engine(c)
    assert tick(e, obs('stage_ready')) == [Action('click', 'start')]
    tick(e, obs('playing'), 1)
    assert e.state == 'playing'
    return e


def test_target_recipe_once_and_wait_for_disappearance():
    e = playing()
    actions = tick(e, obs('playing', orders=('target',)), 2, 7)
    assert actions == [Action('click', 'cup'), Action('click', 'material')]
    tick(e, obs('playing'), 3.4, 3)
    assert tick(e, obs('playing', orders=('target',)), 6, 5) == [Action('click', 'cup')]


def test_two_customers_are_serialized():
    e = playing()
    actions = tick(e, obs('playing', orders=('target', 'target')), 2, 7)
    assert actions == [Action('click', 'cup'), Action('click', 'material')]
    actions = tick(e, obs('playing', orders=('absent', 'target')), 3.4, 5)
    assert actions == [Action('click', 'cup'), Action('click', 'material')]


def test_absent_orders_never_trigger_settlement():
    e = playing()
    assert tick(e, obs('playing'), 2, 40) == []
    assert e.state == 'playing'


def test_other_order_needs_continuous_confirmation():
    e = playing()
    assert tick(e, obs('playing', orders=('other',)), 2, 4) == []
    tick(e, obs('playing'), 3, 4)
    assert tick(e, obs('playing', orders=('other',)), 4, 4) == []
    assert tick(e, obs('playing', orders=('other',)), 5, 10) == [Action('key', 'escape')]


def test_three_stars_priority_over_new_order():
    e = playing()
    assert tick(e, obs('playing', 'three_stars', orders=('target',)), 2) == [Action('key', 'escape')]
    assert e.reason == '三星'


def test_settlement_confirm_result_then_ready_counts_once():
    e = playing()
    tick(e, obs('playing', 'three_stars'), 2)
    assert tick(e, obs('stage_ready'), 3) == []  # Esc alone proves nothing.
    assert e.completed == 0
    assert tick(e, obs('settle_menu'), 4, 6) == [Action('click', 'settle')]
    assert tick(e, obs('confirm'), 6, 6) == [Action('click', 'confirm')]
    assert tick(e, obs('result'), 8, 6) == [Action('click', 'close')]
    assert tick(e, obs('stage_ready'), 10, 6) == []
    assert e.completed == e.success == 1
    assert e.stopped


def test_early_exit_and_restart_limit():
    e = playing(2)
    tick(e, obs('playing', orders=('other',)), 2, 15)
    tick(e, obs('settle_menu'), 6)
    tick(e, obs('stage_ready'), 7)
    assert e.completed == e.early == 1
    assert not e.stopped
    assert tick(e, obs('stage_ready'), 8) == [Action('click', 'start')]


def test_no_repeated_escape_on_unrecognized_menu():
    e = playing()
    tick(e, obs('playing', 'three_stars'), 2)
    assert tick(e, obs(), 3, 110) == []
    assert e.stopped and '逾時' in e.reason


def test_stop_prevents_second_recipe_click():
    e = playing()
    tick(e, obs('playing', orders=('target',)), 2)
    e.stop()
    assert tick(e, obs('playing', orders=('target',)), 3, 20) == []


def test_lost_hud_never_clicks_material():
    e = playing()
    tick(e, obs('playing', orders=('target',)), 2)
    assert tick(e, obs(orders=('target',)), 3, 20) == []


def test_stuck_order_times_out_without_retry():
    e = playing()
    actions = tick(e, obs('playing', orders=('target',)), 2, 20)
    assert actions == [Action('click', 'cup'), Action('click', 'material'), Action('key', 'escape')]
    assert e.state == 'settling' and '出餐' in e.reason


def test_whole_round_timeout_with_no_orders():
    e = playing()
    assert e.step(obs('playing'), 200) == []
    assert e.stopped


def test_scroll_until_entry_then_wait_for_confirmed_title():
    e = Engine(defaults())
    assert tick(e, obs('stage_list'), 0) == [Action('scroll', 'scroll')]
    o = Observation(frozenset({'stage_list','stage_entry'}), (), {}, {'stage_entry':(.1,.3)})
    assert tick(e, o, 1) == [Action('match', 'stage_entry')]
    assert tick(e, o, 2, 10) == []
    assert tick(e, obs('stage_list','stage_ready'), 5) == [Action('click', 'start')]


def test_scroll_is_bounded():
    c=defaults(); c['scroll_limit']=2
    e=Engine(c)
    actions=tick(e, obs('stage_list'), 0, 20)
    assert actions == [Action('scroll','scroll'),Action('scroll','scroll')]
    assert e.stopped


def test_zero_energy_prevents_start_and_claim():
    c=defaults(); c['energy_roi']=[.8,0,.9,.1]
    e=Engine(c)
    o=Observation(frozenset({'stage_ready','energy_anchor'}), (), {}, energy='zero')
    assert tick(e,o)==[]
    assert e.stopped
    e=playing(); e.c['energy_roi']=[.8,0,.9,.1]
    tick(e,obs('playing','three_stars'),2)
    o=Observation(frozenset({'result','energy_anchor'}), (), {}, energy='zero')
    assert tick(e,o,3)==[]
    assert e.stopped


def test_unreadable_energy_never_claims():
    e=playing();e.c['energy_roi']=[.8,0,.9,.1]
    tick(e,obs('playing','three_stars'),2)
    o=Observation(frozenset({'result'}), (), {}, energy='unreadable')
    assert tick(e,o,3,10)==[]


def test_any_original_customer_can_receive_and_next_recipe_runs():
    e = playing()
    both = obs('playing', orders=('target', 'target', 'absent'))
    assert tick(e, both, 2, 6) == [Action('click', 'cup'), Action('click', 'material')]
    # Game serves customer 1 although the controller chose customer 0.
    assert e.step(obs('playing', orders=('target', 'absent', 'absent')), 3.2) == []
    assert e.delivered == 1 and e.busy is None
    assert e.step(both, 3.4) == [Action('click', 'cup')]
    assert e.step(both, 4.0) == [Action('click', 'material')]
    assert e.step(obs('playing', orders=('absent', 'target', 'absent')), 4.2) == []
    assert e.delivered == 2
    assert e.step(both, 4.4) == [Action('click', 'cup')]


def test_deadline_is_one_second_after_material_release():
    e = playing()
    same = obs('playing', orders=('target', 'absent'))
    tick(e, same, 2, 6)
    e.action_completed(Action('click', 'material'), 3.25)
    assert e.step(same, 4.24) == []
    assert e.step(same, 4.25) == [Action('key', 'escape')]
    assert e.step(same, 4.5) == []
    assert e.delivered == 0  # The already absent slot is not a completion.


def test_fast_mode_first_order_frame_returns_entire_recipe():
    c=defaults();e=Engine(c);e.enter('playing',0)
    o=obs('playing',orders=('target','absent'))
    assert e.step(o,.1)==[Action('click','cup'),Action('click','material')]
    e.action_completed(Action('click','material'),.3)
    assert e.step(o,.4)==[]
    # A different customer may receive the next recipe too.
    assert e.step(obs('playing',orders=('absent','target')),.5)==[Action('click','cup'),Action('click','material')]
    assert e.step(obs('playing',orders=('absent','target')),.6)==[]
    assert e.delivered==1


def test_fast_mode_no_hud_or_order_never_cooks():
    e=Engine(defaults());e.enter('playing',0)
    assert e.step(obs(orders=('target',)),.1)==[]
    assert e.step(obs('playing'),.2)==[]


def test_first_playing_frame_with_order_cooks_without_another_capture():
    e=Engine(defaults());e.enter('starting',0)
    assert e.step(obs('playing',orders=('target',)),.1)==[Action('click','cup'),Action('click','material')]


def test_two_visible_orders_batch_then_escape_on_second_material_release():
    e=Engine(defaults());e.enter('playing',0)
    pair=[Action('click','cup'),Action('click','material')]
    assert e.step(obs('playing',orders=('target','target','target')),.1)==pair*2
    assert e.recipes_sent==0 and e.state=='playing'
    assert e.action_completed(pair[1],.3)==[]
    assert e.action_completed(pair[1],.5)==[Action('key','escape')]
    assert e.state=='settling' and e.recipes_sent==2
    assert e.step(obs('playing',orders=('target','target')),.6)==[]


def test_second_order_arrives_later_only_one_more_recipe_then_escape():
    e=Engine(defaults());e.enter('playing',0)
    pair=[Action('click','cup'),Action('click','material')]
    assert e.step(obs('playing',orders=('target','absent')),.1)==pair
    assert e.action_completed(pair[1],.3)==[]
    assert e.step(obs('playing',orders=('absent','target','target')),.5)==pair
    assert e.action_completed(pair[1],.7)==[Action('key','escape')]
    # On restart the counter is per-round.
    e.enter('starting',2)
    assert e.step(obs('playing',orders=('target','target')),2.1)==pair*2
    assert e.recipes_sent==0
