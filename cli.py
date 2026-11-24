"""Interactive command loop and one-shot command entry point."""

import argparse
import shlex
import sqlite3
import sys
from calendar import month_abbr, month_name
from pathlib import Path

from .game import GameError, duration
from .market import CROPS, MONTH_SECONDS
from .storage import open_game

DEFAULT_SAVE = Path(__file__).resolve().parent / "farm.sqlite3"


def crop_argument(value):
    try:
        return CROPS[value.lower()]
    except KeyError:
        choices = ", ".join(CROPS)
        raise argparse.ArgumentTypeError(f"Choose a crop from {choices}.") from None


def profile(game, args):
    farm = game.farm
    next_level_xp = 100 * 2 ** farm.farm_level
    low = farm.yield_multiplier(0.8)
    high = farm.yield_multiplier(1.2)
    return "\n".join((
        f"Emeralds        {farm.emeralds:,}",
        f"Farm level      {farm.farm_level} ({farm.plant_limit:,} seeds per planting)",
        f"Hoe level       {farm.hoe_level} ({low:.2f}–{high:.2f}x harvest yield)",
        f"XP              {farm.xp:,} / {next_level_xp:,}",
        f"Harvests        {farm.harvested:,}",
        f"Crop storage    {farm.used:,} / {farm.capacity:,} (level {farm.inventory_level})",
    ))


def inventory(game, args):
    farm = game.farm
    lines = [
        f"Crop storage {farm.used:,}/{farm.capacity:,} · {farm.emeralds:,} emeralds",
        f"{'Crop':<10} {'Seeds':>9} {'Harvested':>10}",
    ]
    for name in CROPS:
        lines.append(f"{name.title():<10} {farm.seeds[name]:>9,} {farm.inventory[name]:>10,}")
    if farm.field is None:
        lines.append("Field: empty")
    else:
        planted = farm.field
        remaining = planted.remaining(game.now)
        status = f"ready in {duration(remaining)}" if remaining else "ready to harvest"
        lines.append(f"Field: {planted.seeds:,} {planted.crop} seeds · {status}")
    return "\n".join(lines)


def buy(game, args):
    amount, cost = game.buy(args.crop, args.amount)
    seeds = "seed" if amount == 1 else "seeds"
    return (
        f"Bought {amount:,} {args.crop.name} {seeds} for {cost:,} emeralds. "
        f"Balance: {game.farm.emeralds:,}."
    )


def plant(game, args):
    planted = game.plant(args.crop, args.amount)
    seeds = "seed" if planted.seeds == 1 else "seeds"
    return (
        f"Planted {planted.seeds:,} {planted.crop} {seeds}. "
        f"Ready in {duration(planted.remaining(game.now))}."
    )


def harvest(game, args):
    result = game.harvest()
    message = f"Harvested {result.stored + result.sold:,} units of {result.crop}."
    if result.sold:
        message += f" Sold {result.sold:,} overflow for {result.payout:,} emeralds."
    return f"{message} Crop storage: {game.farm.used:,}/{game.farm.capacity:,}."


def destroy(game, args):
    planted, recovered = game.destroy()
    return f"Cleared the {planted.crop} field. Recovered {recovered:,} of {planted.seeds:,} seeds."


def sell(game, args):
    amount, payout = game.sell(args.crop, args.amount)
    return (
        f"Sold {amount:,} units of {args.crop.name} for {payout:,} emeralds. "
        f"Balance: {game.farm.emeralds:,}."
    )


def crops(game, args):
    market = game.market
    lines = [
        f"{month_name[market.month]}, year {market.year} · Prices in emeralds",
        f"{'Crop':<10} {'Seed':>7} {'Base':>7} {'Sell':>7} {'Growth':>7}  Peak season",
    ]
    for crop in CROPS.values():
        lines.append(
            f"{crop.name.title():<10} {crop.seed_price:>7,} {crop.baseline:>7,} "
            f"{market.price(crop):>7,} {duration(crop.grow_seconds):>7}  "
            f"{month_name[crop.peak_month]}"
        )
    return "\n".join(lines)


