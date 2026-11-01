from dataclasses import dataclass, field
from pathlib import Path
import cv2
import numpy as np

SIZE = (1920, 1080)


def crop(frame, roi):
    h, w = frame.shape[:2]
    x1, y1, x2, y2 = roi
    return frame[round(y1*h):round(y2*h), round(x1*w):round(x2*w)]


def normalize(frame):
    h, w = frame.shape[:2]
    if not (1.5 <= w / h <= 1.85):
        raise ValueError('支援 16:9／16:10 遊戲內容；請排除標題列與黑邊')
    return cv2.resize(frame, (1920, round(1920*h/w)), interpolation=cv2.INTER_AREA)


@dataclass(frozen=True)
class Observation:
    visible: frozenset
    orders: tuple  # absent / target / other
    scores: dict
    locations: dict = field(default_factory=dict)
    energy: str | None = None  # zero / positive / unreadable


class Vision:
    def __init__(self, config, root):
        self.c = config
        self.templates = {}
        self.root = Path(root)
        self.order_tracks = {}
        for key, spec in config['templates'].items():
            img = cv2.imread(str(Path(root) / spec['file']))
            if img is None or min(img.shape[:2]) < 4 or float(img.std()) < 3:
                raise ValueError(f'模板 {key} 無法使用；請選擇有細節的區域')
            self.templates[key] = img

    def match(self, frame, key, roi=None):
        if key not in self.templates:
            return 0.0, None
        roi = roi or self.c['templates'][key]['roi']
        region = crop(frame, roi)
        template = self.templates[key]
        if self.c['templates'][key].get('grayscale'):
            template = cv2.cvtColor(template, cv2.COLOR_BGR2GRAY)
            region = cv2.cvtColor(region, cv2.COLOR_BGR2GRAY)
        best, center = 0.0, None
        for scale in ((.85,.90,.95,.975,1.,1.025,1.05,1.075,1.10,1.125,1.15,1.20) if key == 'target' else (.90,.95,1.,1.05,1.10)):
            t = cv2.resize(template, None, fx=scale, fy=scale)
            if t.shape[0] > region.shape[0] or t.shape[1] > region.shape[1]:
                continue
            _, score, _, loc = cv2.minMaxLoc(cv2.matchTemplate(region, t, cv2.TM_CCOEFF_NORMED))
            if np.isfinite(score) and score > best:
                best = float(score)
                center = (roi[0] + (loc[0]+t.shape[1]/2)/frame.shape[1],
                          roi[1] + (loc[1]+t.shape[0]/2)/frame.shape[0])
        return best, center

    def score(self, frame, key, roi=None):
        return self.match(frame, key, roi)[0]

    def observe(self, frame, context=None):
        keys = set(self.templates)-{'target','order_marker'}
        if context in ('starting','playing'):
            keys &= {'playing','three_stars'}
        elif context == 'ready':
            keys &= {'stage_list','stage_entry','stage_ready','energy_anchor'}
        elif context == 'settling':
            keys &= {'result','result_failed','confirm','settle_menu','stage_list','stage_ready','energy_anchor'}
        matches = {k:self.match(frame,k) for k in keys}
        scores = {k:v[0] for k,v in matches.items()}
        visible = {k for k, v in scores.items() if v >= self.c['templates'][k].get('threshold', self.c['threshold'])}
        locations = {}
        if 'stage_entry' in visible:
            locations['stage_entry'] = matches['stage_entry'][1]
        if self.c.get('star_rois') and not self.c.get('assume_target_drink'):
            ratios = []
            for i, roi in enumerate(self.c['star_rois']):
                hsv = cv2.cvtColor(crop(frame, roi), cv2.COLOR_BGR2HSV)
                ratio = float(np.mean(cv2.inRange(hsv, (18, 130, 170), (40, 255, 255)) > 0))
                ratios.append(ratio)
                scores[f'star_{i}'] = ratio
            if all(r > .30 for r in ratios):
                visible.add('three_stars')
        energy = None
        if self.c.get('energy_roi'):
            energy = self.energy(frame, matches['energy_anchor'][1]) if 'energy_anchor' in visible else 'unreadable'
        orders = []
        if self.c.get('order_search_roi'):
            if 'playing' in visible and context in (None, 'starting', 'playing'):
                orders, order_scores, order_locations = self.dynamic_orders(frame)
                scores.update(order_scores)
                locations.update(order_locations)
            else:
                orders = ['absent']*8
                if context in ('ready', 'starting', 'settling'):
                    self.order_tracks.clear()
        else:
            for i, roi in enumerate(self.c['slots']):
                if context not in (None, 'playing') or (context == 'playing' and 'playing' not in visible):
                    orders.append('absent')
                    continue
                present = self.score(frame, 'order_marker', roi)
                target = self.score(frame, 'target', roi)
                scores[f'order_{i}'] = present
                scores[f'target_{i}'] = target
                orders.append('absent' if present < self.c['threshold'] else
                              'target' if self.c.get('assume_target_drink', False) or target >= self.c['threshold'] else 'other')
        return Observation(frozenset(visible), tuple(orders), scores, locations, energy)

    def dynamic_orders(self, frame):
        """Find bubbles throughout the customer area, then classify locally.

        Spatial tracks retain identity across moving bubbles; output indices are
        track identities, not hard-coded customer rectangles.
        """
        roi = self.c['order_search_roi']
        region = crop(frame, roi)
        h, w = frame.shape[:2]
        template = self.templates['order_marker']
        candidates = []
        small_region = cv2.cvtColor(cv2.resize(region, None, fx=.5, fy=.5, interpolation=cv2.INTER_AREA), cv2.COLOR_BGR2GRAY)
        for scale in (.85, .90, .95, 1., 1.05, 1.10, 1.125, 1.15, 1.20):
            t = cv2.resize(template,None,fx=scale,fy=scale)
            if t.shape[0] > region.shape[0] or t.shape[1] > region.shape[1]:
                continue
            small_t = cv2.cvtColor(cv2.resize(t, None, fx=.5, fy=.5, interpolation=cv2.INTER_AREA), cv2.COLOR_BGR2GRAY)
            heat = cv2.matchTemplate(small_region,small_t,cv2.TM_CCOEFF_NORMED)
            for _ in range(12):
                _, score, _, loc = cv2.minMaxLoc(heat)
                if not np.isfinite(score) or score < .78:
                    break
                sx,sy = loc
                x,y = sx*2,sy*2
                x0,y0 = max(0,x-4),max(0,y-4)
                local = region[y0:y+t.shape[0]+5,x0:x+t.shape[1]+5]
                if local.shape[0] >= t.shape[0] and local.shape[1] >= t.shape[1]:
                    _,full_score,_,pos = cv2.minMaxLoc(cv2.matchTemplate(local,t,cv2.TM_CCOEFF_NORMED))
                    if full_score >= self.c.get('order_marker_threshold', .88):
                        candidates.append((full_score,(round(roi[0]*w)+x0+pos[0]+t.shape[1]/2,
                                                       round(roi[1]*h)+y0+pos[1]+t.shape[0]/2)))
                dx,dy = max(10,small_t.shape[1]),max(10,small_t.shape[0])
                heat[max(0,sy-dy):sy+dy+1,max(0,sx-dx):sx+dx+1] = -1
        detections=[]
        for score,center in sorted(candidates,reverse=True):
            if all(np.linalg.norm(np.subtract(center,p)) > 35 for _,p in detections):
                detections.append((score,center))
        if len(detections)>8:
            raise ValueError('訂單氣泡候選過多，停止以避免誤判')
        for track in self.order_tracks.values():
            track['missed'] += 1
        pairs=[]
        for d,(_,center) in enumerate(detections):
            for slot,track in self.order_tracks.items():
                distance=float(np.linalg.norm(np.subtract(center,track['center'])))
                if distance < 120:
                    pairs.append((distance,d,slot))
        assigned={}; used=set()
        for _,d,slot in sorted(pairs):
            if d not in assigned and slot not in used:
                assigned[d]=slot;used.add(slot)
        for d in range(len(detections)):
            if d in assigned:
                continue
            available=[i for i in range(8) if i not in used and
                       (i not in self.order_tracks or self.order_tracks[i]['missed'] > self.c['stable_frames'])]
            if not available:
                raise ValueError('訂單位置變化過大，停止以避免重複出餐')
            assigned[d]=available[0];used.add(available[0])
        orders=['absent']*8; scores={}; locations={}
        th,tw = self.templates['target'].shape[:2]
        for d,(present,(x,y)) in enumerate(detections):
            slot=assigned[d]
            self.order_tracks[slot]={'center':(x,y),'missed':0}
            local=[max(0,(x-tw*1.3)/w),max(0,(y-th*1.9)/h),
                   min(1,(x+tw*1.3)/w),min(1,(y-4)/h)]
            target=0.0 if self.c.get('assume_target_drink') else self.score(frame,'target',local)
            orders[slot]='target' if self.c.get('assume_target_drink', False) or target >= self.c['threshold'] else 'other'
            scores[f'order_{slot}']=present;scores[f'target_{slot}']=target
            locations[f'order_{slot}']=(x/w,y/h)
        return orders,scores,locations

    def energy(self, frame, anchor_center=None):
        roi = list(self.c['energy_roi'])
        if self.c.get('energy_anchor_center'):
            center = anchor_center or self.match(frame, 'energy_anchor')[1]
            if center is None:
                return 'unreadable'
            dx, dy = (center[i]-self.c['energy_anchor_center'][i] for i in (0,1))
            roi = [roi[0]+dx,roi[1]+dy,roi[2]+dx,roi[3]+dy]
            if min(roi)<0 or max(roi)>1:
                return 'unreadable'
        patch = crop(frame, roi)
        mask = cv2.inRange(patch, (210,210,210), (255,255,255))
        n, labels, stats, _ = cv2.connectedComponentsWithStats(mask)
        glyphs = []
        for x,y,w,h,area in stats[1:]:
            if area >= 12 and h >= mask.shape[0]*.40:
                glyphs.append(mask[y:y+h,x:x+w])
        if not 1 <= len(glyphs) <= 3:
            return 'unreadable'
        if len(glyphs) > 1:
            return 'positive'
        zero = cv2.imread(str(self.root / self.c['energy_zero']), cv2.IMREAD_GRAYSCALE)
        if zero is None:
            return 'unreadable'
        target = cv2.resize(zero, (24,40)) > 127
        glyph = cv2.resize(glyphs[0], (24,40)) > 127
        overlap = np.logical_and(target,glyph).sum() / max(1,np.logical_or(target,glyph).sum())
        return 'zero' if overlap > .80 else 'positive'


class FrameNotReady(ValueError):
    """A black/fading transition has no usable viewport yet."""


def prepare(frame, config):
    """Return canonical pixels and the exact window-relative input viewport."""
    viewport = list(config['viewport'])
    region = crop(frame, viewport)
    if config.get('auto_trim', True):
        rows = np.mean(np.max(region, axis=2) > 10, axis=1)
        nonblack = np.where(rows > .05)[0]
        if not len(nonblack):
            raise FrameNotReady('畫面全黑，等待轉場')
        top, bottom = int(nonblack[0]), int(nonblack[-1])+1
        if not 1.5 <= region.shape[1] / (bottom-top) <= 1.85:
            raise FrameNotReady('轉場尚未顯示完整遊戲畫面')
        height = region.shape[0]
        y1, y2 = viewport[1], viewport[3]
        viewport[1] = y1 + (y2-y1)*top/height
        viewport[3] = y1 + (y2-y1)*bottom/height
        region = region[top:bottom]
    return normalize(region), viewport
