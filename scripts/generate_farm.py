#!/usr/bin/env python3
"""Transform GuiZeroUm's GitHub contributions into a pixel-art farm."""
from __future__ import annotations

import argparse, base64, json, os, urllib.request
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from io import BytesIO
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
PARTS = ROOT / "assets" / "farm-base"
OUTPUT = ROOT / "assets" / "farm-contributions.svg"
META = ROOT / "assets" / "farm-meta.json"
USER = os.getenv("GITHUB_USERNAME", "GuiZeroUm")
TOKEN = os.getenv("GITHUB_TOKEN", "")
WEEKS, DAYS = 53, 7
W, H = 1200, 500
GRID_X, GRID_Y, CELL, GAP = 254, 180, 12, 3
LEVELS = {"NONE": 0, "FIRST_QUARTILE": 1, "SECOND_QUARTILE": 2, "THIRD_QUARTILE": 3, "FOURTH_QUARTILE": 4}
C = {"ink":"#3d2423","shadow":"#241719","wood":"#9a5534","wood_d":"#6b3428","wood_l":"#d28a4a","soil":"#7b3e2e","soil_d":"#5f3027","soil_l":"#a75a38","furrow":"#4b2925","green_d":"#2f6b2d","green":"#55a83b","leaf":"#79c83d","wheat_d":"#b56b24","wheat":"#f1b735","wheat_l":"#ffd75a","cream":"#ffe7a6","paper":"#f4d58a"}

@dataclass(frozen=True)
class Day:
    value: date | None
    count: int
    level: int
    future: bool = False


def graphql(query: str, variables: dict) -> dict:
    if not TOKEN:
        raise RuntimeError("GITHUB_TOKEN is required")
    req = urllib.request.Request("https://api.github.com/graphql", data=json.dumps({"query": query, "variables": variables}).encode(), headers={"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json", "User-Agent": "guizeroum-farm"})
    with urllib.request.urlopen(req, timeout=30) as response:
        payload = json.loads(response.read())
    if payload.get("errors"):
        raise RuntimeError(payload["errors"])
    return payload["data"]


def contributions(username: str) -> tuple[list[list[Day]], int]:
    today = datetime.now(timezone.utc).date()
    start = today - timedelta(days=380)
    query = """query($login:String!,$from:DateTime!,$to:DateTime!){user(login:$login){contributionsCollection(from:$from,to:$to){contributionCalendar{totalContributions weeks{contributionDays{date weekday contributionCount contributionLevel}}}}}}"""
    data = graphql(query, {"login": username, "from": f"{start}T00:00:00Z", "to": f"{today}T23:59:59Z"})
    calendar = data["user"]["contributionsCollection"]["contributionCalendar"]
    raw = calendar["weeks"][-WEEKS:]
    weeks = [[Day(None, 0, 0) for _ in range(DAYS)] for _ in range(WEEKS - len(raw))]
    for source in raw:
        week = [Day(None, 0, 0) for _ in range(DAYS)]
        for item in source["contributionDays"]:
            d = date.fromisoformat(item["date"])
            weekday = int(item["weekday"])
            week[weekday] = Day(d, int(item["contributionCount"]), LEVELS[item["contributionLevel"]], d > today)
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
            level = 0 if signal < 7 else 1 if signal < 11 else 2 if signal < 16 else 3 if signal < 20 else 4
            count = (0, 1, 3, 6, 11)[level]
            if d > today: level, count = 0, 0
            total += count
            week.append(Day(d, count, level, d > today))
        weeks.append(week)
    return weeks, total


def font(size: int):
    for name in ("DejaVuSansMono-Bold.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf"):
        try: return ImageFont.truetype(name, size)
        except OSError: pass
    return ImageFont.load_default()


def center(draw, box, text, size, fill, stroke=None):
    f = font(size); bounds = draw.textbbox((0, 0), text, font=f, stroke_width=1 if stroke else 0)
    x = box[0] + (box[2] - box[0] - (bounds[2] - bounds[0])) // 2
    y = box[1] + (box[3] - box[1] - (bounds[3] - bounds[1])) // 2 - bounds[1]
    draw.text((x, y), text, font=f, fill=fill, stroke_fill=stroke, stroke_width=1 if stroke else 0)


