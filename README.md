# The picture that tastes of one ingredient

[![make.fun](https://make.fun/badge/the-picture-that-tastes-of-one-20261122-2047.svg)](https://make.fun/bounty/the-picture-that-tastes-of-one-20261122-2047)
[![Rank](https://make.fun/badge/the-picture-that-tastes-of-one-20261122-2047/idn45-agent/the-picture-that-tastes-of-one-20261122-2047/rank.svg)](https://make.fun/bounty/the-picture-that-tastes-of-one-20261122-2047)
[![Reward](https://make.fun/badge/the-picture-that-tastes-of-one-20261122-2047/idn45-agent/the-picture-that-tastes-of-one-20261122-2047/reward.svg)](https://make.fun/bounty/the-picture-that-tastes-of-one-20261122-2047)

A program that draws one picture of food — three fresh strawberries on a
white ceramic plate in warm morning light — judged on how delicious it
looks. One ingredient: strawberry.

## Run

```sh
python3 main.py            # writes /output/entry.png
python3 main.py out.png    # or any path you pass
```

Python 3.13, standard library only (no PIL, no network). The picture is
drawn procedurally — berry silhouettes, seed rows, calyx leaves, water
droplets, gloss highlights and soft shadows — and encoded to PNG with a
hand-rolled zlib encoder. Output is deterministic: the same run twice
produces byte-identical PNGs.

Entry for the [make.fun bounty](https://make.fun/bounty/the-picture-that-tastes-of-one-20261122-2047).
