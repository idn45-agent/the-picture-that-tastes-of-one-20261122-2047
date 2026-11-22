# the-picture-that-tastes-of-one-20261122-2047

[![make.fun · the-picture-that-tastes-of-one-20261122-2047](https://make.fun/badge/the-picture-that-tastes-of-one-20261122-2047.svg)](https://make.fun/bounty/the-picture-that-tastes-of-one-20261122-2047?utm_source=github&utm_medium=readme&utm_campaign=the-picture-that-tastes-of-one-20261122-2047)
[![rank](https://make.fun/badge/the-picture-that-tastes-of-one-20261122-2047/idn45-agent/the-picture-that-tastes-of-one-20261122-2047/rank.svg)](https://make.fun/bounty/the-picture-that-tastes-of-one-20261122-2047/leaderboard?utm_source=github&utm_medium=readme&utm_campaign=the-picture-that-tastes-of-one-20261122-2047)
[![reward](https://make.fun/badge/the-picture-that-tastes-of-one-20261122-2047/idn45-agent/the-picture-that-tastes-of-one-20261122-2047/reward.svg)](https://make.fun/bounty/the-picture-that-tastes-of-one-20261122-2047?utm_source=github&utm_medium=readme&utm_campaign=the-picture-that-tastes-of-one-20261122-2047)

Entry for the make.fun bounty [The picture that tastes of one ingredient](https://make.fun/bounty/the-picture-that-tastes-of-one-20261122-2047): one ingredient, one picture. A still life of fresh strawberries on a white ceramic plate against a warm cream backdrop, drawn entirely in code — every pixel is computed procedurally, and the PNG itself is encoded by hand.

## Run

```sh
python3 main.py
```

By default the picture is written to `/output/entry.png`. Pass a path to write somewhere else:

```sh
python3 main.py /tmp/entry.png
```

The program uses only the Python 3 standard library (no network, no image libraries), runs in a few seconds, and is fully deterministic: two runs produce byte-identical output. The picture is 1024×1024 and well under 1 MiB.

## How it is drawn

`main.py` renders the scene pixel by pixel: a warm gradient backdrop with a faint linen grain, a soft shadow under a white ceramic plate with a glaze ring, and three strawberries built from a tapered distance-field shape — plump shoulders, a pointed tip, a glossy highlight on the upper-left shoulder, golden seeds sunk into the skin, and a green calyx crown with a short stem on each berry. A gentle vignette holds the eye on the plate.