def tile(draw, x, y, level, future=False):
    r, b = x + CELL - 1, y + CELL - 1
    draw.rectangle((x,y,r,b), fill=C["ink"]); draw.rectangle((x+1,y+1,r-1,b-1), fill=C["soil_d"]); draw.rectangle((x+2,y+2,r-2,b-2), fill=C["soil"])
    draw.line((x+3,y+5,r-3,y+5), fill=C["furrow"]); draw.line((x+3,y+8,r-3,y+8), fill=C["soil_l"])
    if future: return
    cx, base = x + 6, y + 10
    if level == 0: draw.point((cx, base-3), fill=C["wood_l"])
    elif level == 1:
        draw.line((cx,base,cx,base-3), fill=C["green_d"]); draw.rectangle((cx-2,base-3,cx,base-2), fill=C["green"]); draw.point((cx+2,base-4), fill=C["leaf"])
    elif level == 2:
        draw.line((cx,base,cx,base-6), fill=C["green_d"]); draw.rectangle((cx-3,base-4,cx,base-3), fill=C["green"]); draw.rectangle((cx+1,base-6,cx+3,base-5), fill=C["leaf"])
    elif level == 3:
        for off in (-3,0,3):
            draw.line((cx+off,base,cx+off,base-7), fill=C["green_d"]); draw.point((cx+off-1,base-4), fill=C["leaf"]); draw.point((cx+off+1,base-6), fill=C["green"])
    else:
        for off in (-3,0,3):
            stem = cx + off; draw.line((stem,base,stem,base-7), fill=C["wheat_d"]); draw.rectangle((stem-1,base-9,stem+1,base-7), fill=C["wheat"]); draw.point((stem,base-10), fill=C["wheat_l"])


def streaks(weeks):
    days = sorted((d for week in weeks for d in week if d.value and not d.future), key=lambda d: d.value)
    active, best, run, previous = sum(d.count > 0 for d in days), 0, 0, None
    for d in days:
        run = run + 1 if d.count > 0 and previous and d.value == previous + timedelta(days=1) else (1 if d.count > 0 else 0)
        best = max(best, run); previous = d.value
    lookup = {d.value:d for d in days}; cursor = date.today()
    if lookup.get(cursor, Day(cursor,0,0)).count == 0: cursor -= timedelta(days=1)
    current = 0
    while lookup.get(cursor, Day(cursor,0,0)).count > 0: current += 1; cursor -= timedelta(days=1)
    return active, best, current


def load_base():
    files = sorted(PARTS.glob("part-*.b64"))
    if not files: raise RuntimeError(f"No image parts in {PARTS}")
    encoded = "".join(p.read_text().strip() for p in files)
    image = Image.open(BytesIO(base64.b64decode(encoded))).convert("RGB")
    return image.resize((W,H), Image.Resampling.LANCZOS)


def render(weeks, total):
    image = load_base(); draw = ImageDraw.Draw(image)
    panel = (242,125,1060,379)
    draw.rectangle((247,131,1065,385), fill=C["shadow"]); draw.rectangle(panel, fill=C["ink"]); draw.rectangle((245,128,1057,376), fill=C["wood_d"]); draw.rectangle((249,132,1053,372), fill=C["soil"])
    plaque=(465,135,838,172); draw.rectangle((468,138,841,175), fill=C["shadow"]); draw.rectangle(plaque, fill=C["ink"]); draw.rectangle((469,139,834,168), fill=C["wood"]); center(draw, plaque, "CONTRIBUTION HARVEST", 15, C["cream"], C["ink"])
    for wi, week in enumerate(weeks):
        for wd, d in enumerate(week): tile(draw, GRID_X + wi*(CELL+GAP), GRID_Y + wd*(CELL+GAP), d.level, d.future)
    active, best, current = streaks(weeks)
    cards=((str(total),"CONTRIBUICOES"),(str(active),"DIAS ATIVOS"),(str(best),"MELHOR SEQUENCIA"),(str(current),"SEQUENCIA ATUAL"))
    start, cw = 280, 145
    for i,(value,label) in enumerate(cards):
        left=start+i*160; box=(left,310,left+cw,359); draw.rectangle((left+3,313,left+cw+3,362), fill=C["shadow"]); draw.rectangle(box, fill=C["ink"]); draw.rectangle((left+5,315,left+cw-5,354), fill=C["paper"]); center(draw,(left,312,left+cw,335),value,13,C["ink"]); center(draw,(left,334,left+cw,356),label,7,C["ink"])
    buffer=BytesIO(); image.save(buffer, format="PNG", optimize=True)
    encoded=base64.b64encode(buffer.getvalue()).decode()
    OUTPUT.write_text(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" role="img"><title>GuiZeroUm contribution farm</title><image width="{W}" height="{H}" href="data:image/png;base64,{encoded}"/></svg>')
    META.write_text(json.dumps({"username":USER,"generated_at":datetime.now(timezone.utc).isoformat(),"stats":{"total_contributions":total,"active_days":active,"best_streak":best,"current_streak":current}}, indent=2))


def main():
    parser=argparse.ArgumentParser(); parser.add_argument("--demo", action="store_true"); parser.add_argument("--username", default=USER); args=parser.parse_args()
    weeks,total = demo() if args.demo else contributions(args.username)
    render(weeks,total); print(f"Rendered {total} contributions for @{args.username}")

if __name__ == "__main__": main()
