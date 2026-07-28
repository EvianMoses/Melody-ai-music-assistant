"""GTZAN loading and a leakage-free split (ML-AUD-002).

**Dataset.** GTZAN: 1000 clips of 30 s, 100 per genre, the standard benchmark
for this task. Its faults are well documented (Sturm, *The GTZAN dataset: its
contents, its faults...*, 2013) -- exact duplicates, mislabelled clips, and
several files drawn from the same recording. They are not fixable here, so they
are stated in `docs/ml/audio-genre-classifier.md` and treated as a ceiling on
how much any reported number means. Availability: distributed for research use;
obtained from the `marsyas/gtzan` mirror.

**Leakage.** This is where a genre classifier is most often quietly broken. The
model is trained on 3-second *segments*, and a 30-second clip yields ten of
them. Splitting segments at random puts nine siblings of every test segment into
training, and the reported accuracy then measures memorization of specific
recordings -- it typically lands in the high 90s, which is the tell.

So the split is computed over **files**, and segments inherit their file's
split. `assert_no_leakage` enforces it rather than trusting the comment.

The residual risk that cannot be removed: GTZAN's own duplicate recordings can
place near-identical audio on both sides of a file-level split. Documented, not
hidden.
"""

from __future__ import annotations

import hashlib
import random
import tarfile
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional

import torch
import torchaudio
from torch.utils.data import Dataset

from .labels import GENRES, LABEL_TO_INDEX
from .model import SAMPLE_RATE, SEGMENT_SAMPLES

GTZAN_URL = "https://huggingface.co/datasets/marsyas/gtzan/resolve/main/data/genres.tar.gz"

# GTZAN ships one truncated file that torchaudio cannot decode. Excluded by name
# rather than by swallowing decode errors, so a *new* decode failure is still
# loud instead of being silently absorbed into this exception.
KNOWN_BAD_FILES = frozenset({"jazz.00054.wav"})

SPLIT_RATIOS = {"train": 0.70, "val": 0.15, "test": 0.15}


@dataclass(frozen=True)
class Clip:
    path: Path
    genre: str
    split: str

    @property
    def label(self) -> int:
        return LABEL_TO_INDEX[self.genre]


def download(root: Path) -> Path:
    """Fetch and extract GTZAN if it is not already present. Returns its dir."""
    root.mkdir(parents=True, exist_ok=True)
    genres_dir = root / "genres"
    if genres_dir.is_dir() and any(genres_dir.iterdir()):
        return genres_dir

    archive = root / "genres.tar.gz"
    if not archive.is_file():
        print(f"Downloading GTZAN (~1.2 GB) to {archive} ...")
        urllib.request.urlretrieve(GTZAN_URL, archive)
    print("Extracting ...")
    with tarfile.open(archive) as handle:
        # `filter="data"` refuses absolute paths, traversal entries and device
        # files inside the archive -- a downloaded tarball is untrusted input.
        handle.extractall(root, filter="data")
    return genres_dir


def _stable_bucket(name: str) -> float:
    """A deterministic 0-1 position for a filename.

    Hash-based rather than shuffle-based so the split survives re-runs, machine
    changes and a different Python version: `random.shuffle` with a fixed seed
    does not, and a split that silently moves between runs makes every
    comparison meaningless.
    """
    digest = hashlib.sha256(name.encode("utf-8")).hexdigest()
    return int(digest[:16], 16) / float(1 << 64)


def index_clips(genres_dir: Path) -> list[Clip]:
    """Build the file-level index with its train/val/test assignment.

    Genuinely stratified, and by ranking rather than thresholding. Comparing
    each file's hash against 0.70/0.85 is the obvious way to do this and it is
    only stratified *on average*: the first run produced test folds ranging from
    11 to 22 clips per genre, which distorts macro-F1 because the small folds
    carry far more variance. Sorting each genre's files by hash and cutting at
    exact positions keeps determinism and gives every genre the same proportions.
    """
    clips: list[Clip] = []
    for genre in GENRES:
        folder = genres_dir / genre
        if not folder.is_dir():
            raise FileNotFoundError(f"Missing genre folder: {genre}")
        # `._name.wav` files are macOS AppleDouble resource forks, 211 bytes
        # each, one per real clip -- they are in the distributed archive and
        # `Path.glob("*.wav")` returns them. Left in, they doubled the index to
        # 1999 "clips", half of them undecodable, and every split ratio and
        # per-genre count computed from that would have been wrong.
        files = sorted(
            path
            for path in folder.glob("*.wav")
            if not path.name.startswith(".") and path.name not in KNOWN_BAD_FILES
        )
        if len(files) < 50:
            raise RuntimeError(
                f"Only {len(files)} usable clips in '{genre}' -- the dataset looks "
                "incomplete. Delete data/gtzan and re-download."
            )
        # Hash order, not filename order: GTZAN's files are numbered in the
        # order they were collected, so a positional cut would put whole
        # contiguous runs -- often the same album -- entirely in one split.
        ordered = sorted(files, key=lambda path: _stable_bucket(path.name))
        train_end = round(len(ordered) * SPLIT_RATIOS["train"])
        val_end = train_end + round(len(ordered) * SPLIT_RATIOS["val"])
        for index, path in enumerate(ordered):
            if index < train_end:
                split = "train"
            elif index < val_end:
                split = "val"
            else:
                split = "test"
            clips.append(Clip(path=path, genre=genre, split=split))
    return clips


