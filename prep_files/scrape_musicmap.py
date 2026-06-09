#!/usr/bin/env python3
"""
scrape_musicmap.py
==================
Scrapes music genres from https://musicmap.info/ and writes one Markdown
file per main (super-)genre into genres_knowledge1/.

Strategy
--------
1. Fetch the main page and collect first-party JavaScript bundle URLs.
2. Download each bundle and scan for embedded JSON genre objects that
   contain a "description" field (common in JS-rendered SPAs).
3. If enough structured data is found (>10 objects with descriptions),
   use it.  Otherwise fall back to the comprehensive static genre map
   built from the super-genre and sub-genre lists visible in the HTML.
4. Write one .md file per main genre following the requested structure.

Requirements: requests, beautifulsoup4
"""

import json
import os
import re
import sys
import time
from urllib.parse import urljoin

import urllib3
import requests
from bs4 import BeautifulSoup

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ── Configuration ──────────────────────────────────────────────────────────────
BASE_URL   = "https://musicmap.info"
OUTPUT_DIR = "genres_knowledge1"

DELAY_PAGE = 1.5   # seconds before the main page request
DELAY_JS   = 0.5   # seconds between JS-bundle requests
DELAY_DATA = 0.4   # seconds between candidate data-file requests
TIMEOUT    = 20    # HTTP timeout

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": (
        "text/html,application/xhtml+xml,application/xml;"
        "q=0.9,image/avif,image/webp,*/*;q=0.8"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection":  "keep-alive",
    "Referer":     BASE_URL + "/",
}

# CDN / third-party hosts – skip their scripts
SKIP_HOSTS = {
    "googleapis.com", "gstatic.com", "jquery.com",
    "bootstrapcdn.com", "cloudflare.com", "fontawesome.com",
    "youtube.com", "ytimg.com", "twimg.com",
    "facebook.net", "google-analytics.com", "doubleclick.net",
}

# Paths to probe when looking for a standalone data file
DATA_PATH_CANDIDATES = [
    "/js/data.js", "/js/genres.js", "/data/genres.json",
    "/assets/genres.json", "/js/app.data.js", "/data/data.js",
]

