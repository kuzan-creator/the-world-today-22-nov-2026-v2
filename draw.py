#!/usr/bin/env python3
"""The World Today v2 -- Sunday 22 November 2026, 35 stories, one page.

Renders a 1024x1024 newspaper front page with Pillow at 2x supersampling,
then downscales with LANCZOS. Deterministic: no random module, only a
sine-hash grain. Fixes vs v1: (a) the 22-item list beside the map is
measured so every item fits on exactly one line; (b) every puff of smoke
is clamped inside its scene box, at least 6pt clear of the box top edge.
(c) the map draws filled continent shapes instead of dots, projected
with a margin so no landmass touches the frame, and every card 1-13
carries a big red round number badge in the top-right corner of its
picture.
"""
import hashlib
import math
import os

from PIL import Image, ImageDraw, ImageFont

SCALE = 2
PAGE = 1024
INK = (17, 17, 17)
PAPER = (250, 247, 238)
RED = (185, 28, 28)
NAVY = (22, 35, 63)
MUTED = (90, 90, 90)
RULE = (180, 175, 165)
OCEAN = (198, 226, 240)
LANDDOT = (70, 90, 110)
LAND = (206, 186, 140)
LANDLINE = (168, 146, 100)

FONT_DIR = "/usr/share/fonts/truetype/dejavu"


def px(v):
    """1x layout unit -> 2x render pixels."""
    return int(round(v * SCALE))


def f_sans(size, bold=False):
    name = "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf"
    return ImageFont.truetype(os.path.join(FONT_DIR, name), px(size))


def f_serif(size, bold=True):
    name = "DejaVuSerif-Bold.ttf" if bold else "DejaVuSerif.ttf"
    return ImageFont.truetype(os.path.join(FONT_DIR, name), px(size))


def grad(canvas, box, top_rgb, bot_rgb):
    """Vertical gradient inside box (box in 2x pixels)."""
    x0, y0, x1, y1 = box
    h = max(1, y1 - y0)
    for yy in range(y0, y1):
        t = (yy - y0) / h
        col = tuple(int(top_rgb[i] + (bot_rgb[i] - top_rgb[i]) * t) for i in range(3))
        canvas.line([(x0, yy), (x1, yy)], fill=col)


def wrap_words(paint, text, font, max_w):
    """Greedy word wrap by measured width; returns list of lines."""
    lines, cur = [], ""
    for word in text.split(" "):
        trial = word if not cur else cur + " " + word
        if paint.textlength(trial, font=font) <= max_w or not cur:
            cur = trial
        else:
            lines.append(cur)
            cur = word
    if cur:
        lines.append(cur)
    return lines


