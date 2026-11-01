# Source and attribution

This standalone macOS port is distributed under GPL-3.0-only; see LICENSE.
Reference project: BnanZ0/ok-nte, https://github.com/BnanZ0/ok-nte
Inspected revision: 893525d5c62eb86fb596956b85d3f136e0209918.

The control flow was informed by src/tasks/OwnerSelectionTask.py and
src/tasks/BaseNTETask.py. The macOS controller, capture/input adapter, calibration
UI and tests were newly implemented for this project on 2026-11-01.

assets/reference/confirm_btn_1_2560x1440_1113_1070.png and
assets/reference/confirm_btn_2_2560x1440_1638_1070.png are unchanged copies from
ok-nte/assets/templates at that revision. They are reference-only, not enabled
runtime templates: these generic confirm icons cannot identify a safe settlement
screen by themselves. Preserve attribution and LICENSE when redistributing.
Game artwork remains attributable to its respective rights holders.

No ok-script runtime, OCR model, Windows input implementation, game executable,
user screenshot or private calibration profile is included.
Distribute corresponding source alongside any distributed app binary.

nte_owner/assets/preset contains minimal UI crops and coordinates derived from six screenshots
provided by the user on 2026-11-01. Full screenshots, UID and desktop content are
not included. The crops remain game artwork; do not represent them as original art.
The profile is a local calibration reference, not evidence of live-game validation.

Tests/fixtures contains cropped order-bubble and HUD reference patches from a
user-authorized local diagnostic screenshot, without UID, desktop or characters.