def assert_no_leakage(clips: Iterable[Clip]) -> None:
    """Fail loudly if any file appears in more than one split.

    An assertion rather than a comment because this is the property that decides
    whether the reported macro-F1 means anything at all.
    """
    seen: dict[str, str] = {}
    for clip in clips:
        previous = seen.get(clip.path.name)
        if previous is not None and previous != clip.split:
            raise AssertionError(
                f"{clip.path.name} appears in both '{previous}' and '{clip.split}'"
            )
        seen[clip.path.name] = clip.split


class SegmentDataset(Dataset):
    """3-second segments drawn from the clips of one split.

    Training takes a *random* offset per epoch (a cheap, label-preserving
    augmentation that multiplies the effective data), while validation and test
    take fixed, evenly spaced offsets so the score does not move between runs.
    """

    def __init__(
        self,
        clips: list[Clip],
        *,
        split: str,
        segments_per_clip: int = 10,
        augment: bool = False,
        seed: int = 1337,
    ) -> None:
        self.clips = [clip for clip in clips if clip.split == split]
        self.segments_per_clip = segments_per_clip
        self.augment = augment
        self.split = split
        self._rng = random.Random(seed)
        if not self.clips:
            raise ValueError(f"No clips in split '{split}'")

    def __len__(self) -> int:
        return len(self.clips) * self.segments_per_clip

    def _load(self, path: Path) -> torch.Tensor:
        waveform, sample_rate = torchaudio.load(str(path))
        if waveform.size(0) > 1:
            waveform = waveform.mean(dim=0, keepdim=True)
        if sample_rate != SAMPLE_RATE:
            waveform = torchaudio.functional.resample(waveform, sample_rate, SAMPLE_RATE)
        return waveform.squeeze(0)

    def __getitem__(self, index: int) -> tuple[torch.Tensor, int]:
        clip = self.clips[index // self.segments_per_clip]
        segment_index = index % self.segments_per_clip
        waveform = self._load(clip.path)

        usable = max(0, waveform.numel() - SEGMENT_SAMPLES)
        if self.augment and usable > 0:
            offset = self._rng.randint(0, usable)
        elif usable > 0:
            # Evenly spaced, deterministic: segment k of n covers its own slice.
            offset = int(usable * segment_index / max(1, self.segments_per_clip - 1))
        else:
            offset = 0

        segment = waveform[offset : offset + SEGMENT_SAMPLES]
        if segment.numel() < SEGMENT_SAMPLES:
            segment = torch.nn.functional.pad(
                segment, (0, SEGMENT_SAMPLES - segment.numel())
            )

        if self.augment:
            # Gain jitter only. Time-stretch or pitch-shift would change the
            # tempo and key a genre is partly defined by, so they are not
            # label-preserving here; spectrogram masking is applied downstream
            # in train.py where the spectrogram exists.
            segment = segment * self._rng.uniform(0.7, 1.3)
            segment = segment.clamp(-1.0, 1.0)

        return segment, clip.label


def build_splits(
    genres_dir: Path, *, segments_per_clip: int = 10, seed: int = 1337
) -> dict[str, SegmentDataset]:
    clips = index_clips(genres_dir)
    assert_no_leakage(clips)
    return {
        split: SegmentDataset(
            clips,
            split=split,
            segments_per_clip=segments_per_clip,
            augment=(split == "train"),
            seed=seed,
        )
        for split in ("train", "val", "test")
    }


def split_summary(clips: list[Clip]) -> dict[str, dict[str, int]]:
    """Clip counts per split per genre -- printed before training starts."""
    summary: dict[str, dict[str, int]] = {}
    for clip in clips:
        summary.setdefault(clip.split, {}).setdefault(clip.genre, 0)
        summary[clip.split][clip.genre] += 1
    return summary


def resolve_dataset_dir(root: Optional[str]) -> Path:
    # parents[1] is the service root (`/app` in the container, `audio-service/`
    # on a host checkout) -- the directory `data/gtzan` is mounted under.
    base = Path(root) if root else Path(__file__).resolve().parents[1] / "data" / "gtzan"
    return download(base)
