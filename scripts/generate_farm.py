#!/usr/bin/env python3
"""Transform GuiZeroUm's GitHub contributions into a pixel-art farm.

The base art (assets/farm-base.png) stays untouched except for the central
crop field: that region is repainted as a real 53x7 contribution calendar,
where each day's activity level decides how far its crop has grown.
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

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "assets" / "farm-base.png"
OUTPUT = ROOT / "assets" / "farm-contributions.svg"
META = ROOT / "assets" / "farm-meta.json"

USER = os.getenv("GITHUB_USERNAME", "GuiZeroUm")
TOKEN = os.getenv("GITHUB_TOKEN", "")

WEEKS, DAYS = 53, 7

# Crop-field rectangle inside the base art, in native (1942x809) pixels.
FIELD = (416, 223, 1743, 602)

# Width of the exported image; smaller keeps the README SVG light.
OUTPUT_WIDTH = 1300

# GitHub contributionLevel -> internal growth stage.
LEVELS = {
    "NONE": 0,
    "FIRST_QUARTILE": 1,
    "SECOND_QUARTILE": 2,
    "THIRD_QUARTILE": 3,
    "FOURTH_QUARTILE": 4,
}

# Palette sampled to match the base art's soil and crops.
C = {
    "bed_edge": (78, 45, 30),
    "soil": (150, 96, 58),
    "soil_hi": (182, 124, 78),
    "furrow": (120, 74, 46),
    "green_lo": (58, 104, 30),
    "green": (96, 150, 34),
    "green_hi": (150, 190, 60),
    "wheat_lo": (168, 116, 44),
    "wheat": (222, 168, 62),
    "wheat_hi": (247, 214, 108),
}

# Fraction of each bed covered by foliage, per growth stage.
COVER = {1: 0.34, 2: 0.60, 3: 0.86, 4: 0.94}


@dataclass(frozen=True)
class Day:
    value: date | None
    count: int
    level: int
    future: bool = False


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
        "date weekday contributionCount contributionLevel}}}}}}"
    )
    data = graphql(
        query,
        {"login": username, "from": f"{start}T00:00:00Z", "to": f"{today}T23:59:59Z"},
    )
    calendar = data["user"]["contributionsCollection"]["contributionCalendar"]
    raw = calendar["weeks"][-WEEKS:]
    weeks = [[Day(None, 0, 0) for _ in range(DAYS)] for _ in range(WEEKS - len(raw))]
    for source in raw:
        week = [Day(None, 0, 0) for _ in range(DAYS)]
        for item in source["contributionDays"]:
            d = date.fromisoformat(item["date"])
            weekday = int(item["weekday"])
            week[weekday] = Day(
                d,
                int(item["contributionCount"]),
                LEVELS[item["contributionLevel"]],
                d > today,
            )
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
            level = (
                0 if signal < 7
                else 1 if signal < 11
                else 2 if signal < 16
                else 3 if signal < 20
                else 4
            )
            count = (0, 1, 3, 6, 11)[level]
            future = d > today
            if future:
                level, count = 0, 0
            total += count
            week.append(Day(d, count, level, future))
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
    if lookup.get(cursor, Day(cursor, 0, 0)).count == 0:
        cursor -= timedelta(days=1)
    current = 0
    while lookup.get(cursor, Day(cursor, 0, 0)).count > 0:
        current += 1
        cursor -= timedelta(days=1)
    return active, best, current


def leafy(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int]) -> None:
    """Fill a bed region with a dense, textured green canopy (top-down bushes)."""
    x0, y0, x1, y1 = box
    draw.rounded_rectangle((x0, y0, x1, y1), radius=4, fill=C["green_lo"])
    step = 4
    toggle = 0
    by = y0 + 2
    while by <= y1:
        bx = x0 + 2 + (2 if toggle else 0)
        while bx <= x1:
            draw.ellipse((bx - 3, by - 3, bx + 3, by + 3), fill=C["green"])
            draw.ellipse((bx - 3, by - 3, bx, by), fill=C["green_hi"])
            bx += step
        by += step
        toggle ^= 1


def wheaty(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int]) -> None:
    """Fill a bed region with packed golden wheat stalks and grain heads."""
    x0, y0, x1, y1 = box
    draw.rounded_rectangle((x0, y0, x1, y1), radius=3, fill=C["wheat_lo"])
    sx = x0 + 2
    flip = 0
    while sx <= x1:
        top = y0 + (1 if flip else 3)
        draw.line((sx, y1 - 1, sx, top + 2), fill=C["wheat_lo"], width=2)
        draw.ellipse((sx - 2, top, sx + 2, top + 6), fill=C["wheat"])
        draw.ellipse((sx - 1, top, sx + 1, top + 3), fill=C["wheat_hi"])
        sx += 3
        flip ^= 1


def tile(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int], level: int, future: bool) -> None:
    x0, y0, x1, y1 = box
    w, h = x1 - x0, y1 - y0
    # Plowed soil bed with a dark rim, a lit top edge and horizontal furrows.
    draw.rectangle((x0, y0, x1, y1), fill=C["bed_edge"])
    draw.rectangle((x0 + 1, y0 + 1, x1 - 1, y1 - 1), fill=C["soil"])
    draw.line((x0 + 2, y0 + 2, x1 - 2, y0 + 2), fill=C["soil_hi"])
    for fy in range(y0 + 5, y1 - 1, 5):
        draw.line((x0 + 2, fy, x1 - 2, fy), fill=C["furrow"])
    if future or level == 0:
        return
    # Foliage fills the bed from the bottom up, taller with more activity.
    fh = max(4, int((h - 3) * COVER[level]))
    crop = (x0 + 1, y1 - 1 - fh, x1 - 1, y1 - 1)
    (wheaty if level == 4 else leafy)(draw, crop)


def render_field(image: Image.Image, weeks: list[list[Day]]) -> None:
    draw = ImageDraw.Draw(image)
    x0, y0, x1, y1 = FIELD
    col_w = (x1 - x0) / WEEKS
    row_h = (y1 - y0) / DAYS
    pad = 2
    for wi, week in enumerate(weeks):
        for wd, day in enumerate(week):
            cx0 = round(x0 + wi * col_w) + pad
            cy0 = round(y0 + wd * row_h) + pad
            cx1 = round(x0 + (wi + 1) * col_w) - pad
            cy1 = round(y0 + (wd + 1) * row_h) - pad
            tile(draw, (cx0, cy0, cx1, cy1), day.level, day.future)


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
    image = Image.open(BASE).convert("RGB")
    render_field(image, weeks)
    export(image)
    write_meta(args.username, total, weeks)
    print(f"Rendered {total} contributions for @{args.username}")


if __name__ == "__main__":
    main()
