"""Offline recognizer: no capture, no input, no game changes.
Example: python scripts/replay.py --profile /path/profile.json screenshot.png
"""
import argparse
import json
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import cv2
from nte_owner.config import load
from nte_owner.vision import Vision, prepare

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--profile',type=Path,required=True)
parser.add_argument('images',nargs='+',type=Path)
args=parser.parse_args()
config=load(args.profile)
vision=Vision(config,args.profile.parent)
for path in args.images:
    frame=cv2.imread(str(path))
    if frame is None:
        parser.error(f'Cannot read {path}')
    observation=vision.observe(prepare(frame,config)[0])
    print(json.dumps(dict(image=path.name,visible=sorted(observation.visible),orders=observation.orders,
                          energy=observation.energy,scores=observation.scores),ensure_ascii=False))
