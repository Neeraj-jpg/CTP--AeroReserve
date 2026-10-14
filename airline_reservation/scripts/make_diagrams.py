"""Create report diagrams from the current AeroReserve design using Pillow."""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "diagrams"
OUT.mkdir(parents=True, exist_ok=True)

NAVY = "#102B46"
BLUE = "#1463A5"
CYAN = "#14B8C5"
GOLD = "#F4A62A"
INK = "#172B3E"
MUTED = "#536B80"
PALE = "#F3F7FA"
LIGHT_BLUE = "#E8F3F9"
LIGHT_CYAN = "#E7F8F7"
LIGHT_GOLD = "#FFF5E4"
WHITE = "#FFFFFF"
BORDER = "#C9D8E4"
GREEN = "#16835D"


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = (
        ["/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", "C:/Windows/Fonts/arialbd.ttf"]
        if bold
        else ["/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "C:/Windows/Fonts/arial.ttf"]
    )
    for candidate in candidates:
        if Path(candidate).exists():
            return ImageFont.truetype(candidate, size)
    return ImageFont.load_default()


def wrap_pixels(
    draw: ImageDraw.ImageDraw, text: str, face: ImageFont.ImageFont, width: int
) -> list[str]:
    lines: list[str] = []
    for paragraph in text.split("\n"):
        if not paragraph:
            lines.append("")
            continue
        line = ""
        for word in paragraph.split():
            trial = f"{line} {word}".strip()
            if line and draw.textlength(trial, font=face) > width:
                lines.append(line)
                line = word
            else:
                line = trial
        lines.append(line)
    return lines


def center_text(
    draw: ImageDraw.ImageDraw,
    box: tuple[int, int, int, int],
    text: str,
    face: ImageFont.ImageFont,
    fill: str = INK,
    spacing: int = 8,
) -> None:
    x1, y1, x2, y2 = box
    lines = wrap_pixels(draw, text, face, x2 - x1 - 32)
    heights = [draw.textbbox((0, 0), line, font=face)[3] for line in lines]
    total = sum(heights) + max(0, len(lines) - 1) * spacing
    y = y1 + (y2 - y1 - total) // 2
    for line, height in zip(lines, heights, strict=False):
        w = draw.textlength(line, font=face)
        draw.text((x1 + (x2 - x1 - w) / 2, y), line, font=face, fill=fill)
        y += height + spacing


def box(
    draw: ImageDraw.ImageDraw,
    coords: tuple[int, int, int, int],
    title: str,
    body: str,
    fill: str = LIGHT_BLUE,
    accent: str = BLUE,
    title_font: ImageFont.ImageFont | None = None,
    body_font: ImageFont.ImageFont | None = None,
) -> None:
    x1, y1, x2, y2 = coords
    draw.rounded_rectangle(coords, radius=24, fill=fill, outline=BORDER, width=3)
    draw.rounded_rectangle((x1, y1, x2, y1 + 16), radius=8, fill=accent)
    tf = title_font or font(34, True)
    bf = body_font or font(25)
    title_lines = wrap_pixels(draw, title, tf, x2 - x1 - 36)
    body_lines = wrap_pixels(draw, body, bf, x2 - x1 - 44)
    all_h = sum(draw.textbbox((0, 0), t, font=tf)[3] for t in title_lines) + 18
    all_h += sum(draw.textbbox((0, 0), t, font=bf)[3] for t in body_lines) + 6 * len(body_lines)
    y = y1 + max(34, (y2 - y1 - all_h) // 2)
    for line in title_lines:
        tw = draw.textlength(line, font=tf)
        draw.text((x1 + (x2 - x1 - tw) / 2, y), line, font=tf, fill=NAVY)
        y += draw.textbbox((0, 0), line, font=tf)[3] + 3
    y += 9
    for line in body_lines:
        tw = draw.textlength(line, font=bf)
        draw.text((x1 + (x2 - x1 - tw) / 2, y), line, font=bf, fill=MUTED)
        y += draw.textbbox((0, 0), line, font=bf)[3] + 6


def arrow(
    draw: ImageDraw.ImageDraw,
    start: tuple[int, int],
    end: tuple[int, int],
    color: str = BLUE,
    width: int = 7,
) -> None:
    draw.line([start, end], fill=color, width=width)
    import math

    angle = math.atan2(end[1] - start[1], end[0] - start[0])
    length = 24
    left = (end[0] - length * math.cos(angle - 0.55), end[1] - length * math.sin(angle - 0.55))
    right = (end[0] - length * math.cos(angle + 0.55), end[1] - length * math.sin(angle + 0.55))
    draw.polygon([end, left, right], fill=color)


def save(name: str, image: Image.Image) -> None:
    image.save(OUT / name, quality=95, optimize=True)


def architecture() -> None:
    image = Image.new("RGB", (1900, 1050), WHITE)
    draw = ImageDraw.Draw(image)
    draw.text((85, 55), "AeroReserve runtime architecture", font=font(48, True), fill=NAVY)
    draw.text(
        (87, 116),
        "Single-process demo · SQLite by default · PostgreSQL URL supported",
        font=font(27),
        fill=MUTED,
    )

    nodes = [
        (
            (70, 250, 365, 500),
            "Browser UI",
            "Search · cabin · passenger form\nSeat-map preview · native EventSource",
            LIGHT_CYAN,
            CYAN,
        ),
        (
            (440, 250, 735, 500),
            "FastAPI",
            "REST JSON · Pydantic validation\nSSE snapshot and event endpoints",
            LIGHT_BLUE,
            BLUE,
        ),
        (
            (810, 250, 1105, 500),
            "Booking service",
            "Route search · 45-min rule\nFare · seat selection · PNR",
            LIGHT_GOLD,
            GOLD,
        ),
        (
            (1180, 250, 1475, 500),
            "Repository",
            "SQLAlchemy sessions\nAtomic booking and audit writes",
            LIGHT_BLUE,
            BLUE,
        ),
        (
            (1550, 250, 1835, 500),
            "Database",
            "SQLite file: no setup\nOptional PostgreSQL URL",
            LIGHT_CYAN,
            CYAN,
        ),
    ]
    for coords, title, body, fill, accent in nodes:
        box(draw, coords, title, body, fill, accent)
    for start, end in [
        ((365, 375), (440, 375)),
        ((735, 375), (810, 375)),
        ((1105, 375), (1180, 375)),
        ((1475, 375), (1550, 375)),
    ]:
        arrow(draw, start, end)

    box(
        draw,
        (445, 675, 860, 900),
        "Flight lock manager",
        "Sorted process-local per-flight RLocks\nProtect threaded booking flow only",
        LIGHT_GOLD,
        GOLD,
    )
    box(
        draw,
        (1000, 675, 1415, 900),
        "In-process event bus",
        "Bounded per-flight queues\nPublish booking/cancellation after commit",
        LIGHT_CYAN,
        CYAN,
    )
    arrow(draw, (950, 500), (680, 675), GOLD)
    arrow(draw, (1100, 500), (1200, 675), CYAN)
    # SSE path back to the UI, deliberately labelled as in-process.
    draw.line([(1205, 900), (1205, 985), (210, 985), (210, 500)], fill=CYAN, width=7)
    arrow(draw, (210, 540), (210, 500), CYAN, width=7)
    draw.text(
        (550, 930),
        "SSE: initial seat snapshot + committed booking / cancellation updates",
        font=font(25, True),
        fill=BLUE,
    )
    save("architecture.png", image)


def booking_flow() -> None:
    image = Image.new("RGB", (1900, 700), WHITE)
    draw = ImageDraw.Draw(image)
    draw.text(
        (85, 55), "Booking flow: one PNR for the complete itinerary", font=font(46, True), fill=NAVY
    )
    steps = [
        (
            (75, 220, 390, 475),
            "1 · Validate",
            "Date, flights, airport joins\n≤3 legs · ≥45-min layover\nCabin and passengers",
            LIGHT_BLUE,
            BLUE,
        ),
        (
            (445, 220, 760, 475),
            "2 · Lock",
            "Acquire each flight ID\nin sorted order\nProcess-local only",
            LIGHT_GOLD,
            GOLD,
        ),
        (
            (815, 220, 1130, 475),
            "3 · Allocate",
            "Read active seat labels\nSelect per leg\nRe-check while locked",
            LIGHT_CYAN,
            CYAN,
        ),
        (
            (1185, 220, 1500, 475),
            "4 · Commit",
            "One PNR + every leg\nFare + audit row\nSingle DB transaction",
            LIGHT_BLUE,
            BLUE,
        ),
        (
            (1555, 220, 1840, 475),
            "5 · Publish",
            "Release locks\nPush SSE event per leg\nClient refreshes seat map",
            LIGHT_CYAN,
            CYAN,
        ),
    ]
    for coords, title, body, fill, accent in steps:
        box(draw, coords, title, body, fill, accent, font(30, True), font(22))
    for x1, x2 in [(390, 445), (760, 815), (1130, 1185), (1500, 1555)]:
        arrow(draw, (x1, 350), (x2, 350), BLUE, 6)
    draw.rounded_rectangle((250, 555, 1650, 635), radius=16, fill=LIGHT_GOLD, outline=GOLD, width=2)
    center_text(
        draw,
        (250, 555, 1650, 635),
        "Cancellation: mark the PNR CANCELLED atomically, release seats on all legs, then publish cancellation events.",
        font(23, True),
        NAVY,
    )
    save("booking_flow.png", image)


def er_diagram() -> None:
    image = Image.new("RGB", (1900, 1000), WHITE)
    draw = ImageDraw.Draw(image)
    draw.text((85, 55), "Persistence model", font=font(48, True), fill=NAVY)

    box(
        draw,
        (75, 170, 650, 770),
        "bookings",
        "PK  pnr\nstatus · travel_date · cabin\norigin · destination\npassenger_payload (JSON)\nfare_payload (JSON)\ncreated_at · cancelled_at",
        LIGHT_BLUE,
        BLUE,
        font(37, True),
        font(26),
    )
    box(
        draw,
        (740, 170, 1320, 770),
        "booking_legs",
        "PK  id\nFK  pnr → bookings.pnr\nsequence · flight_id\nflight_number · route · times\ncabin · seats_payload (JSON)\ndistance_km",
        LIGHT_CYAN,
        CYAN,
        font(37, True),
        font(26),
    )
    box(
        draw,
        (1420, 170, 1825, 500),
        "audit_log",
        "id · pnr · action\ndetail (JSON)\ncreated_at",
        LIGHT_GOLD,
        GOLD,
        font(35, True),
        font(26),
    )
    arrow(draw, (650, 465), (740, 465), BLUE, 7)
    draw.text((655, 410), "1 : many", font=font(20, True), fill=MUTED)
    draw.rounded_rectangle((1420, 585, 1825, 820), radius=24, fill=PALE, outline=BORDER, width=3)
    center_text(
        draw,
        (1435, 600, 1810, 805),
        "Audit PNR is a correlation field, not a foreign key. Schedule templates and cabin layouts are code constants; active booking legs determine seat occupancy.",
        font(23),
        MUTED,
    )
    draw.text(
        (80, 865),
        "A connecting itinerary stores one booking row and one ordered leg row per flight.",
        font=font(27, True),
        fill=NAVY,
    )
    save("data_model.png", image)


def route_network() -> None:
    image = Image.new("RGB", (1900, 950), WHITE)
    draw = ImageDraw.Draw(image)
    draw.text((85, 55), "Example dated itinerary options", font=font(48, True), fill=NAVY)
    draw.text(
        (87, 116),
        "Fictional AeroSky services · Vijayawada (VGA) to New Delhi (DEL)",
        font=font(27),
        fill=MUTED,
    )

    def node(x: int, y: int, code: str, highlight: bool = False) -> None:
        radius = 55
        fill = LIGHT_GOLD if highlight else LIGHT_BLUE
        draw.ellipse(
            (x - radius, y - radius, x + radius, y + radius), fill=fill, outline=BLUE, width=5
        )
        face = font(29, True)
        width = draw.textlength(code, font=face)
        draw.text((x - width / 2, y - 18), code, font=face, fill=NAVY)

    def path_line(x1: int, x2: int, y: int, label: str, color: str = BLUE) -> None:
        arrow(draw, (x1, y), (x2, y), color, width=5)
        face = font(20, True)
        width = draw.textlength(label, font=face)
        center_x = (x1 + x2) / 2
        draw.rounded_rectangle(
            (center_x - width / 2 - 14, y - 48, center_x + width / 2 + 14, y - 8),
            radius=8,
            fill=WHITE,
        )
        draw.text((center_x - width / 2, y - 43), label, font=face, fill=color)

    # Non-stop path.
    y = 270
    node(180, y, "VGA", True)
    node(1720, y, "DEL", True)
    path_line(245, 1650, y, "AS110 · 06:40–09:15 · Non-stop", GOLD)
    draw.text((700, 325), "1 flight leg · one PNR", font=font(22), fill=MUTED)

    # One-stop path: VGA → HYD → DEL.
    y = 485
    node(180, y, "VGA", True)
    node(950, y, "HYD")
    node(1720, y, "DEL", True)
    path_line(245, 880, y, "AS101 · 06:00–07:15", BLUE)
    path_line(1020, 1650, y, "AS205 · 08:30–10:55", CYAN)
    draw.text((655, 545), "Layover: 75 minutes", font=font(20, True), fill=GREEN)

    # Two-stop path: VGA → HYD → BLR → DEL.
    y = 725
    node(180, y, "VGA", True)
    node(650, y, "HYD")
    node(1130, y, "BLR")
    node(1720, y, "DEL", True)
    path_line(245, 585, y, "AS101 · 06:00–07:15", BLUE)
    path_line(715, 1065, y, "AS206 · 08:45–10:00", CYAN)
    path_line(1195, 1650, y, "AS306 · 11:30–14:00", BLUE)
    draw.rounded_rectangle((315, 850, 1585, 915), radius=16, fill=LIGHT_CYAN, outline=CYAN, width=2)
    center_text(
        draw,
        (330, 854, 1570, 910),
        "Every transfer requires the same airport and at least a 45-minute layover; all legs share one PNR.",
        font(22, True),
        NAVY,
    )
    save("route_network.png", image)


if __name__ == "__main__":
    architecture()
    booking_flow()
    er_diagram()
    route_network()
    print(f"Generated diagrams in {OUT}")
