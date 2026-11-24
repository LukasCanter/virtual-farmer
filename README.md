# Virtual Farmer

Grow wheat, carrots, and potatoes, then sell them for emeralds in a market whose prices change each in-game month.

## Play

From this folder, run the game with Python 3.10 or newer. It uses only Python's standard library and runs offline.

```sh
python3 -m virtual_farmer
```

At the `farmer>` prompt, type `help` to see all commands or `help buy` for one command. A new farm starts with 25 emeralds. Try this first harvest.

```text
buy wheat 5
plant wheat
inventory
```

After one real-time minute, type `harvest`, then `sell wheat`. Crops keep growing after you exit. The field holds one batch at a time, and each harvest automatically sells any crops that would exceed your storage capacity.

Use `crops` to compare seed costs, sale prices, and growth times. Use `crop wheat` for its 12-month price schedule and `economy` to check when the market changes. The original bot tracked XP and levels without gameplay actions that changed them. The terminal profile keeps those stats.

## Saves

Game commands save automatically to `farm.sqlite3` in this folder. Type `exit` to leave the prompt. You can also run a single command directly or start a separate farm with a different file.

```sh
python3 -m virtual_farmer inventory
python3 -m virtual_farmer --save another-farm.sqlite3
```

The terminal save starts fresh. The original Discord source is archived in `legacy/`.
