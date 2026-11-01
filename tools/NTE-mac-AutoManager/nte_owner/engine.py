"""Pure, deterministic controller. No OS calls, sleeps, or wall clock."""
from dataclasses import dataclass


@dataclass(frozen=True)
class Action:
    kind: str
    name: str


class Engine:
    def __init__(self, config, now=0.0):
        self.c = config
        self.state = 'ready'
        self.since = now
        self.round_since = now
        self.completed = self.success = self.early = 0
        self.reason = ''
        self.streak = {}
        self.order_streak = {}
        self.other_since = {}
        self.busy = None
        self.pending_orders = set()
        self.delivery_absent = {}
        self.delivered = 0
        self.recipes_sent = 0
        self.two_order_rounds = 0
        self.latched = set()
        self.settle_seen = set()
        self.failed_exit_at = None
        self.stopped = False
        self.scrolls = 0
        self.last_scroll = -100.0
        self.selecting = False
        self.energy_last, self.energy_count = None, 0
        self.last_hud = now

    def stop(self, reason='使用者停止'):
        self.stopped = True
        self.reason = reason
        self.state = 'stopped'
        return []

    def enter(self, state, now):
        self.state, self.since = state, now
        self.streak.clear()
        self.order_streak.clear()

    def suspend_time(self, seconds):
        """Exclude unavailable screen/loading time from action deadlines."""
        self.since += seconds
        self.round_since += seconds
        self.last_hud += seconds
        if self.last_scroll >= 0:
            self.last_scroll += seconds
        if self.busy:
            slot, phase, stamp = self.busy
            self.busy = (slot, phase, stamp + seconds)
        self.other_since = {k: stamp+seconds for k, stamp in self.other_since.items()}
        self.streak.clear()
        self.order_streak.clear()

    def action_completed(self, action, now):
        # Count actual material releases, not merely planned recipes.
        if action == Action("click", "material"):
            self.recipes_sent += 1
            if self.c.get('assume_target_drink') and self.recipes_sent >= 2:
                return self.settle(now, '已送出兩單')
            if self.busy and self.busy[1] == 'served':
                self.busy = (self.busy[0], 'served', now)
        return []

    def step(self, obs, now):
        if self.stopped:
            return []
        self.energy_count = self.energy_count + 1 if obs.energy == self.energy_last else 1
        self.energy_last = obs.energy
        confirmations = 1 if self.c.get('assume_target_drink') else self.c['stable_frames']
        energy_stable = self.energy_count >= confirmations
        for k in set(self.streak) | set(obs.visible):
            self.streak[k] = self.streak.get(k, 0) + 1 if k in obs.visible else 0
        stable = {k for k, n in self.streak.items() if n >= confirmations}
        for i, order in enumerate(obs.orders):
            previous, count = self.order_streak.get(i, ('', 0))
            self.order_streak[i] = (order, count + 1 if previous == order else 1)
        orders = {i: kind for i, (kind, n) in self.order_streak.items() if n >= self.c['stable_frames']}
        if self.c.get('assume_target_drink'):
            orders = {i: kind for i, kind in enumerate(obs.orders)}
        if self.state != 'playing' and now - self.since > self.c['state_timeout']:
            return self.stop(f'{self.state} 畫面確認逾時')
        if self.state == 'ready':
            if self.c.get('energy_roi') and obs.energy == 'zero' and energy_stable and 'energy_anchor' in stable:
                return self.stop('活力已歸零')
            if self.c.get('energy_roi') and (obs.energy != 'positive' or not energy_stable or 'energy_anchor' not in stable):
                return []
            if 'stage_ready' in stable:
                self.enter('starting', now)
                return [Action('click', 'start')]
            if 'stage_list' in stable and not self.selecting:
                if 'stage_entry' in stable and obs.locations.get('stage_entry') and now-self.last_scroll >= self.c['scroll_interval']:
                    self.selecting = True
                    self.since = now
                    return [Action('match', 'stage_entry')]
                if 'stage_entry' not in obs.visible and now-self.last_scroll >= self.c['scroll_interval']:
                    if self.scrolls >= self.c['scroll_limit']:
                        return self.stop('向上捲動後仍找不到 1-1')
                    self.scrolls += 1
                    self.last_scroll = now
                    return [Action('scroll', 'scroll')]
        elif self.state == 'starting':
            if 'playing' in obs.visible and (self.c.get('assume_target_drink') or 'playing' in stable):
                self.last_hud = now
                self.round_since = now
                self.recipes_sent = 0
                self.enter('playing', now)
                if self.c.get('assume_target_drink'):
                    return self.step(obs, now)
        elif self.state == 'playing':
            if now - self.round_since > self.c['round_timeout']:
                return self.stop('單局逾時')
            if 'playing' in obs.visible:
                self.last_hud = now
            if now - self.last_hud > self.c['state_timeout']:
                return self.stop('營業畫面無法辨識，已逾時')
            if 'playing' not in obs.visible or (not self.c.get('assume_target_drink') and 'playing' not in stable):
                # No input on an unrecognized screen, including the second recipe click.
                return []
            if 'three_stars' in stable and not self.c.get('assume_target_drink'):
                return self.settle(now, '三星')
            for i, kind in orders.items():
                if kind == 'other':
                    self.other_since.setdefault(i, now)
                    if now - self.other_since[i] >= self.c['unknown_seconds']:
                        return self.settle(now, '非目標訂單')
                else:
                    self.other_since.pop(i, None)
                if kind == 'absent':
                    self.latched.discard(i)
            # Require continuous other-order evidence, not separated glimpses.
            for i in list(self.other_since):
                if orders.get(i) != 'other':
                    self.other_since.pop(i)
            if self.busy:
                slot, phase, stamp = self.busy
                if phase == 'served':
                    for candidate in self.pending_orders:
                        missing = candidate < len(obs.orders) and obs.orders[candidate] == 'absent'
                        self.delivery_absent[candidate] = self.delivery_absent.get(candidate, 0)+1 if missing else 0
                    if any(n >= self.c.get('delivery_confirm_frames', 1) for n in self.delivery_absent.values()):
                        self.delivered += 1
                        self.latched.discard(slot)
                        self.busy = None
                        self.pending_orders.clear()
                        self.delivery_absent.clear()
                        if self.c.get('assume_target_drink'):
                            return self.step(obs, now)
                        return []
                    if now-stamp >= self.c.get('delivery_timeout', 1.0):
                        return self.settle(now, '出餐後未完成訂單')
                elif now-stamp > self.c['serve_timeout']:
                    return self.settle(now, '製作等待逾時')
                if phase == 'cup' and now - stamp >= self.c['click_gap']:
                    if orders.get(slot) == 'target':
                        self.pending_orders = {i for i, kind in enumerate(obs.orders) if kind != 'absent'}
                        self.delivery_absent.clear()
                        self.busy = (slot, 'served', now)
                        return [Action('click', 'material')]
                return []
            for slot, kind in orders.items():
                if kind == 'target' and slot not in self.latched:
                    self.latched.add(slot)
                    if self.c.get('assume_target_drink'):
                        self.pending_orders = {i for i, kind in enumerate(obs.orders) if kind != 'absent'}
                        self.delivery_absent.clear()
                        self.busy = (slot, 'served', now)
                        count = min(sum(k == 'target' for k in obs.orders), 2-self.recipes_sent)
                        return [Action('click', 'cup'), Action('click', 'material')] * count
                    self.busy = (slot, 'cup', now)
                    return [Action('click', 'cup')]
        elif self.state == 'settling':
            if self.c.get('energy_roi') and 'energy_anchor' in stable and obs.energy == 'zero' and energy_stable:
                return self.stop('活力已歸零')
            if 'result_failed' in stable:
                # No energy HUD here, and 'close' would land on 重新挑戰. Retry in case a click lands mid-fade.
                if self.failed_exit_at is None or now-self.failed_exit_at >= 2.0:
                    if self.failed_exit_at is None:
                        self.since = now
                    self.failed_exit_at = now
                    self.settle_seen.add('result_failed')
                    return [Action('click', 'failed_exit')]
                return []
            if 'result' in stable and self.c.get('energy_roi') and (obs.energy != 'positive' or not energy_stable or 'energy_anchor' not in stable):
                return []
            # One click per recognized settlement screen. No blind retries.
            for screen, button in (('result', 'close'), ('confirm', 'confirm'), ('settle_menu', 'settle')):
                if screen in stable and screen not in self.settle_seen:
                    self.settle_seen.add(screen)
                    self.since = now
                    self.streak.clear()
                    return [Action('click', button)]
            if ('stage_list' in stable or 'stage_ready' in stable) and self.settle_seen:
                self.completed += 1
                if self.reason == '三星':
                    self.success += 1
                elif self.reason == '已送出兩單':
                    self.two_order_rounds += 1
                else:
                    self.early += 1
                if self.c['rounds'] and self.completed >= self.c['rounds']:
                    return self.stop('已完成指定次數')
                self.busy = None
                self.scrolls = 0
                self.selecting = False
                self.last_scroll = -100.0
                self.latched.clear()
                self.other_since.clear()
                self.enter('ready', now)
        return []

    def settle(self, now, reason):
        self.reason = reason
        self.pending_orders.clear()
        self.delivery_absent.clear()
        self.busy = None
        self.settle_seen.clear()
        self.failed_exit_at = None
        self.enter('settling', now)
        return [Action('key', self.c['settle_key'])]
