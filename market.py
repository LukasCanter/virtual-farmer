"""Crop catalog and seasonal prices."""

import random
from dataclasses import dataclass

MONTH_SECONDS = 3 * 60 * 60


@dataclass(frozen=True)
class Crop:
    name: str
    seed_price: int
    baseline: int
    grow_seconds: int
    peak_month: int


CROPS = {
    crop.name: crop
    for crop in (
        Crop("wheat", 5, 10, 60, 1),
        Crop("carrot", 25, 50, 150, 6),
        Crop("potato", 750, 1250, 300, 8),
    )
}


def yearly_prices(rng: random.Random) -> dict[str, list[int]]:
    prices = {}
    for crop in CROPS.values():
        high_distances = (5, 6) if rng.choice((True, False)) else (3, 4)
        bands = {
            0: (1.1, 1.3),
            1: (1.05, 1.1),
            2: (0.75, 0.9),
            **{distance: (0.7, 0.85) for distance in range(3, 7)},
            **{distance: (1.02, 1.04) for distance in high_distances},
        }
        prices[crop.name] = []
        for month in range(1, 13):
            distance = abs(crop.peak_month - month)
            low, high = bands[min(distance, 12 - distance)]
            prices[crop.name].append(round(rng.uniform(low, high) * (crop.baseline + 1)))
    return prices
