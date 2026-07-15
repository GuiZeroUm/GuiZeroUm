#!/usr/bin/env python3
"""Transform GuiZeroUm's GitHub contributions into a pixel-art farm.

The base art (assets/farm-base.png) keeps an empty plowed field in the
middle. This script tiles that field with a 53x7 grid of crop sprites,
where each cell is one day and its sprite shows how much wheat grew:

    0 commits   -> 1.png  (bare soil)
    1 commit    -> 2.png  (sprout)
    2-3 commits -> 3.png  (growing wheat)
    4-7 commits -> 4.png  (ripe wheat)
    8+ commits  -> 5.png  (golden wheat)

Sprites are square and pasted without stretching.
"""
from __future__ import annotations

import argparse
import json
import os
import urllib.request
from base64 import b64encode
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from io import BytesIO
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "assets" / "farm-base.png"
CROPS = ROOT / "assets" / "crops"
OUTPUT = ROOT / "assets" / "farm-contributions.svg"
META = ROOT / "assets" / "farm-meta.json"

USER = os.getenv("GITHUB_USERNAME", "GuiZeroUm")
TOKEN = os.getenv("GITHUB_TOKEN", "")

WEEKS, DAYS = 53, 7

# Plowed-field rectangle inside the base art, in native (1942x809) pixels.
FIELD = (422, 208, 1742, 612)

# Width of the exported image; smaller keeps the README SVG light.
OUTPUT_WIDTH = 1600

# Sprite files, ordered by growth stage (index 0 = bare soil).
SPRITE_FILES = ["1.png", "2.png", "3.png", "4.png", "5.png"]


@dataclass(frozen=True)
class Day:
    value: date | None
    count: int
    future: bool = False


def stage(count: int) -> int:
    """Map a day's contribution count to a sprite index (0-4)."""
    if count <= 0:
        return 0
    if count == 1:
        return 1
    if count <= 3:
        return 2
    if count <= 7:
        return 3
    return 4