# ── Super-genre → sub-genre mapping (built from static HTML) ──────────────────
#
# This is the ground-truth list extracted from the "Super-genres" panel and
# the alphabetical "Navigate" genre list visible in musicmap.info's static HTML.
# It is used as a fallback when the JS bundles yield no usable descriptions.
#
GENRE_MAP: dict[str, list[str]] = {
    "INDUSTRIAL & GOTHIC": [
        "(AVANT-GARDE) INDUSTRIAL",
        "KRAUTROCK",
        "GOTHIC ROCK & DEATHROCK",
        "DARKWAVE & COLDWAVE",
        "INDUSTRIAL ROCK / INDUSTRIAL METAL",
        "NOISE MUSIC",
        "MINIMAL WAVE / SYNTH & MINIMAL INDUSTRIAL (REVIVAL)",
        "FUTUREPOP",
        "ELECTRO-INDUSTRIAL / AGGREPPO",
        "ELECTRONIC BODY MUSIC (EBM)",
        "DARK AMBIENT / DARK INDUSTRIAL",
        "INDUSTRIAL TECHNO & SCHRANZ",
    ],
    "(HEAVY) METAL": [
        "CLASSIC METAL",
        "NWOBHM (NEW WAVE OF BRITISH HEAVY METAL)",
        "THRASH METAL",
        "GLAM METAL / HAIR METAL / POP METAL",
        "DOOM METAL",
        "PROGRESSIVE METAL",
        "BLACK METAL",
        "DEATH METAL",
        "POWER METAL",
        "EXTREME METAL (BLACK I & SPEED)",
        "NU METAL & RAP METAL",
        "SYMPHONIC METAL & GOTHIC METAL",
        "METALCORE / NEW WAVE OF AMERICAN HEAVY METAL (NWOAHM)",
        "CROSSOVER THRASH",
        "GRINDCORE",
        "STONER METAL / ROCK & SLUDGE METAL / ROCK",
        "MATH ROCK & MATHCORE",
    ],
    "ROCK: ROCK 'N' ROLL (R'N'R)": [
        "ROCK 'N' ROLL & ROCKABILLY",
        "SKIFFLE (REVIVAL)",
    ],
    "ROCK: GOLDEN AGE / CLASSIC ROCK": [
        "(MERSEY)BEAT / BRITISH INVASION",
        "GARAGE ROCK",
        "SURF ROCK / INSTRUMENTAL",
        "AMERICAN & BRITISH FOLK REVIVAL",
        "FOLK ROCK",
        "PSYCHEDELIC / ACID ROCK & PSYCHEDELIA",
        "PROGRESSIVE ROCK, ART ROCK & SYMPHONIC ROCK",
        "HARD ROCK",
        "SOUTHERN ROCK",
        "HEARTLAND ROCK & A.O.R. (ADULT ORIENTED ROCK)",
        "GLAM ROCK / GLITTER ROCK / SHOCK ROCK",
    ],
    "ROCK: PUNK ROCK / NEW WAVE": [
        "PUB ROCK & PROTO PUNK",
        "PUNK ROCK",
        "POST-PUNK",
        "NEW WAVE",
        "SYNTHPOP & NEW ROMANTICS",
        "NO WAVE",
        "ANARCHO-PUNK, CRUST PUNK & D-BEAT / DISCORECORE",
        "HORROR PUNK & PSYCHOBILLY",
    ],
    "ROCK: HARDCORE PUNK": [
        "ORIGINAL HARDCORE (PUNK)",
        "CROSSOVER THRASH",
        "GRINDCORE",
        "POST-HARDCORE, EMO(CORE) & SCREAMO",
        "MATH ROCK & MATHCORE",
        "SYNTHCORE & CRUNKCORE",
    ],
    "ROCK: ALTERNATIVE ROCK / INDIE": [
        "JANGLE POP / INDIE ROCK (& PAISLEY UNDERGROUND)",
        "NOISE ROCK",
        "ALTERNATIVE ROCK / INDIE II",
        "DREAM POP & SHOEGAZE",
        "GRUNGE",
        "POST-ROCK",
        "RAP ROCK, RAPCORE & FUNK METAL",
    ],
    "ROCK: CONTEMPORARY ROCK": [
        "POST-GRUNGE",
        "SKATE PUNK & POP PUNK",
        "GARAGE & POST-PUNK REVIVALS / NU-RAWK",
        "EMO-ROCK",
        "INDIETRONICA & CHILLWAVE",
        "NEW PROG / NU PROG / POST PROG (ROCK)",
        "INDIE FOLK & FREAKFOLK / NEW WEIRD AMERICA",
        "DANCE-PUNK & NU RAVE",
        "POST-BRITPOP",
    ],
    "POP MUSIC": [
        "BRILL BUILDING POP & CROONERS",
        "BUBBLEGUM & TEENYBOP",
        "(EARLY) POP ROCK & POWER POP",
        "SOFT ROCK / ADULT CONTEMPORARY (A.C.)",
        "SINGER/SONGWRITER",
        "BRITPOP",
        "DANCE POP",
        "INDIE POP (TWEE)",
        "HI-NRG / EURODISCO",
        "ELECTROPOP",
        "DISCOPOP / POST-DISCO",
        "ASIAN POP",
        "SCHLAGER",
        "RELIPOP & -ROCK / CONTEMPORARY CHRISTIAN MUSIC (CCM)",
        "ELECTROCLASH",
    ],
    "COUNTRY": [
        "CLASSIC COUNTRY / HILLBILLY",
        "WESTERN SWING",
        "BLUEGRASS",
        "HONKY TONK / HARDCORE COUNTRY",
        "BAKERSFIELD",
        "NASHVILLE / COUNTRYPOLITAN",
        "PROGRESSIVE COUNTRY & OUTLAW COUNTRY",
        "URBAN COUNTRY",
        "CONTEMPORARY COUNTRY / NEOTRADITIONALISTS",
        "AMERICANA / ALTERNATIVE COUNTRY",
        "COUNTRY POP & COUNTRY ROCK",
    ],
    "RHYTHM 'N' BLUES (R&B)": [
        "(EARLY) RHYTHM 'N' BLUES",
        "DOO WOP",
        "CHICAGO SOUL & DETROIT SOUL (MOTOWN)",
        "PHILLY SOUL",
        "MEMPHIS SOUL / DEEP SOUL / SOUTHERN SOUL",
        "SOUL BLUES (SOUTHERN SOUL II)",
        "EARLY FUNK & P-FUNK",
        "DEEP FUNK / RARE GROOVE & NU FUNK",
        "BOOGIE / ELECTROFUNK",
        "GO-GO",
        "NEO SOUL / NU SOUL",
        "NEW JACK SWING / SWINGBEAT",
        "DISCO",
        "NU-DISCO & FUNKTRONICA",
        "URBAN SOUL / POP (NU R&B I)",
        "URBAN BREAKS (NU R&B II)",
    ],
    "BLUE NOTE: GOSPEL & PIONEERS": [
        "(NEGRO) SPIRITUALS & WORKSONGS",
        "TRADITIONAL GOSPEL",
        "MODERN GOSPEL",
        "RAGTIME & STRIDE",
    ],
    "BLUE NOTE: BLUES": [
        "VAUDEVILLE / CLASSIC BLUES",
        "BOOGIE WOOGIE / PIANO BLUES",
        "COUNTRY BLUES / FOLK BLUES",
        "CHICAGO BLUES / CITY BLUES / URBAN BLUES",
        "JUMP BLUES",
        "HILL COUNTRY BLUES & TRANCE BLUES",
        "LOUISIANA BLUES / SWAMP BLUES",
        "(ELECTRIC) TEXAS BLUES",
        "WEST COAST BLUES",
        "BRITISH BLUES & BLUES ROCK",
        "SOUL BLUES (SOUTHERN SOUL II)",
        "TEXAS BLUESROCK & MODERN ELECTRIC BLUES",
    ],
    "BLUE NOTE: JAZZ": [
        "NEW ORLEANS JAZZ & DIXIELAND JAZZ",
        "CHICAGO JAZZ",
        "SWING / BIG BAND",
        "NEW ORLEANS & DIXIELAND JAZZ REVIVALS",
        "BEBOP",
        "COOL JAZZ & WEST COAST JAZZ",
        "HARD BOP",
        "SOUL JAZZ / JAZZ FUNK",
        "FREE JAZZ / AVANT-GARDE (JAZZ)",
        "FUSION / JAZZ ROCK",
        "THIRD STREAM / PROGRESSIVE JAZZ & MODAL JAZZ",
        "ACID JAZZ / JAZZDANCE",
        "ELECTRO SWING",
        "NU JAZZ / ELECTRO JAZZ",
        "NORDIC JAZZ",
        "SMOOTH JAZZ",
    ],
    "JAMAICAN MUSIC / REGGAE": [
        "MENTO",
        "SKA",
        "ROCKSTEADY",
        "(ROOTS) REGGAE",
        "DUB",
        "SKA REVIVAL (2-TONE), SKA PUNK & SKACORE",
        "LOVER'S ROCK & UK REGGAE",
        "DANCEHALL",
        "RAGGA",
        "REGGAE FUSION & BHANGRAMUFFIN",
        "REGGAETÓN & LATIN RAP",
    ],
    "RAP / HIP-HOP MUSIC": [
        "OLD SKOOL RAP PIONEERS",
        "GOLDEN AGE RAP (& HARDCORE RAP)",
        "(WEST COAST) GANGSTA RAP",
        "MIAMI BASS & BOUNCE",
        "JAZZ RAP / NATIVE TONGUE",
        "EAST COAST GANGSTA RAP",
        "TRAP & DRILL",
        "(DIRTY) SOUTH RAP, CRUNK & SNAP",
        "PROGRESSIVE RAP / NU SKOOL RAP",
        "GLITCH HOP & WONKY",
        "RAP ROCK, RAPCORE & FUNK METAL",
    ],
    "EDM / DANCE: BREAKBEAT": [
        "FREESTYLE & BREAKDANCE",
        "BREAKBEAT HARDCORE (RAVE II)",
        "CHEMICAL BREAKS & BIG BEAT",
        "NU SKOOL BREAKS",
        "UK GARAGE (2-STEP & SPEED GARAGE)",
        "BREAKBEAT GARAGE & GRIME",
        "EDM TRAP / TRAPSTEP",
        "FLORIDA BREAKS (& FUNKY BREAKS)",
        "AMBIENT BREAKS & ILLBIENT",
        "BROKEN BEATS",
        "ELECTRO",
    ],
    "EDM / DANCE: DRUM 'N' BASS / JUNGLE": [
        "OLD SKOOL JUNGLE & OLD SKOOL DRUM 'N' BASS",
        "JUMP UP",
        "LIQUID FUNK",
        "HARDSTEP & TECHSTEP",
        "INTELLIGENT / AMBIENT DRUM 'N' BASS & JAZZSTEP",
        "NEUROFUNK",
        "DARKCORE & DARKSTEP",
        "FUTURE BASS / FUTURE GARAGE",
    ],
    "EDM / DANCE: HARDCORE (TECHNO)": [
        "BREAKBEAT HARDCORE (RAVE II)",
        "(EARLY) GABBER",
        "HARDSTYLE (& JUMPSTYLE)",
        "HAPPY HARDCORE & BOUNCY TECHNO",
        "DIGITAL HARDCORE & BREAKCORE",
        "UK HARDCORE & FREEFORM / TRANCECORE & ACIDCORE",
        "SPEEDCORE, FRENCHCORE & TERRORCORE",
        "NU STYLE (GABBER) / MAINSTREAM HARDCORE",
        "NEW BEAT",
    ],
    "EDM / DANCE: TECHNO": [
        "DETROIT TECHNO",
        "MINIMAL TECHNO",
        "(FREE)TEK(K)NO",
        "INDUSTRIAL TECHNO & SCHRANZ",
        "TECH HOUSE",
        "HARDTECHNO (SCHRANZ II)",
        "AMBIENT TECHNO & IDM (INTELLIGENT DANCE MUSIC)",
    ],
    "EDM / DANCE: HOUSE": [
        "CHICAGO HOUSE & GARAGE HOUSE",
        "HIP HOUSE & EURODANCE",
        "DEEP HOUSE",
        "ELECTRO HOUSE & DUTCH HOUSE",
        "MOOMBAHTON",
        "ACID HOUSE",
        "FRENCH HOUSE & FUNKY HOUSE",
        "MICROHOUSE / MINIMAL HOUSE",
        "GHETTO HOUSE, GHETTOTECH & JUKE",
        "FIDGET HOUSE & COMPLEXTRO",
        "NRG, HARD NRG & (UK) HARD HOUSE",
        "PROGRESSIVE HOUSE",
        "IBIZA HOUSE / TRANCE & DREAM HOUSE / TRANCE",
    ],
    "EDM / DANCE: TRANCE": [
        "PROGRESSIVE TRANCE",
        "NEO-TRANCE",
        "EUROTRANCE & VOCAL TRANCE",
        "CLASSIC TRANCE & ACID TRANCE",
        "GOA TRANCE & PSYTRANCE",
        "IBIZA HOUSE / TRANCE & DREAM HOUSE / TRANCE",
        "UPLIFTING TRANCE / EPIC TRANCE",
        "HARDTRANCE",
        "TECH TRANCE",
    ],
    "DOWNTEMPO / AMBIENT": [
        "MUSIQUE CONCRETE",
        "MINIMALISM",
        "NEW AGE",
        "AMBIENT",
        "LOUNGE / EXOTICA / SPACE AGE POP",
        "SYNTH / ELECTRONICA",
        "MUZAK / ELEVATOR MUSIC",
        "BIT MUSIC / VGM (CHIPTUNE & 8-BIT)",
        "DIGITAL MINIMALISM / LOWERCASE",
        "SYNTHWAVE & VAPORWAVE",
        "AMBIENT HOUSE / CHILL-OUT",
        "GLITCH / CLICKS 'N' CUTS",
        "TRIP HOP",
    ],
}


