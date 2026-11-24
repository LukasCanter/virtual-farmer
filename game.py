"""Farming rules and state shared by all terminal commands."""

import random
from dataclasses import dataclass, field

from .market import CROPS, MONTH_SECONDS, Crop, yearly_prices


class GameError(Exception):
    """An action the player cannot currently take."""


def duration(seconds: int) -> str:
    hours, remainder = divmod(seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    parts = [f"{value}{unit}" for value, unit in (
        (hours, "h"), (minutes, "m"), (seconds, "s")
    ) if value]
    return " ".join(parts) or "0s"


@dataclass
class Field:
    crop: str
    seeds: int
    ready_at: int

    def remaining(self, now: int) -> int:
        return max(0, self.ready_at - now)


@dataclass
class Farm:
    emeralds: int = 25
    farm_level: int = 1
    inventory_level: int = 1
    hoe_level: int = 1
    xp: int = 0
    harvested: int = 0
    seeds: dict[str, int] = field(default_factory=lambda: dict.fromkeys(CROPS, 0))
    inventory: dict[str, int] = field(default_factory=lambda: dict.fromkeys(CROPS, 0))
    field: Field | None = None

    @property
    def plant_limit(self) -> int:
        return self.farm_level * 5

    @property
    def capacity(self) -> int:
        return self.inventory_level * 15

    @property
    def used(self) -> int:
        return sum(self.inventory.values())

    def yield_multiplier(self, variation: float) -> float:
        return round(max(1, (1 + self.hoe_level * 0.1) * variation), 2)


@dataclass
class Market:
    month_started_at: int
    prices: dict[str, list[int]]
    month: int = 1
    year: int = 1

    def refresh(self, now: int, rng: random.Random) -> None:
        elapsed = max(0, (now - self.month_started_at) // MONTH_SECONDS)
        years, month_index = divmod(self.month - 1 + elapsed, 12)
        if years:
            self.year += years
            self.prices = yearly_prices(rng)
        self.month = month_index + 1
        self.month_started_at += elapsed * MONTH_SECONDS

    def price(self, crop: Crop) -> int:
        return self.prices[crop.name][self.month - 1]


@dataclass(frozen=True)
class Harvest:
    crop: str
    stored: int
    sold: int
    payout: int


class Game:
    def __init__(self, farm: Farm, market: Market, now: int, rng: random.Random):
        self.farm = farm
        self.market = market
        self.now = now
        self.rng = rng
        self.market.refresh(now, rng)

    def buy(self, crop: Crop, amount: int | None) -> tuple[int, int]:
        if amount is None:
            amount = max(1, self.farm.emeralds // crop.seed_price)
        elif not 1 <= amount <= 100:
            raise GameError("Enter a purchase quantity between 1 and 100.")
        cost = amount * crop.seed_price
        if cost > self.farm.emeralds:
            raise GameError(f"You need {cost - self.farm.emeralds:,} more emeralds.")
        self.farm.emeralds -= cost
        self.farm.seeds[crop.name] += amount
        return amount, cost

    def plant(self, crop: Crop, amount: int | None) -> Field:
        if self.farm.field is not None:
            planted = self.farm.field
            remaining = planted.remaining(self.now)
            status = f"Ready in {duration(remaining)}." if remaining else "Ready to harvest."
            raise GameError(f"You already have {planted.crop} planted. {status}")
        owned = self.farm.seeds[crop.name]
        if amount is None:
            amount = min(owned, self.farm.plant_limit)
        if owned == 0:
            raise GameError(f"You have no {crop.name} seeds. Use 'buy {crop.name}'.")
        if amount < 1:
            raise GameError("Enter a positive planting quantity.")
        if amount > self.farm.plant_limit:
            raise GameError(f"Your field holds up to {self.farm.plant_limit:,} seeds.")
        if amount > owned:
            raise GameError(f"You have only {owned:,} {crop.name} seeds.")

        planted = Field(crop.name, amount, self.now + crop.grow_seconds)
        self.farm.seeds[crop.name] -= amount
        self.farm.field = planted
        return planted

    def harvest(self) -> Harvest:
        planted = self.require_field()
        remaining = planted.remaining(self.now)
        if remaining:
            raise GameError(f"Your {planted.crop} will be ready in {duration(remaining)}.")

        amount = round(planted.seeds * self.farm.yield_multiplier(self.rng.uniform(0.8, 1.2)))
        stored = min(amount, max(0, self.farm.capacity - self.farm.used))
        sold = amount - stored
        payout = sold * self.market.price(CROPS[planted.crop])
        self.farm.inventory[planted.crop] += stored
        self.farm.emeralds += payout
        self.farm.harvested += 1
        self.farm.field = None
        return Harvest(planted.crop, stored, sold, payout)

    def destroy(self) -> tuple[Field, int]:
        planted = self.require_field()
        recovered = planted.seeds // 2
        self.farm.seeds[planted.crop] += recovered
        self.farm.field = None
        return planted, recovered

    def sell(self, crop: Crop, amount: int | None) -> tuple[int, int]:
        owned = self.farm.inventory[crop.name]
        if owned == 0:
            raise GameError(f"You have no harvested {crop.name} to sell.")
        if amount is None:
            amount = owned
        if amount < 1:
            raise GameError("Enter a positive selling quantity.")
        if amount > owned:
            raise GameError(f"You have only {owned:,} harvested units of {crop.name}.")
        payout = amount * self.market.price(crop)
        self.farm.inventory[crop.name] -= amount
        self.farm.emeralds += payout
        return amount, payout

    def require_field(self) -> Field:
        if self.farm.field is None:
            raise GameError("Your field is empty. Buy seeds and plant them first.")
        return self.farm.field