def graphql(query: str, variables: dict) -> dict:
    if not TOKEN:
        raise RuntimeError("GITHUB_TOKEN is required (use --demo for a preview)")
    body = json.dumps({"query": query, "variables": variables}).encode()
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=body,
        headers={
            "Authorization": f"Bearer {TOKEN}",
            "Content-Type": "application/json",
            "User-Agent": "guizeroum-farm",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as response:
        payload = json.loads(response.read())
    if payload.get("errors"):
        raise RuntimeError(payload["errors"])
    return payload["data"]


def contributions(username: str) -> tuple[list[list[Day]], int]:
    today = datetime.now(timezone.utc).date()
    # GitHub's contributionsCollection window may not exceed one year.
    start = today - timedelta(days=364)
    query = (
        "query($login:String!,$from:DateTime!,$to:DateTime!){"
        "user(login:$login){contributionsCollection(from:$from,to:$to){"
        "contributionCalendar{totalContributions weeks{contributionDays{"
        "date weekday contributionCount}}}}}}"
    )
    data = graphql(
        query,
        {"login": username, "from": f"{start}T00:00:00Z", "to": f"{today}T23:59:59Z"},
    )
    calendar = data["user"]["contributionsCollection"]["contributionCalendar"]
    raw = calendar["weeks"][-WEEKS:]
    weeks = [[Day(None, 0) for _ in range(DAYS)] for _ in range(WEEKS - len(raw))]
    for source in raw:
        week = [Day(None, 0) for _ in range(DAYS)]
        for item in source["contributionDays"]:
            d = date.fromisoformat(item["date"])
            weekday = int(item["weekday"])
            week[weekday] = Day(d, int(item["contributionCount"]), d > today)
        weeks.append(week)
    return weeks[-WEEKS:], int(calendar["totalContributions"])


def demo() -> tuple[list[list[Day]], int]:
    today = date.today()
    first = today - timedelta(days=(today.weekday() + 1) % 7, weeks=WEEKS - 1)
    weeks, total = [], 0
    for wi in range(WEEKS):
        week = []
        for wd in range(DAYS):
            d = first + timedelta(weeks=wi, days=wd)
            signal = (wi * 17 + wd * 11 + d.toordinal()) % 23
            count = (0, 1, 3, 6, 11)[
                0 if signal < 7
                else 1 if signal < 11
                else 2 if signal < 16
                else 3 if signal < 20
                else 4
            ]
            future = d > today
            if future:
                count = 0
            total += count
            week.append(Day(d, count, future))
        weeks.append(week)
    return weeks, total


def streaks(weeks: list[list[Day]]) -> tuple[int, int, int]:
    days = sorted(
        (d for week in weeks for d in week if d.value and not d.future),
        key=lambda d: d.value,
    )
    active = sum(d.count > 0 for d in days)
    best = run = 0
    previous: date | None = None
    for d in days:
        if d.count > 0 and previous and d.value == previous + timedelta(days=1):
            run += 1
        else:
            run = 1 if d.count > 0 else 0
        best = max(best, run)
        previous = d.value
    lookup = {d.value: d for d in days}
    cursor = date.today()
    if lookup.get(cursor, Day(cursor, 0)).count == 0:
        cursor -= timedelta(days=1)
    current = 0
    while lookup.get(cursor, Day(cursor, 0)).count > 0:
        current += 1
        cursor -= timedelta(days=1)
    return active, best, current


def load_sprites() -> list[Image.Image]:
    sprites = []
    for name in SPRITE_FILES:
        path = CROPS / name
        if not path.exists():
            raise RuntimeError(f"Missing crop sprite: {path}")
        sprites.append(Image.open(path).convert("RGBA"))
    return sprites


def render_field(base: Image.Image, weeks: list[list[Day]]) -> Image.Image:
    x0, y0, x1, y1 = FIELD
    sprites = load_sprites()
    canvas = base.convert("RGBA")
    cache: dict[tuple[int, int, int], Image.Image] = {}
    for wi, week in enumerate(weeks):
        # Integer cell edges from float boundaries so cells tile with no gaps.
        cx0 = round(x0 + wi * (x1 - x0) / WEEKS)
        cx1 = round(x0 + (wi + 1) * (x1 - x0) / WEEKS)
        for wd, day in enumerate(week):
            cy0 = round(y0 + wd * (y1 - y0) / DAYS)
            cy1 = round(y0 + (wd + 1) * (y1 - y0) / DAYS)
            idx = stage(day.count)
            key = (idx, cx1 - cx0, cy1 - cy0)
            sprite = cache.get(key)
            if sprite is None:
                sprite = sprites[idx].resize((cx1 - cx0, cy1 - cy0), Image.Resampling.LANCZOS)
                cache[key] = sprite
            canvas.alpha_composite(sprite, (cx0, cy0))
    return canvas.convert("RGB")


def export(image: Image.Image) -> None:
    if OUTPUT_WIDTH and image.width != OUTPUT_WIDTH:
        height = round(image.height * OUTPUT_WIDTH / image.width)
        image = image.resize((OUTPUT_WIDTH, height), Image.Resampling.LANCZOS)
    quantized = image.quantize(colors=256, method=Image.Quantize.FASTOCTREE, dither=Image.Dither.NONE)
    buffer = BytesIO()
    quantized.save(buffer, format="PNG", optimize=True)
    encoded = b64encode(buffer.getvalue()).decode()
    OUTPUT.write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" '
        f'viewBox="0 0 {image.width} {image.height}" role="img">'
        "<title>GuiZeroUm contribution farm</title>"
        f'<image width="{image.width}" height="{image.height}" '
        f'href="data:image/png;base64,{encoded}"/></svg>'
    )


def write_meta(username: str, total: int, weeks: list[list[Day]]) -> None:
    active, best, current = streaks(weeks)
    dated = [d.value for week in weeks for d in week if d.value]
    META.write_text(
        json.dumps(
            {
                "username": username,
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "period": {
                    "from": min(dated).isoformat() if dated else None,
                    "to": max(dated).isoformat() if dated else None,
                },
                "dimensions": {"weeks": WEEKS, "days": DAYS},
                "stats": {
                    "total_contributions": total,
                    "active_days": active,
                    "best_streak": best,
                    "current_streak": current,
                },
            },
            indent=2,
        )
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Render the GuiZeroUm contribution farm")
    parser.add_argument("--demo", action="store_true", help="use synthetic data, no API call")
    parser.add_argument("--username", default=USER)
    args = parser.parse_args()

    if not BASE.exists():
        raise RuntimeError(f"Base art not found: {BASE}")

    weeks, total = demo() if args.demo else contributions(args.username)
    base = Image.open(BASE).convert("RGB")
    image = render_field(base, weeks)
    export(image)
    write_meta(args.username, total, weeks)
    print(f"Rendered {total} contributions for @{args.username}")


if __name__ == "__main__":
    main()