# ── HTTP helpers ───────────────────────────────────────────────────────────────

def fetch(url: str, delay: float = 1.0) -> "requests.Response | None":
    """GET a URL after a short delay.  Returns None on any error."""
    time.sleep(delay)
    try:
        r = requests.get(url, headers=HEADERS, timeout=TIMEOUT, verify=False)
        r.raise_for_status()
        return r
    except requests.RequestException as exc:
        print(f"    [WARN] {url}")
        print(f"           {exc}")
        return None


def is_first_party(src: str) -> bool:
    """True if the script src belongs to musicmap.info (not a CDN)."""
    if src.startswith("/"):
        return True
    for host in SKIP_HOSTS:
        if host in src:
            return False
    site_host = BASE_URL.split("//")[-1].rstrip("/")
    return site_host in src


# ── JS bundle genre extraction ─────────────────────────────────────────────────

# Match a JS variable assigned a JSON array that is at least 500 chars
_RE_JS_ARRAY = re.compile(
    r"""(?:var|let|const)\s+\w+\s*=\s*(\[[\s\S]{500,}?\]);""",
    re.DOTALL,
)
# Match an object that contains the word "description" anywhere inside
_RE_JS_OBJ = re.compile(
    r"""\{(?:[^{}]|\{[^{}]*\}){50,}"description"\s*:[\s\S]{5,200}\}""",
    re.DOTALL,
)


