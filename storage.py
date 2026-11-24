"""Load and commit each game action as a single SQLite transaction."""

import json
import random
import sqlite3
import time
from contextlib import closing, contextmanager
from dataclasses import asdict
from pathlib import Path

from .game import Farm, Field, Game, Market
from .market import yearly_prices


@contextmanager
def open_game(path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(path)) as db, db:
        db.execute("BEGIN IMMEDIATE")
        db.execute("""
            CREATE TABLE IF NOT EXISTS farm_save (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                farm TEXT NOT NULL,
                market TEXT NOT NULL
            )
        """)
        row = db.execute("SELECT farm, market FROM farm_save WHERE id = 1").fetchone()
        now = int(time.time())
        rng = random.Random()
        if row is None:
            farm = Farm()
            market = Market(now, yearly_prices(rng))
        else:
            farm_data, market_data = map(json.loads, row)
            if farm_data["field"] is not None:
                farm_data["field"] = Field(**farm_data["field"])
            farm = Farm(**farm_data)
            market = Market(**market_data)

        game = Game(farm, market, now, rng)
        yield game

        db.execute("""
            INSERT INTO farm_save (id, farm, market) VALUES (1, ?, ?)
            ON CONFLICT (id) DO UPDATE SET farm = excluded.farm, market = excluded.market
        """, (json.dumps(asdict(farm)), json.dumps(asdict(market))))