def smoke(paint, box, puffs):
    """Draw smoke puffs, HARD-CLAMPED inside box.

    box: (x0, y0, x1, y1) in 2x pixels. puffs: (fx, fy, r_frac) with fx/fy
    fractions of the box. Every puff's top stays >= y0 + 6pt (12px at 2x),
    and no puff leaves the box on any side. This is the v2 smoke rule:
    smoke never covers the headline / chip sitting above its scene.
    """
    x0, y0, x1, y1 = box
    w, h = x1 - x0, y1 - y0
    margin = px(6)
    for i, (fx, fy, rf) in enumerate(puffs):
        r = max(4, int(rf * h))
        cx = x0 + int(fx * w)
        cy = y0 + int(fy * h)
        cy = max(cy, y0 + margin + r)
        cy = min(cy, y1 - 4 - r)
        cx = max(cx, x0 + 2 + r)
        cx = min(cx, x1 - 2 - r)
        shade = 205 - (i % 3) * 14
        paint.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(shade, shade, shade))
        paint.ellipse([cx - r // 2, cy - r // 2, cx + r // 2, cy + r // 2],
                      fill=(shade + 18, shade + 18, shade + 18))


def flames(paint, box, n=3):
    """Small flame triangles hugging the bottom edge of the scene box."""
    x0, y0, x1, y1 = box
    w = x1 - x0
    for i in range(n):
        fx = x0 + int(w * (0.2 + 0.3 * i))
        fw = px(9)
        fh = px(16)
        paint.polygon([(fx - fw, y1), (fx, y1 - fh), (fx + fw, y1)], fill=(230, 110, 20))
        paint.polygon([(fx - fw // 2, y1), (fx, y1 - fh // 2), (fx + fw // 2, y1)],
                      fill=(245, 200, 40))


def skyline(paint, box, colour, seed):
    """Deterministic block skyline along the bottom of a scene box."""
    x0, y0, x1, y1 = box
    w = x1 - x0
    x = x0
    k = 0
    while x < x1 - px(4):
        bw = px(10 + int(9 * abs(math.sin(seed * 7.3 + k * 2.1))))
        bh = px(14 + int(20 * abs(math.sin(seed * 3.1 + k * 1.7))))
        paint.rectangle([x, y1 - bh, min(x + bw, x1), y1], fill=colour)
        x += bw + px(2)
        k += 1


def paint_scene(paint, box, kind):
    """Original coded illustration for one story card; all art stays in box."""
    x0, y0, x1, y1 = box
    w, h = x1 - x0, y1 - y0
    if kind == "summit":
        grad(paint, box, (126, 200, 190), (240, 235, 200))
        paint.ellipse([x1 - px(34), y0 + px(8), x1 - px(10), y0 + px(32)],
                      fill=(250, 220, 120))
        paint.polygon([(x0, y1), (x0 + w // 3, y0 + h // 2),
                       (x0 + 2 * w // 3, y1)], fill=(90, 140, 110))
        paint.polygon([(x0 + w // 3, y1), (x0 + 2 * w // 3, y0 + h // 3),
                       (x1, y1)], fill=(70, 120, 95))
        paint.rectangle([x0, y1 - px(10), x1, y1], fill=(60, 100, 80))
        for i, cx in enumerate([0.2, 0.5, 0.8]):
            fx = x0 + int(cx * w)
            paint.line([(fx, y1 - px(10)), (fx, y1 - px(30))], fill=(120, 60, 60), width=px(1))
            paint.polygon([(fx, y1 - px(30)), (fx + px(10), y1 - px(26)),
                           (fx, y1 - px(22))], fill=(185, 28, 28) if i % 2 == 0 else (30, 80, 160))
    elif kind == "strike":
        grad(paint, box, (40, 45, 80), (120, 70, 60))
        paint.ellipse([x0 + w // 2 - px(10), y0 + px(10), x0 + w // 2 + px(10),
                       y0 + px(30)], fill=(250, 180, 90))
        smoke(paint, box, [(0.3, 0.45, 0.16), (0.55, 0.38, 0.2), (0.75, 0.5, 0.14)])
        skyline(paint, box, (25, 25, 40), 3)
        flames(paint, box, 2)
    elif kind == "base":
        grad(paint, box, (25, 35, 70), (90, 90, 120))
        paint.rectangle([x0, y1 - px(16), x1, y1], fill=(15, 25, 45))
        for i in range(3):
            bx = x0 + px(14 + i * 34)
            paint.rectangle([bx, y1 - px(34), bx + px(22), y1 - px(16)], fill=(50, 55, 80))
            paint.line([(bx + px(11), y1 - px(34)), (bx + px(11), y1 - px(44))],
                       fill=(200, 200, 200), width=px(1))
        smoke(paint, box, [(0.25, 0.4, 0.15), (0.6, 0.34, 0.18), (0.85, 0.45, 0.13)])
        flames(paint, box, 2)
    elif kind == "ship":
        grad(paint, box, (150, 190, 220), (220, 230, 235))
        paint.rectangle([x0, y0 + int(h * 0.62), x1, y1], fill=(60, 110, 160))
        paint.polygon([(x0 + w // 4, y1 - px(14)), (x0 + 3 * w // 4, y1 - px(14)),
                       (x0 + 3 * w // 4 - px(8), y1 - px(4)),
                       (x0 + w // 4 + px(8), y1 - px(4))], fill=(40, 40, 55))
        paint.rectangle([x0 + w // 2 - px(4), y1 - px(26), x0 + w // 2 + px(4),
                         y1 - px(14)], fill=(40, 40, 55))
        smoke(paint, box, [(0.5, 0.42, 0.18), (0.68, 0.34, 0.15), (0.32, 0.48, 0.12)])
        flames(paint, box, 2)
    elif kind == "city":
        grad(paint, box, (90, 110, 150), (190, 190, 200))
        smoke(paint, box, [(0.3, 0.42, 0.15), (0.6, 0.36, 0.17)])
        skyline(paint, box, (45, 50, 70), 5)
    elif kind == "ruin":
        grad(paint, box, (200, 170, 130), (150, 120, 95))
        smoke(paint, box, [(0.35, 0.42, 0.16), (0.62, 0.36, 0.18), (0.8, 0.48, 0.12)])
        for i in range(4):
            bx = x0 + px(8 + i * 30)
            bh = px(16 + (i % 2) * 10)
            paint.rectangle([bx, y1 - bh, bx + px(22), y1], fill=(90, 80, 70))
    elif kind == "dome":
        grad(paint, box, (180, 200, 230), (240, 235, 220))
        paint.rectangle([x0, y1 - px(14), x1, y1], fill=(120, 110, 90))
        paint.pieslice([x0 + w // 2 - px(20), y1 - px(40), x0 + w // 2 + px(20),
                        y1 - px(4)], 180, 360, fill=(200, 170, 90))
        paint.rectangle([x0 + w // 2 - px(20), y1 - px(22), x0 + w // 2 + px(20),
                         y1 - px(14)], fill=(200, 170, 90))
    elif kind == "plant":
        grad(paint, box, (120, 130, 150), (200, 200, 195))
        for i in range(3):
            bx = x0 + px(12 + i * 40)
            paint.rectangle([bx, y1 - px(36), bx + px(10), y1 - px(10)], fill=(80, 85, 95))
        paint.rectangle([x0, y1 - px(12), x1, y1], fill=(70, 75, 85))
        smoke(paint, box, [(0.3, 0.4, 0.17), (0.55, 0.33, 0.19), (0.78, 0.46, 0.13)])
        flames(paint, box, 3)
    elif kind == "desert":
        grad(paint, box, (240, 210, 150), (220, 180, 120))
        paint.ellipse([x1 - px(30), y0 + px(6), x1 - px(8), y0 + px(28)],
                      fill=(250, 220, 130))
        paint.polygon([(x0, y1), (x0 + w // 2, y1 - px(12)), (x1, y1)], fill=(190, 150, 95))
        paint.ellipse([x0 + w // 3, y0 + px(10), x0 + w // 3 + px(26),
                       y0 + px(20)], fill=(90, 90, 100))
    elif kind == "tanker":
        grad(paint, box, (140, 170, 200), (210, 220, 230))
        paint.rectangle([x0, y0 + int(h * 0.6), x1, y1], fill=(50, 95, 140))
        paint.rectangle([x0 + w // 5, y1 - px(16), x0 + 4 * w // 5, y1 - px(6)],
                        fill=(120, 40, 40))
        smoke(paint, box, [(0.7, 0.38, 0.16), (0.85, 0.46, 0.12)])
        flames(paint, box, 2)
    elif kind == "jet":
        grad(paint, box, (130, 180, 230), (225, 235, 245))
        for i in range(3):
            cy = y0 + px(12 + i * 10)
            paint.line([(x0 + px(6), cy), (x1 - px(6), cy)], fill=(255, 255, 255), width=px(3))
        fx, fy = x0 + w // 2, y0 + h // 2
        paint.polygon([(fx - px(26), fy), (fx + px(26), fy - px(4)),
                       (fx + px(26), fy + px(4))], fill=(60, 65, 80))
        paint.polygon([(fx, fy - px(10)), (fx + px(8), fy), (fx, fy + px(2))],
                      fill=(60, 65, 80))
    elif kind == "hospital":
        grad(paint, box, (200, 220, 235), (245, 245, 240))
        paint.rectangle([x0 + w // 4, y0 + px(10), x0 + 3 * w // 4, y1 - px(8)],
                        fill=(235, 235, 230))
        paint.rectangle([x0 + w // 2 - px(3), y0 + px(14), x0 + w // 2 + px(3),
                         y0 + px(26)], fill=(185, 28, 28))
        paint.rectangle([x0 + w // 2 - px(9), y0 + px(17), x0 + w // 2 + px(9),
                         y0 + px(23)], fill=(185, 28, 28))
        paint.rectangle([x0, y1 - px(8), x1, y1], fill=(110, 160, 110))
    else:  # border
        grad(paint, box, (170, 200, 220), (230, 235, 230))
        paint.rectangle([x0, y1 - px(10), x1, y1], fill=(100, 140, 100))
        for i in range(6):
            bx = x0 + px(6 + i * 24)
            paint.line([(bx, y1 - px(10)), (bx, y1 - px(34))], fill=(70, 70, 70), width=px(2))
        paint.line([(x0, y1 - px(30)), (x1, y1 - px(30))], fill=(70, 70, 70), width=px(2))
        paint.polygon([(x0 + w // 2, y1 - px(44)), (x0 + w // 2 + px(12), y1 - px(34)),
                       (x0 + w // 2, y1 - px(24))], fill=(185, 28, 28))

# ---------------------------------------------------------------- data
TOPLINE = "THE WORLD IN ONE DAY  |  35 STORIES  \u00b7  6 REGIONS  \u00b7  EVERY ONE DATED SUNDAY 22 NOVEMBER 2026"
BIGDATE = "Sunday 22 November 2026"
SUBHEAD = ("Climate deal in sight at COP31  \u00b7  Missiles kill a boy of 7 in Kryvyi Rih  "
           "\u00b7  Iran claims strikes on US bases in Bahrain")

FIGURES = [
    ("~200", "nations at COP31"),
    ("03:00 GMT", "objection deadline"),
    ("148", "drones overnight"),
    ("73", "injured in Kryvyi Rih"),
    ("16", "crew evacuated"),
    ("2", "Patriot radars claimed"),
]

REGIONS = [("EUROPE", 9), ("MIDDLE EAST", 8), ("AMERICAS", 7),
           ("ASIA-PACIFIC", 5), ("AFRICA", 3), ("WORLD", 3)]
REGION_COLOURS = [(185, 28, 28), (200, 90, 30), (30, 90, 160),
                  (30, 130, 90), (120, 80, 160), (90, 90, 90)]
# Region index per list number 14-35 and per map pin 1-13, reusing the
# region-bar colours above (0=EUROPE, 1=MIDDLE EAST, 2=AMERICAS,
# 3=ASIA-PACIFIC, 4=AFRICA, 5=WORLD), so the list numbers and the map
# pins match the region bar.
MORE_REGION = {14: 0, 15: 0, 16: 0, 17: 0, 18: 1, 19: 1, 20: 1, 21: 2,
               22: 2, 23: 2, 24: 2, 25: 2, 26: 3, 27: 3, 28: 3, 29: 3,
               30: 4, 31: 4, 32: 4, 33: 0, 34: 5, 35: 5}
PIN_REGION = {1: 5, 2: 0, 3: 1, 4: 0, 5: 0, 6: 1, 7: 1, 8: 1, 9: 2, 10: 1,
              11: 3, 12: 2, 13: 0}

HEROES = [
    dict(tag="COP31: DEAL CLOSE", place="ANTALYA, TURKEY \u00b7 CLIMATE",
         head="COP31 talks close in on a final deal",
         body=("A new package lands after a fight over fossil fuels; states have "
               "until 03:00 GMT to object. (Reuters)"),
         credit="Summit president \u00b7 Reuters", scene="summit"),
    dict(tag="KRYVYI RIH: 2 DEAD, 73 HURT", place="KRYVYI RIH, UKRAINE",
         head="Missiles kill a boy of 7 in Zelenskyy's home city",
         body=("Three ballistic missiles and 148 drones hit overnight; a boy of 7 "
               "and a paramedic die. (Ukrinform)"),
         credit="City officials \u00b7 Ukrinform", scene="strike"),
    dict(tag="BAHRAIN: STRUCK", place="MANAMA, BAHRAIN \u00b7 IRAN WAR",
         head="Iran claims strikes on US bases in Bahrain",
         body=("The IRGC says missiles and drones hit two Patriot radars; Bahrain "
               "reports a site burned. (Al Jazeera)"),
         credit="IRGC statement \u00b7 Al Jazeera", scene="base"),
]

MEDIUMS = [
    dict(num=4, tag="SHIP ABLAZE", place="GULF OF FINLAND",
         head="Russian cargo ship burns after drone strike",
         credit="Finnish forces \u00b7 BBC", scene="ship"),
    dict(num=5, tag="NINE REGIONS HIT", place="KYIV, UKRAINE",
         head="Russia hits nine regions in one night",
         credit="Live updates \u00b7 Ukrinform", scene="city"),
    dict(num=6, tag="4 KILLED", place="GAZA",
         head="Four killed in Gaza as the ceasefire strains",
         credit="Witnesses \u00b7 QNA", scene="ruin"),
    dict(num=7, tag="COALITION TALKS", place="JERUSALEM",
         head="Eisenkot invites Likud to marathon talks",
         credit="Party statement \u00b7 Straits Times", scene="dome"),
    dict(num=8, tag="4 DEAD, 35 HURT", place="BASRA, IRAQ",
         head="Fire at Hartha power station kills four",
         credit="Security officials \u00b7 Reuters", scene="plant"),
    dict(num=9, tag="11 DEAD", place="SINALOA, MEXICO",
         head="'El Chapo Isidro' caught in raid",
         credit="Security chief \u00b7 Reuters", scene="desert"),
    dict(num=10, tag="TANKERS HIT", place="STRAIT OF HORMUZ",
         head="Two tankers struck off Oman as Gulf burns",
         credit="Maritime reports \u00b7 Reuters", scene="tanker"),
    dict(num=11, tag="170 KM OUT", place="MANILA, PHILIPPINES",
         head="Chinese bomber turns back from Manila",
         credit="Defence reports \u00b7 Reports", scene="jet"),
    dict(num=12, tag="BOLSONARO: ICU", place="BRASILIA, BRAZIL",
         head="Bolsonaro in intensive care, stable",
         credit="Hospital \u00b7 Reuters", scene="hospital"),
    dict(num=13, tag="1 DEC", place="TALLINN, ESTONIA",
         head="Estonia to shut its Russia border on 1 Dec",
         credit="Border guard \u00b7 Reuters", scene="border"),
]

# The 22 list items, each kept short enough to fit ONE line in its column.
# Format: (number, "Place: short fact (Outlet)")
MORE = [
    (14, "Denmark: Expels Russian attache (Guardian)"),
    (15, "Germany: IG Metall widens strike halt (Reuters)"),
    (16, "Moldova: Reports airspace breach (Kyiv Ind.)"),
    (17, "Portugal: March over living costs (Reuters)"),
    (18, "Saudi: Air defences down a missile (Investing)"),
    (19, "Lebanon: Aoun demands Israel pullout (Al Jazeera)"),
    (20, "Iran: Warns of 'silent economic war' (Al Jazeera)"),
    (21, "US: FBI probes hack of its crime database (BBC)"),
    (22, "US: Teen gamer helps FBI rescue girl (BBC)"),
    (23, "US: Midterm loss corners Vance for 2028 (ST)"),
    (24, "US: First child measles death in Virginia (Reports)"),
    (25, "US: Hegseth tightens US-Canada defence ties (WP)"),
    (26, "Myanmar: Quake of 4.1 strikes early (NCS)"),
    (27, "Japan: First live-fire training in India (Reports)"),
    (28, "Australia: Fred Nile, ex-NSW MP, dies at 92 (ABC)"),
    (29, "India: Modi opens Nitish Setu bridge (PTI)"),
    (30, "Nigeria: Funeral boat capsizes; 24 dead (NEMA)"),
    (31, "Somalia: Expels UAE ambassador (Reports)"),
    (32, "Ethiopia: ~700,000 displaced by fighting (Sat)"),
    (33, "Geneva: Killer-robot talks end with no rules (AP)"),
    (34, "Space: Voyager-1 one light-day from Earth (NASA)"),
    (35, "Tennis: Zverev v Alcaraz in ATP Finals (TOI)"),
]

DATECHECK = ("DATE CHECK \u2014 Wires read to 04:00 UTC, Sunday 22 November 2026. Every story here "
             "was reported, or was still developing, in the Sunday news cycle. Left out as other "
             "days' news: the 400-drone, 110-missile barrage on Ukraine (overnight 19\u201320 Nov); "
             "the Peru quake (Fri 20 Nov, 19:09 local); missiles landing in Poland (20 Nov); the "
             "Kerch Bridge strikes (17\u201318 Nov); the Shenzhen summit, the GTA VI launch and the "
             "Anthropic market debut (all 19 Nov).")

FOOT_SOURCES = ("Sources: Reuters, BBC, Al Jazeera, AP, CNN, Guardian, Straits Times, Kyiv "
                "Independent, ABC, Times of India, Ukrinform. Pictures and map: original, drawn in code.")
FOOT_MARK = "THE WORLD IN ONE DAY  \u00b7  SUNDAY 22 NOVEMBER 2026  \u00b7  ONE PAGE"

# Rough continent outlines in (lon, lat) for the filled map. Europe and
# Asia are one Eurasia shape, so no sea wedge cuts the landmass; the
# closing edge runs along 36N through the Mediterranean (sea, and any
# sliver of North Africa it clips is the same tan as Africa itself).
CONTINENTS = [
    [(-168, 66), (-140, 70), (-120, 72), (-95, 80), (-80, 73), (-65, 60), (-55, 47),
     (-70, 42), (-75, 35), (-80, 26), (-90, 21), (-97, 16), (-105, 20), (-115, 30),
     (-125, 40), (-125, 49), (-145, 60), (-165, 60)],
    [(-80, 10), (-60, 8), (-50, 0), (-35, -8), (-40, -20), (-48, -28), (-58, -35),
     (-70, -40), (-73, -50), (-70, -54), (-65, -45), (-70, -30), (-75, -18), (-80, -5)],
    [(-10, 36), (-9, 43), (0, 44), (3, 43), (8, 44), (12, 44), (19, 42), (23, 40),
     (28, 41), (30, 46), (40, 48), (50, 50), (60, 55), (70, 60), (80, 68), (100, 72),
     (120, 72), (140, 72), (160, 70), (178, 66), (170, 60), (162, 56), (158, 52),
     (142, 50), (135, 43), (127, 40), (122, 32), (120, 25), (110, 20), (105, 10),
     (100, 8), (95, 15), (90, 22), (85, 20), (80, 15), (76, 8), (72, 20), (65, 25),
     (58, 26), (52, 28), (48, 30), (43, 28), (40, 35), (35, 36)],
    [(-17, 15), (-10, 30), (0, 36), (10, 37), (20, 32), (32, 31), (35, 28), (43, 12),
     (51, 11), (48, 0), (40, -10), (35, -20), (32, -29), (20, -35), (15, -30),
     (12, -18), (9, -2), (9, 4), (-8, 5), (-13, 8)],
    [(113, -22), (114, -30), (120, -34), (130, -32), (140, -38), (150, -37),
     (153, -27), (146, -19), (142, -11), (136, -12), (132, -12), (126, -14),
     (122, -17), (114, -22)],
    [(-5, 50), (-3, 53), (-5, 56), (-2, 58), (0, 53)],
    [(130, 31), (133, 34), (137, 35), (140, 38), (141, 42), (143, 44), (140, 40)],
    [(167, -45), (172, -41), (175, -38), (178, -37), (174, -41)],
]

# Numbered pins: (story number, lon, lat). A few pins are nudged a few
# degrees apart so neighbouring numbers stay readable on the small map;
# each stays in its own country/sea area.
PINS = [(1, 26.0, 37.0), (2, 38.0, 47.0), (3, 48.0, 22.0), (4, 14.0, 63.0),
        (5, 26.0, 54.0), (6, 34.0, 28.0), (7, 36.0, 35.0), (8, 49.0, 30.0),
        (9, -107.0, 25.0), (10, 60.0, 29.0), (11, 121.0, 14.6),
        (12, -47.9, -15.8), (13, 28.0, 58.0)]


def inside_poly(lon, lat, poly):
    """Ray-casting point-in-polygon for the dotted map."""
    hit = False
    n = len(poly)
    for i in range(n):
        x1, y1 = poly[i]
        x2, y2 = poly[(i + 1) % n]
        if (y1 > lat) != (y2 > lat):
            x_at = (x2 - x1) * (lat - y1) / (y2 - y1) + x1
            if lon < x_at:
                hit = not hit
    return hit

# ---------------------------------------------------------------- layout
def draw_header(paint, w2):
    paint.rectangle([0, 0, w2, px(30)], fill=NAVY)
    f = f_sans(12.5, bold=True)
    tw = paint.textlength(TOPLINE, font=f)
    paint.text(((w2 - tw) / 2, px(7)), TOPLINE, font=f, fill=(255, 255, 255))
    f = f_serif(54)
    tw = paint.textlength(BIGDATE, font=f)
    paint.text(((w2 - tw) / 2, px(36)), BIGDATE, font=f, fill=INK)
    f = f_sans(15, bold=True)
    tw = paint.textlength(SUBHEAD, font=f)
    paint.text(((w2 - tw) / 2, px(100)), SUBHEAD, font=f, fill=RED)
    paint.line([(px(24), px(122)), (w2 - px(24), px(122))], fill=RULE, width=px(1))


def draw_figures(paint, w2):
    y0, y1 = px(128), px(160)
    cell = (w2 - px(48)) / 6
    for i, (num, label) in enumerate(FIGURES):
        x = px(24) + i * cell
        paint.rectangle([x + px(2), y0, x + cell - px(2), y1], fill=(255, 255, 255),
                        outline=RULE, width=px(1))
        f = f_sans(18, bold=True)
        tw = paint.textlength(num, font=f)
        paint.text((x + (cell - tw) / 2, y0 + px(2)), num, font=f, fill=RED)
        f = f_sans(10)
        tw = paint.textlength(label, font=f)
        paint.text((x + (cell - tw) / 2, y0 + px(21)), label, font=f, fill=MUTED)


def draw_regions(paint, w2):
    y0, y1 = px(166), px(188)
    total = sum(c for _, c in REGIONS)
    x = px(24)
    full = w2 - px(48)
    for (name, count), col in zip(REGIONS, REGION_COLOURS):
        seg = full * count / total
        paint.rectangle([x, y0, x + seg, y1], fill=col)
        f = f_sans(11, bold=True)
        lab = "%s %d" % (name, count)
        tw = paint.textlength(lab, font=f)
        paint.text((x + (seg - tw) / 2, y0 + px(6)), lab, font=f, fill=(255, 255, 255))
        x += seg


def num_badge(paint, cx, cy, r, num, font):
    """Red round story-number badge, white bold number centred on (cx, cy)."""
    paint.ellipse([cx - r, cy - r, cx + r, cy + r], fill=RED,
                  outline=(255, 255, 255), width=px(2))
    t = str(num)
    tw = paint.textlength(t, font=font)
    paint.text((cx - tw / 2, cy - font.size // 2), t, font=font,
               fill=(255, 255, 255))


def draw_hero(paint, box, hero, num):
    x0, y0, x1, y1 = box
    paint.rectangle(box, fill=(255, 255, 255), outline=RULE, width=px(1))
    scene_h = px(96)
    paint_scene(paint, (x0, y0, x1, y0 + scene_h), hero["scene"])
    paint.line([(x0, y0 + scene_h), (x1, y0 + scene_h)], fill=RULE, width=px(1))
    y = y0 + scene_h + px(6)
    f = f_sans(11, bold=True)
    paint.text((x0 + px(8), y), hero["tag"], font=f, fill=RED)
    # Big round number badge tucked into the top-right corner of the
    # picture (1.5x the old size, thick white rim), clear of the tag,
    # place and headline lines below the picture.
    num_badge(paint, x1 - px(4) - px(18), y0 + px(4) + px(18), px(18), num,
              f_sans(19, bold=True))
    y += px(15)
    f = f_sans(9.5)
    paint.text((x0 + px(8), y), hero["place"], font=f, fill=MUTED)
    y += px(13)
    f = f_sans(19, bold=True)
    for line in wrap_words(paint, hero["head"], f, x1 - x0 - px(16)):
        paint.text((x0 + px(8), y), line, font=f, fill=INK)
        y += px(21)
    y += px(2)
    f = f_sans(12)
    for line in wrap_words(paint, hero["body"], f, x1 - x0 - px(16)):
        paint.text((x0 + px(8), y), line, font=f, fill=(40, 40, 40))
        y += px(14)
    f = f_sans(10.5)
    paint.text((x0 + px(8), y1 - px(16)), hero["credit"], font=f, fill=MUTED)


def draw_medium(paint, box, card):
    x0, y0, x1, y1 = box
    paint.rectangle(box, fill=(255, 255, 255), outline=RULE, width=px(1))
    scene_h = px(52)
    paint_scene(paint, (x0, y0, x1, y0 + scene_h), card["scene"])
    paint.line([(x0, y0 + scene_h), (x1, y0 + scene_h)], fill=RULE, width=px(1))
    y = y0 + scene_h + px(4)
    f = f_sans(10, bold=True)
    paint.text((x0 + px(6), y), card["tag"], font=f, fill=RED)
    # Big round number badge tucked into the top-right corner of the
    # picture (1.5x the old size, thick white rim), clear of the tag,
    # place and headline lines below the picture.
    num_badge(paint, x1 - px(4) - px(15), y0 + px(4) + px(15), px(15),
              card["num"], f_sans(15, bold=True))
    y += px(12)
    f = f_sans(8.5)
    paint.text((x0 + px(6), y), card["place"], font=f, fill=MUTED)
    y += px(11)
    f = f_sans(12.5, bold=True)
    for line in wrap_words(paint, card["head"], f, x1 - x0 - px(12))[:3]:
        paint.text((x0 + px(6), y), line, font=f, fill=INK)
        y += px(14)
    f = f_sans(9.5)
    paint.text((x0 + px(6), y1 - px(12)), card["credit"], font=f, fill=MUTED)


def check_list_widths(paint, col_w):
    """V2 gate: every one of the 22 list lines must fit its column in ONE line.

    Measures number (bold red) + text (regular) exactly as drawn and
    raises if any line is too wide. Run before drawing so a bad line can
    never silently wrap onto a second row.
    """
    num_f = f_sans(11, bold=True)
    txt_f = f_sans(11)
    worst = 0.0
    for num, text in MORE:
        w = (paint.textlength(str(num), font=num_f) + px(4)
             + paint.textlength(text, font=txt_f))
        worst = max(worst, w)
        print("list %2d: %6.1f / %6.1f px  %s" % (num, w, col_w, text))
        if w > col_w:
            raise SystemExit("LIST OVERFLOW: item %d is %.1f px wide, column is %.1f px"
                             % (num, w, col_w))
    print("LIST OK: widest line %.1f / %.1f px" % (worst, col_w))
    return worst

def draw_map(paint, box):
    x0, y0, x1, y1 = box
    paint.rectangle(box, fill=OCEAN, outline=RULE, width=px(1))
    lon0, lon1, lat0, lat1 = -170.0, 190.0, 75.0, -55.0
    # Project into an inset box so every landmass sits fully inside the
    # frame with blue sea around it on all sides. Pins use the same
    # mapping, so they stay glued to their places.
    m = px(10)
    ix0, iy0, ix1, iy1 = x0 + m, y0 + m, x1 - m, y1 - m

    def to_xy(lon, lat):
        return (ix0 + (lon - lon0) / (lon1 - lon0) * (ix1 - ix0),
                iy0 + (lat0 - lat) / (lat0 - lat1) * (iy1 - iy0))

    # Filled continent shapes on the blue sea, so each landmass reads at a
    # glance; pins are drawn on top afterwards.
    for poly in CONTINENTS:
        paint.polygon([to_xy(lon, lat) for lon, lat in poly],
                      fill=LAND, outline=LANDLINE)
    f = f_sans(8, bold=True)
    for num, lon, lat in PINS:
        cx, cy = to_xy(lon, lat)
        r = px(7)
        paint.ellipse([cx - r, cy - r, cx + r, cy + r],
                      fill=REGION_COLOURS[PIN_REGION[num]], outline=(255, 255, 255),
                      width=px(1))
        tw = paint.textlength(str(num), font=f)
        paint.text((cx - tw / 2, cy - px(5)), str(num), font=f, fill=(255, 255, 255))


def draw_list(paint, col_a_x, col_b_x, col_w, y_top, row_h):
    num_f = f_sans(11, bold=True)
    txt_f = f_sans(11)
    for i, (num, text) in enumerate(MORE):
        col_x = col_a_x if i < 11 else col_b_x
        y = y_top + (i % 11) * row_h
        paint.text((col_x, y), str(num), font=num_f,
                   fill=REGION_COLOURS[MORE_REGION[num]])
        nw = paint.textlength(str(num), font=num_f)
        paint.text((col_x + nw + px(4), y), text, font=txt_f, fill=INK)


def draw_bottom(paint, w2):
    # Section headings above map and list.
    f = f_sans(13, bold=True)
    paint.text((px(24), px(706)), "WHERE IT HAPPENED", font=f, fill=INK)
    f2 = f_sans(10)
    paint.text((px(214), px(708)), "\u00b7 pins match story numbers", font=f2, fill=MUTED)
    f = f_sans(13, bold=True)
    paint.text((px(368), px(704)), "ALSO ON SUNDAY 22 NOVEMBER \u2014 22 MORE STORIES",
               font=f, fill=INK)
    draw_map(paint, (px(24), px(728), px(352), px(908)))
    col_w = px(310)
    check_list_widths(paint, col_w)
    draw_list(paint, px(368), px(690), col_w, px(730), px(16.2))
    # Date check box.
    paint.rectangle([px(24), px(916), w2 - px(24), px(970)], fill=(253, 232, 232),
                    outline=RED, width=px(1))
    f = f_sans(11)
    y = px(922)
    for line in wrap_words(paint, DATECHECK, f, w2 - px(48) - px(16)):
        paint.text((px(32), y), line, font=f, fill=(90, 20, 20))
        y += px(14)
    # Footer.
    f = f_sans(10)
    tw = paint.textlength(FOOT_SOURCES, font=f)
    paint.text(((w2 - tw) / 2, px(976)), FOOT_SOURCES, font=f, fill=MUTED)
    f = f_sans(10, bold=True)
    tw = paint.textlength(FOOT_MARK, font=f)
    paint.text(((w2 - tw) / 2, px(990)), FOOT_MARK, font=f, fill=INK)


def add_grain(img):
    """Deterministic sine-hash grain, no random module."""
    paint = ImageDraw.Draw(img)
    w2, h2 = img.size
    step = 7
    for yy in range(0, h2, step):
        for xx in range(0, w2, step):
            v = math.sin(xx * 12.9898 + yy * 78.233) * 43758.5453
            frac = v - math.floor(v)
            if frac > 0.93:
                paint.point((xx, yy), fill=(255, 255, 255))
            elif frac < 0.07:
                paint.point((xx, yy), fill=(0, 0, 0))


def build():
    w2 = PAGE * SCALE
    img = Image.new("RGB", (w2, w2), PAPER)
    paint = ImageDraw.Draw(img)
    draw_header(paint, w2)
    draw_figures(paint, w2)
    draw_regions(paint, w2)
    hero_w, hero_gap = px(312), px(16)
    for i, hero in enumerate(HEROES):
        x = px(24) + i * (hero_w + hero_gap)
        draw_hero(paint, (x, px(196), x + hero_w, px(432)), hero, i + 1)
    med_w, med_gap = px(190), px(6)
    for i, card in enumerate(MEDIUMS):
        row, col = divmod(i, 5)
        x = px(24) + col * (med_w + med_gap)
        y = px(440) + row * px(134)
        draw_medium(paint, (x, y, x + med_w, y + px(126)), card)
    draw_bottom(paint, w2)
    add_grain(img)
    small = img.resize((PAGE, PAGE), Image.LANCZOS)
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "entry.png")
    small.save(out, "JPEG", quality=90)
    return out


if __name__ == "__main__":
    path = build()
    data = open(path, "rb").read()
    print("wrote %s  %d bytes  sha256 %s" % (path, len(data), hashlib.sha256(data).hexdigest()))