def _clean_html(text: str) -> str:
    """Strip HTML tags and unescape common entities."""
    text = re.sub(r"<[^>]+>", "", text)
    for ent, ch in [
        ("&amp;", "&"), ("&lt;", "<"), ("&gt;", ">"),
        ("&quot;", '"'), ("&#39;", "'"), ("&nbsp;", " "),
    ]:
        text = text.replace(ent, ch)
    return text.strip()


def extract_genre_objects(js: str) -> list[dict]:
    """
    Try several heuristics to pull genre dicts from minified JS.
    Returns a (possibly empty) list of raw dicts.
    """
    results: list[dict] = []

    # Heuristic 1 — top-level array assignment
    for m in _RE_JS_ARRAY.finditer(js):
        chunk = m.group(1)
        if '"description"' not in chunk:
            continue
        try:
            data = json.loads(chunk)
            if isinstance(data, list):
                valid = [
                    d for d in data
                    if isinstance(d, dict)
                    and any(k in d for k in ("name", "title", "genre"))
                ]
                if len(valid) > 5:
                    results.extend(valid)
                    return results
        except (json.JSONDecodeError, ValueError):
            pass

    # Heuristic 2 — individual inline objects (one JSON object per line)
    for line in js.splitlines():
        line = line.strip().rstrip(",")
        if not (line.startswith("{") and '"description"' in line):
            continue
        try:
            obj = json.loads(line)
            if isinstance(obj, dict) and any(k in obj for k in ("name", "title")):
                results.append(obj)
        except (json.JSONDecodeError, ValueError):
            pass

    return results


