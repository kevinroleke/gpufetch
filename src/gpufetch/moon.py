"""Moon phase widget — computed locally, no network required."""

import math
from datetime import datetime, timezone

from .ansi import RESET, BOLD, DIM, CYAN, YELLOW, WHITE, strip_ansi

# Reference new moon (J2000 era) and synodic period
_NEW_MOON_REF = datetime(2000, 1, 6, 18, 14, 0, tzinfo=timezone.utc)
_SYNODIC      = 29.53058867   # days

# Per-row inner character widths that approximate a circle at 2:1 aspect ratio
_INNER = [3, 7, 9, 9, 9, 7, 3]   # rows top → bottom, 9 chars wide total


# ── Phase calculation ─────────────────────────────────────────────────────────

def _phase() -> dict:
    """Return a dict with phase fraction, illumination, name, age, and next event."""
    now  = datetime.now(timezone.utc)
    age  = (now - _NEW_MOON_REF).total_seconds() / 86400 % _SYNODIC
    f    = age / _SYNODIC                              # 0.0 = new → 0.5 = full → 1.0 = new
    ill  = (1.0 - math.cos(math.tau * f)) / 2         # 0..1

    if   f < 0.025 or f > 0.975: name = "New Moon"
    elif f < 0.225:               name = "Waxing Crescent"
    elif f < 0.275:               name = "First Quarter"
    elif f < 0.475:               name = "Waxing Gibbous"
    elif f < 0.525:               name = "Full Moon"
    elif f < 0.725:               name = "Waning Gibbous"
    elif f < 0.775:               name = "Last Quarter"
    else:                         name = "Waning Crescent"

    days_to_full = ((0.5 - f) % 1.0) * _SYNODIC
    days_to_new  = ((1.0 - f) % 1.0) * _SYNODIC
    if days_to_full <= days_to_new:
        next_label, days_to = "Full in", days_to_full
    else:
        next_label, days_to = "New in",  days_to_new

    return {
        "f":          f,
        "ill":        ill,
        "name":       name,
        "age":        age,
        "next_label": next_label,
        "days_to":    days_to,
    }


# ── ASCII art ─────────────────────────────────────────────────────────────────

def _art(f: float) -> tuple[list[str], list[str]]:
    """
    Return (plain_rows, colored_rows), each 7 strings of exactly 9 chars.

    The illuminated fraction is placed on the RIGHT for waxing phases and on the
    LEFT for waning.  Because the circle narrows at the top and bottom rows, a
    uniform vertical terminator naturally produces a crescent silhouette.
    """
    ill    = (1.0 - math.cos(math.tau * f)) / 2
    waxing = f < 0.5
    plain: list[str] = []
    color: list[str] = []

    for inner_w in _INNER:
        lit  = round(inner_w * ill)
        dark = inner_w - lit
        lpad = (9 - inner_w) // 2
        rpad = 9 - inner_w - lpad

        if waxing:
            p = '░' * dark + '█' * lit
            c = (f"{DIM}{'░' * dark}{RESET}" if dark else "") + \
                (f"{YELLOW}{'█' * lit}{RESET}"  if lit  else "")
        else:
            p = '█' * lit + '░' * dark
            c = (f"{YELLOW}{'█' * lit}{RESET}"  if lit  else "") + \
                (f"{DIM}{'░' * dark}{RESET}" if dark else "")

        plain.append(' ' * lpad + p + ' ' * rpad)
        color.append(' ' * lpad + c + ' ' * rpad)

    return plain, color


# ── Widget renderer ───────────────────────────────────────────────────────────

def render_moon_widget(term_cols: int) -> str:
    border = WHITE
    width  = min(62, max(44, term_cols - 2))
    inner  = width - 2

    def top() -> str:
        return f"{border}╔{'═' * inner}╗{RESET}"
    def sep() -> str:
        return f"{border}╠{'═' * inner}╣{RESET}"
    def bot() -> str:
        return f"{border}╚{'═' * inner}╝{RESET}"

    def center(plain: str, colored: str = "") -> str:
        body = colored or plain
        pt   = max(0, inner - len(strip_ansi(body)))
        return f"{border}║{RESET}{' ' * (pt // 2)}{body}{' ' * (pt - pt // 2)}{border}║{RESET}"

    def row(plain: str, colored: str = "") -> str:
        body = colored or plain
        pad  = max(0, inner - len(strip_ansi(body)))
        return f"{border}║{RESET}{body}{' ' * pad}{border}║{RESET}"

    p          = _phase()
    ill_pct    = round(p["ill"] * 100)
    art_p, art_c = _art(p["f"])

    # Layout: 9-char moon disc | 2-char gap | info text
    ART_W, GAP_W = 9, 2
    info_w = inner - ART_W - GAP_W

    bar_w  = max(4, min(12, info_w - 6))
    filled = round(bar_w * p["ill"])
    empty  = bar_w - filled
    bar_p  = '█' * filled + '░' * empty
    bar_c  = f"{YELLOW}{'█' * filled}{RESET}{DIM}{'░' * empty}{RESET}"

    # 7 info lines aligned with the 7 art rows
    info_p = [
        f"  {p['name']}",
        f"  {bar_p} {ill_pct}%",
        "",
        f"  Age {p['age']:.1f} d",
        f"  {p['next_label']} {p['days_to']:.1f} d",
        "",
        "",
    ]
    info_c = [
        f"  {BOLD}{WHITE}{p['name']}{RESET}",
        f"  {bar_c} {YELLOW}{ill_pct}%{RESET}",
        "",
        f"  {DIM}Age{RESET} {CYAN}{p['age']:.1f} d{RESET}",
        f"  {DIM}{p['next_label']}{RESET} {CYAN}{p['days_to']:.1f} d{RESET}",
        "",
        "",
    ]

    lines = [
        top(),
        center("  MOON PHASE  ", f"  {WHITE}{BOLD}MOON PHASE{RESET}  "),
        sep(),
    ]
    for i in range(7):
        ip = (info_p[i] if i < len(info_p) else "")[:info_w]
        ic =  info_c[i] if i < len(info_c) else ""
        if len(strip_ansi(ic)) > info_w:
            ic = ip
        lines.append(row(
            art_p[i] + ' ' * GAP_W + ip,
            art_c[i] + ' ' * GAP_W + ic,
        ))

    lines.append(bot())
    return "\n".join(lines) + "\n"
