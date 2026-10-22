## What and why

<!-- The problem, what you saw, and how this fixes it. Link the issue if there is one. -->

## Tested on

- Robot (model / SKU):
- Firmware:
- Classic (local) or Prime (cloud):
- Home Assistant version:
- Live on the robot, or tests only:

Coding assistant used (fine either way): yes / no

## Checklist

- [ ] `bash scripts/check_all.sh` passes. If a test also fails on an unchanged `main`, name it here instead of ticking:
- [ ] The new test fails without the change (`AGENTS.md`, rule 1)
- [ ] No private data; placeholders as in `AGENTS.md`, rule 5
- [ ] Nothing taken from the iRobot apps, no texts or images (rule 8)
- [ ] No passwords or tokens in log lines (rule 6)
- [ ] If texts changed: in `strings.json` and all eight translations (rule 7)
- [ ] No version bump in `manifest.json` and no new file in `release-notes/` (rule 9)