def normalise(raw: dict) -> dict:
    """Map any JS key naming to canonical {name, description, subgenres}."""
    name = (
        raw.get("name") or raw.get("title") or raw.get("genre") or ""
    ).strip()
    desc = _clean_html(
        raw.get("description") or raw.get("desc") or raw.get("text") or ""
    )

    raw_subs = (
        raw.get("subgenres") or raw.get("sub_genres")
        or raw.get("subGenres") or raw.get("children") or []
    )
    subgenres: list[dict] = []
    if isinstance(raw_subs, list):
        for s in raw_subs:
            if isinstance(s, dict):
                sn = (s.get("name") or s.get("title") or "").strip()
                sd = _clean_html(s.get("description") or s.get("desc") or "")
                if sn:
                    subgenres.append({"name": sn, "description": sd})

    return {"name": name, "description": desc, "subgenres": subgenres}


# ── Markdown writer ────────────────────────────────────────────────────────────

def _safe_name(name: str) -> str:
    """Sanitise genre name for use as a filesystem path."""
    name = re.sub(r'[<>:"/\\|?*\r\n]', "", name).strip()
    return name[:120]


def write_md(
    main_name: str,
    main_desc: str,
    subgenres: list[dict],
    out_dir: str,
) -> str:
    """
    Write one Markdown file.  Returns the file path.

    Format:
        # Main Genre Name
        Main Genre Description

        ## Sub-Genres

        ### Sub-Genre Name
        Sub-Genre Description
    """
    lines = [
        f"# {main_name}",
        "",
        main_desc if main_desc else "*Description not available.*",
        "",
    ]

    if subgenres:
        lines += ["## Sub-Genres", ""]
        for sg in subgenres:
            lines.append(f"### {sg['name']}")
            lines.append("")
            lines.append(sg["description"] if sg["description"]
                         else "*Description not available.*")
            lines.append("")

    path = os.path.join(out_dir, _safe_name(main_name) + ".md")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines))
    return path


# ── Main ───────────────────────────────────────────────────────────────────────

