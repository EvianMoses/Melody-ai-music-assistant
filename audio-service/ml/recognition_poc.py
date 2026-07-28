"""ACRCloud recognition POC — the §6.4 measurement (REC-ID-001, 002, 003).

    docker compose exec audio-service python -m ml.recognition_poc

**The test set (REC-ID-001)** is built from four classes, because a recognition
provider fails in four different ways and one number cannot describe all of them:

* **clean originals** — 30 s excerpts of real commercial recordings, taken from
  the GTZAN clips already on disk. These are the case the provider exists for.
* **noisy originals** — the same clips with added white noise and a lowered
  level, standing in for a phone held across a room, swept across several
  severities. This is the realistic case, and the gap between it and clean is
  the number that actually matters.

  **The catalogue control is not optional here.** A GTZAN clip that simply is
  not in ACRCloud's index fails identically to one the noise destroyed, so a
  noisy match rate computed over *all* clips silently blames the noise for
  missing catalogue coverage. Every clip is therefore run clean first, and the
  degradation curve is reported over the in-catalogue subset only. The first
  version of this script omitted that control and its noise figures were
  meaningless as a result.
* **no-match** — synthesized tones and noise. Nothing in any catalogue matches
  them, so **any** match here is a false positive, which is the most damaging
  failure mode: a confident wrong answer that the user cannot detect.
* **humming** — synthesized monophonic melodies. Included with an explicit
  caveat rather than omitted: they are *not* real humming, so they can only
  demonstrate that the query-by-humming path is reachable and cheap. **A pass
  rate here would not be evidence about real humming**, which is why the Phase 6
  gate criterion stays open regardless of what this run reports.

**What is measured (REC-ID-003)**: match rate per class, false-positive rate,
latency (median and p95), and the request count for cost. Cost per request comes
from the ACRCloud plan, not from here — this reports the volume it would take.
"""

from __future__ import annotations

import argparse
import asyncio
import io
import json
import math
import random
import statistics
import struct
import time
import wave
from pathlib import Path

from app import acrcloud, config, transcode

random.seed(1337)

SAMPLE_RATE = 22_050
CLIP_SECONDS = 12  # ACRCloud asks for 5-12 s; use the top of the range.


# ---------------------------------------------------------------------------
# Synthetic clips for the classes GTZAN cannot supply
# ---------------------------------------------------------------------------


def _write_wav(path: Path, samples: list[float]) -> Path:
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(SAMPLE_RATE)
        handle.writeframes(
            b"".join(struct.pack("<h", int(max(-1.0, min(1.0, s)) * 32767)) for s in samples)
        )
    return path


def make_no_match(path: Path, kind: str) -> Path:
    """Audio that provably matches nothing: tones, sweeps and noise."""
    total = CLIP_SECONDS * SAMPLE_RATE
    if kind == "tone":
        samples = [0.4 * math.sin(2 * math.pi * 440 * i / SAMPLE_RATE) for i in range(total)]
    elif kind == "sweep":
        samples = [
            0.4 * math.sin(2 * math.pi * (200 + 1800 * i / total) * i / SAMPLE_RATE)
            for i in range(total)
        ]
    else:
        samples = [random.uniform(-0.35, 0.35) for _ in range(total)]
    return _write_wav(path, samples)


def make_hummed_melody(path: Path, root: float) -> Path:
    """A monophonic melody with vibrato — a *stand-in* for humming, not humming.

    Labelled everywhere it appears so no reader mistakes a result on this for a
    result on real human humming.
    """
    intervals = [0, 2, 4, 5, 7, 5, 4, 2]  # a plain major-scale phrase
    note_len = int(SAMPLE_RATE * CLIP_SECONDS / len(intervals))
    samples: list[float] = []
    for step in intervals:
        freq = root * (2 ** (step / 12))
        for i in range(note_len):
            # Vibrato and a soft attack/decay, which is what makes a hum a hum
            # rather than a beep.
            vibrato = 1 + 0.012 * math.sin(2 * math.pi * 5.5 * i / SAMPLE_RATE)
            envelope = min(1.0, i / (SAMPLE_RATE * 0.05)) * math.exp(-i / (note_len * 1.6))
            samples.append(0.45 * envelope * math.sin(2 * math.pi * freq * vibrato * i / SAMPLE_RATE))
    return _write_wav(path, samples)