def crop_details(game, args):
    crop = args.crop
    market = game.market
    price = market.price(crop)
    change = round(100 * (price - crop.baseline) / crop.baseline)
    lines = [
        f"{crop.name.title()} · Year {market.year}",
        f"Seeds: {crop.seed_price:,} emeralds · Growth: {duration(crop.grow_seconds)}",
        f"Current sell price: {price:,} emeralds ({change:+d}% vs. base {crop.baseline:,})",
        "Monthly sell prices",
    ]
    for month, month_price in enumerate(market.prices[crop.name], start=1):
        current = "  (current)" if month == market.month else ""
        lines.append(f"  {month_abbr[month]}  {month_price:>5,}{current}")
    return "\n".join(lines)


def economy(game, args):
    market = game.market
    until_month = market.month_started_at + MONTH_SECONDS - game.now
    until_year = until_month + (12 - market.month) * MONTH_SECONDS
    return "\n".join((
        f"{month_name[market.month]}, year {market.year}",
        f"Next month in {duration(until_month)}",
        f"Next year in {duration(until_year)}",
        "Each market month lasts 3 real-time hours.",
    ))


def add_commands(parser, *, required):
    command_label = "COMMAND" if required else "[COMMAND]"
    commands = parser.add_subparsers(title="commands", metavar=command_label, required=required)
    actions = (
        ("profile", profile, "Show balance, levels, and farm stats."),
        ("inventory", inventory, "Show seeds, crops, and field status."),
        ("crops", crops, "List crops, seed costs, and current prices."),
        ("crop", crop_details, "Show a crop's prices for all 12 months."),
        ("buy", buy, "Buy seeds. Omit amount to spend up to your balance."),
        ("plant", plant, "Plant seeds. Omit amount to fill the field."),
        ("harvest", harvest, "Harvest the field and sell any overflow."),
        ("sell", sell, "Sell crops. Omit amount to sell all of that crop."),
        ("destroy", destroy, "Clear the field and recover half the seeds."),
        ("economy", economy, "Show the market calendar."),
    )
    for name, handler, help_text in actions:
        command = commands.add_parser(name, help=help_text, description=help_text)
        command.set_defaults(handler=handler)
        if name in ("crop", "buy", "plant", "sell"):
            command.add_argument("crop", type=crop_argument, metavar="CROP")
        if name in ("buy", "plant", "sell"):
            command.add_argument("amount", nargs="?", type=int, metavar="AMOUNT")


def run_action(path, args):
    try:
        with open_game(path) as game:
            output = args.handler(game, args)
    except GameError as error:
        print(error, file=sys.stderr)
        return 1
    except (OSError, sqlite3.Error, ValueError) as error:
        print(f"Could not use save at {path}: {error}", file=sys.stderr)
        return 1
    print(output)
    return 0


def play(path):
    parser = argparse.ArgumentParser(prog="farmer", description="Type 'exit' to leave the farm.")
    add_commands(parser, required=True)
    print("Virtual Farmer")
    print("Type 'help' for commands. To start, try 'inventory' or 'buy wheat 5'.")
    prompt = "farmer> " if sys.stdin.isatty() else ""
    while True:
        try:
            line = input(prompt)
        except (EOFError, KeyboardInterrupt):
            if prompt:
                print()
            return 0

        try:
            words = shlex.split(line)
        except ValueError as error:
            print(f"Invalid command: {error}", file=sys.stderr)
            continue
        if not words:
            continue
        words[0] = words[0].lower().lstrip("/")
        if len(words) == 1 and words[0] in ("exit", "quit"):
            return 0
        if words == ["help"]:
            parser.print_help()
            continue
        if words[0] == "help":
            words = [*words[1:], "--help"]
        try:
            args = parser.parse_args(words)
        except SystemExit:
            continue
        run_action(path, args)


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="python3 -m virtual_farmer",
        description="Play Virtual Farmer. Omit COMMAND to open the interactive prompt.",
    )
    parser.add_argument("--save", type=Path, default=DEFAULT_SAVE, help="Use a different save file.")
    add_commands(parser, required=False)
    args = parser.parse_args(argv)
    if hasattr(args, "handler"):
        return run_action(args.save.expanduser(), args)
    return play(args.save.expanduser())