def main() -> None:
    # 1 ── Create output directory ────────────────────────────────────────────
    abs_out = os.path.abspath(OUTPUT_DIR)
    os.makedirs(abs_out, exist_ok=True)
    print(f"Output directory : {abs_out}")

    # 2 ── Fetch the main page ─────────────────────────────────────────────────
    print(f"\n[1/3] Fetching {BASE_URL} …")
    resp = fetch(BASE_URL, delay=DELAY_PAGE)
    if resp is None:
        print("[FATAL] Could not reach musicmap.info.  Check your connection.")
        sys.exit(1)

    soup = BeautifulSoup(resp.text, "html.parser")
    print("       Page retrieved successfully.")

    # 3 ── Scan first-party JS bundles + candidate data files ─────────────────
    print("\n[2/3] Scanning for embedded genre data …")
    found_objects: list[dict] = []

    # First-party script src values from <script src="…">
    script_urls = [
        urljoin(BASE_URL, tag["src"])
        for tag in soup.find_all("script", src=True)
        if is_first_party(tag.get("src", ""))
    ]
    print(f"       {len(script_urls)} first-party script(s) found.")

    for url in script_urls:
        print(f"       ↓ {url}")
        js = fetch(url, delay=DELAY_JS)
        if js is None:
            continue
        objs = extract_genre_objects(js.text)
        if objs:
            print(f"         → {len(objs)} genre object(s) extracted")
            found_objects.extend(objs)

    # Also probe predictable standalone data-file paths
    print("       Probing candidate data-file paths …")
    for path in DATA_PATH_CANDIDATES:
        url = BASE_URL + path
        r = fetch(url, delay=DELAY_DATA)
        if r is None:
            continue
        # JSON file?
        try:
            data = r.json()
            if isinstance(data, list) and len(data) > 5:
                print(f"         ✓ JSON data found at {url} ({len(data)} items)")
                found_objects.extend(data)
                break
            if isinstance(data, dict):
                nested = data.get("genres") or data.get("data") or []
                if isinstance(nested, list) and len(nested) > 5:
                    print(f"         ✓ JSON data found at {url}")
                    found_objects.extend(nested)
                    break
        except ValueError:
            pass
        # JS file?
        objs = extract_genre_objects(r.text)
        if objs:
            print(f"         ✓ JS data found at {url} ({len(objs)} objects)")
            found_objects.extend(objs)
            break

    # Deduplicate by name
    seen_names: set[str] = set()
    unique: list[dict] = []
    for raw in found_objects:
        norm = normalise(raw)
        key = norm["name"].upper()
        if norm["name"] and key not in seen_names:
            seen_names.add(key)
            unique.append(norm)

    has_descriptions = sum(1 for g in unique if g["description"]) > 10
    print(f"\n       JS extraction : {len(unique)} unique genre(s), "
          f"{sum(1 for g in unique if g['description'])} with descriptions.")

    # 4 ── Write Markdown files ────────────────────────────────────────────────
    print(f"\n[3/3] Writing Markdown files to '{OUTPUT_DIR}/' …")
    saved = 0

    if has_descriptions:
        # ── Path A: real scraped data ──────────────────────────────────────
        print("       Using scraped JS data.\n")
        for g in unique:
            path = write_md(
                g["name"], g["description"], g["subgenres"], abs_out
            )
            print(f"  ✓  Saved: {os.path.basename(path)}")
            saved += 1
    else:
        # ── Path B: static genre map (names only, no descriptions) ────────
        print("       Descriptions not found in JS bundles.")
        print("       Falling back to static genre map (names only).\n")
        for main_name, sub_names in GENRE_MAP.items():
            subgenres = [{"name": s, "description": ""} for s in sub_names]
            path = write_md(main_name, "", subgenres, abs_out)
            print(f"  ✓  Saved: {os.path.basename(path)}")
            saved += 1

    print(f"\n{'─'*60}")
    print(f"Done.  {saved} file(s) written to '{OUTPUT_DIR}/'.")
    if not has_descriptions:
        print(
            "\nNote: Descriptions are empty because musicmap.info renders its\n"
            "content entirely via JavaScript (a canvas-based SPA).  The genre\n"
            "names and structure are complete and correct; descriptions can be\n"
            "filled in manually or via a headless-browser tool (e.g. Playwright)."
        )


if __name__ == "__main__":
    main()