def add_noise(source: Path, destination: Path, *, noise: float, gain: float) -> Path:
    """Room simulation: attenuate, then add white noise.

    Crude on purpose. A convolution reverb would model one specific room; what
    matters here is the signal-to-noise floor, which is what actually degrades
    a fingerprint.
    """
    with wave.open(str(source), "rb") as handle:
        frames = handle.readframes(handle.getnframes())
        channels, width, rate = handle.getnchannels(), handle.getsampwidth(), handle.getframerate()
    values = struct.unpack("<%dh" % (len(frames) // 2), frames)
    mixed = [
        max(-32767, min(32767, int(v * gain + random.gauss(0, noise * 32767))))
        for v in values
    ]
    with wave.open(str(destination), "wb") as handle:
        handle.setnchannels(channels)
        handle.setsampwidth(width)
        handle.setframerate(rate)
        handle.writeframes(b"".join(struct.pack("<h", v) for v in mixed))
    return destination


# ---------------------------------------------------------------------------
# The run
# ---------------------------------------------------------------------------


async def probe(path: Path) -> tuple[acrcloud.Recognition, float]:
    started = time.perf_counter()
    result = await acrcloud.identify(path)
    return result, (time.perf_counter() - started) * 1000


async def run(args: argparse.Namespace) -> dict:
    if not acrcloud.is_configured():
        raise SystemExit(
            "ACRCloud is not configured. Set ACRCLOUD_HOST, ACRCLOUD_ACCESS_KEY "
            "and ACRCLOUD_ACCESS_SECRET, then re-run."
        )

    workdir = Path(args.workdir)
    workdir.mkdir(parents=True, exist_ok=True)

    results: list[dict] = []

    async def measure(klass: str, path: Path, label: str) -> dict:
        recognition, latency_ms = await probe(path)
        row = {
            "class": klass,
            "label": label,
            "matched": recognition.matched,
            "confidence": recognition.confidence,
            "low_confidence": recognition.low_confidence,
            "reason": recognition.reason,
            "latency_ms": round(latency_ms),
            "title": recognition.track.get("title"),
            "artist": recognition.track.get("artist"),
        }
        results.append(row)
        mark = "MATCH" if row["matched"] else "  -  "
        detail = f'{row["title"]} — {row["artist"]}' if row["matched"] else (row["reason"] or "")
        print(f'{mark} {klass:<20} {label:<30} {row["latency_ms"]:>5} ms  {detail[:60]}')
        # Politeness to a rate-limited tier, and closer to real usage than a burst.
        await asyncio.sleep(args.delay)
        return row

    # --- 1. clean originals, which double as the catalogue control --------
    in_catalogue: list[tuple[Path, str]] = []
    genres_dir = Path(args.gtzan) if args.gtzan else None
    if genres_dir and genres_dir.is_dir():
        from ml import dataset as data_module

        clips = data_module.index_clips(genres_dir)
        # Sampled across genres rather than taking the first N, which would be
        # all blues and would say nothing about coverage.
        chosen = random.sample(clips, min(args.originals, len(clips)))
        print("── clean originals (also the catalogue control) ──")
        for index, clip in enumerate(chosen):
            clean = workdir / f"clean_{index:02d}.wav"
            transcode.to_analysis_wav(clip.path, clean)
            label = f"{clip.genre}/{clip.path.name}"
            row = await measure("clean_original", clean, label)
            if row["matched"]:
                in_catalogue.append((clean, label))
        print(
            f"\n{len(in_catalogue)}/{len(chosen)} are in ACRCloud's catalogue. "
            "The noise curve below covers those only.\n"
        )
    else:
        print("!! GTZAN not found — skipping the original-recording classes.")

    # --- 2. the degradation curve, over in-catalogue clips only -----------
    conditions = [
        ("light", 0.02, 0.55),
        ("moderate", 0.06, 0.40),
        ("heavy", 0.12, 0.25),
        ("severe", 0.20, 0.15),
    ]
    if in_catalogue:
        print("── noisy originals, by severity ──")
    for name, noise, gain in conditions:
        for index, (clean, label) in enumerate(in_catalogue):
            noisy = workdir / f"noisy_{name}_{index:02d}.wav"
            add_noise(clean, noisy, noise=noise, gain=gain)
            await measure(f"noisy_{name}", noisy, label)

    # --- 3. no-match: any match here is a false positive ------------------
    print("── no-match controls ──")
    for kind in ("tone", "sweep", "noise"):
        await measure("no_match", make_no_match(workdir / f"nomatch_{kind}.wav", kind), kind)

    # --- 4. humming stand-ins (NOT real humming — see the module docstring)
    print("── humming stand-ins (synthetic, not human) ──")
    for index, root in enumerate((220.0, 261.6, 329.6)):
        await measure(
            "humming_synthetic",
            make_hummed_melody(workdir / f"hum_{index}.wav", root),
            f"root={root:.0f}Hz",
        )

    # --- summary ----------------------------------------------------------
    by_class: dict[str, list[dict]] = {}
    for row in results:
        by_class.setdefault(row["class"], []).append(row)

    latencies = sorted(r["latency_ms"] for r in results)
    summary = {
        "host": acrcloud._credentials()[0],
        "clips": len(results),
        "requests": len(results),
        "catalogue_coverage": (
            round(len(in_catalogue) / args.originals, 3) if args.originals else None
        ),
        "latency_ms": {
            "median": statistics.median(latencies),
            "p95": latencies[max(0, int(len(latencies) * 0.95) - 1)],
            "max": latencies[-1],
        },
        "by_class": {},
    }
    for klass, rows in by_class.items():
        matched = [r for r in rows if r["matched"]]
        entry = {
            "n": len(rows),
            "matched": len(matched),
            "match_rate": round(len(matched) / len(rows), 3),
            "mean_confidence": (
                round(sum(r["confidence"] for r in matched) / len(matched), 3) if matched else None
            ),
        }
        if klass == "no_match":
            # For this class a match *is* the error, so it is named as one.
            entry["false_positive_rate"] = entry.pop("match_rate")
        summary["by_class"][klass] = entry

    print("\n" + json.dumps(summary, indent=2))

    output = Path(args.out)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps({"summary": summary, "results": results}, indent=2), encoding="utf-8")
    print(f"\nwritten: {output}")
    return summary


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--originals", type=int, default=10,
                        help="How many GTZAN clips to use (each is run clean AND noisy).")
    parser.add_argument("--gtzan", default="/app/data/gtzan/genres")
    parser.add_argument("--workdir", default="/tmp/melody-recognition-poc")
    parser.add_argument("--out", default="/app/ml/checkpoints/recognition_poc.json")
    parser.add_argument("--noise", type=float, default=0.02, help="White-noise sigma (0-1).")
    parser.add_argument("--gain", type=float, default=0.55, help="Level attenuation.")
    parser.add_argument("--delay", type=float, default=1.0, help="Seconds between requests.")
    return parser


if __name__ == "__main__":
    asyncio.run(run(build_parser().parse_args()))
