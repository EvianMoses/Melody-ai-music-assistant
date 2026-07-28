"""Held-out test evaluation: accuracy, per-class F1, confusion matrix (ML-AUD-005).

    docker compose run --rm audio-service python -m ml.evaluate

Kept separate from `train.py` for one reason: the test split must be read *once*,
after the model is chosen. Folding it into the training script makes it far too
easy to glance at test performance between epochs and start selecting on it,
which turns the held-out number into a training signal and the reported figure
into a fiction.

Two numbers are reported, and both matter:

* **segment-level** -- how the network performs on the 3-second windows it was
  trained on;
* **clip-level** -- probabilities averaged across a clip's segments, which is
  how the service actually predicts (`app/classifier.py`). This is the honest
  headline, and it is normally the higher of the two, because averaging cancels
  the odd unrepresentative window.

The confusion matrix is printed in full. On GTZAN it should show rock bleeding
into metal and country, and disco into pop -- genuinely adjacent genres. A
matrix that is *clean* on 1000 clips is evidence of leakage, not of quality.
"""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path

import torch
from torch.utils.data import DataLoader

from . import dataset as data_module
from .labels import BASELINE_MACRO_F1, GENRES, TARGET_MACRO_F1, decide
from .model import load_checkpoint
from .train import DEFAULT_CHECKPOINT, macro_f1


def per_class_report(confusion: torch.Tensor) -> list[dict]:
    rows = []
    for index, genre in enumerate(GENRES):
        true_positive = confusion[index, index].item()
        predicted = confusion[:, index].sum().item()
        actual = confusion[index, :].sum().item()
        precision = true_positive / predicted if predicted else 0.0
        recall = true_positive / actual if actual else 0.0
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
        rows.append(
            {
                "genre": genre,
                "support": actual,
                "precision": round(precision, 3),
                "recall": round(recall, 3),
                "f1": round(f1, 3),
            }
        )
    return rows


def print_confusion(confusion: torch.Tensor) -> None:
    width = max(len(name) for name in GENRES) + 1
    header = " " * width + "".join(f"{name[:6]:>7}" for name in GENRES)
    print("\nconfusion matrix (rows = true, cols = predicted)")
    print(header)
    for index, genre in enumerate(GENRES):
        cells = "".join(f"{confusion[index, column].item():>7}" for column in range(len(GENRES)))
        print(f"{genre:<{width}}{cells}")


@torch.no_grad()
def evaluate(checkpoint: Path, data_root: str | None, segments_per_clip: int = 10) -> dict:
    model, metadata = load_checkpoint(checkpoint)
    genres_dir = data_module.resolve_dataset_dir(data_root)
    clips = data_module.index_clips(genres_dir)
    data_module.assert_no_leakage(clips)

    test_set = data_module.SegmentDataset(
        clips, split="test", segments_per_clip=segments_per_clip, augment=False
    )
    loader = DataLoader(test_set, batch_size=64, shuffle=False)

    confusion = torch.zeros(len(GENRES), len(GENRES), dtype=torch.long)
    correct = total = 0
    # Accumulated per clip so the clip-level score uses the same averaging the
    # service does at inference time.
    clip_probabilities: dict[int, torch.Tensor] = defaultdict(
        lambda: torch.zeros(len(GENRES))
    )
    clip_labels: dict[int, int] = {}

    index = 0
    for waveforms, labels in loader:
        probabilities = torch.softmax(model(waveforms), dim=1)
        predictions = probabilities.argmax(dim=1)
        for true_label, predicted, row in zip(labels, predictions, probabilities):
            confusion[true_label.item(), predicted.item()] += 1
            clip_index = index // segments_per_clip
            clip_probabilities[clip_index] += row
            clip_labels[clip_index] = true_label.item()
            index += 1
        correct += int((predictions == labels).sum())
        total += labels.numel()

    segment_accuracy = correct / total if total else 0.0
    segment_f1 = macro_f1(confusion)

    clip_confusion = torch.zeros(len(GENRES), len(GENRES), dtype=torch.long)
    uncertain = 0
    for clip_index, summed in clip_probabilities.items():
        averaged = summed / segments_per_clip
        label, _, _ = decide(
            {genre: averaged[position].item() for position, genre in enumerate(GENRES)}
        )
        if label == "uncertain":
            uncertain += 1
            # An abstention is still counted against the model in the matrix, by
            # attributing it to the argmax. Excluding abstentions would let the
            # confidence policy inflate the score by dropping hard clips.
        predicted = int(averaged.argmax())
        clip_confusion[clip_labels[clip_index], predicted] += 1

    clip_correct = int(clip_confusion.diagonal().sum())
    clip_total = int(clip_confusion.sum())

    report = {
        "model_version": metadata.get("model_version"),
        "trained_at": metadata.get("trained_at"),
        "checkpoint_val_macro_f1": metadata.get("val_macro_f1"),
        "test_clips": clip_total,
        "test_segments": total,
        "segment_accuracy": round(segment_accuracy, 4),
        "segment_macro_f1": round(segment_f1, 4),
        "clip_accuracy": round(clip_correct / clip_total if clip_total else 0.0, 4),
        "clip_macro_f1": round(macro_f1(clip_confusion), 4),
        "abstained_clips": uncertain,
        "baseline_macro_f1": BASELINE_MACRO_F1,
        "target_macro_f1": TARGET_MACRO_F1,
        "per_class": per_class_report(clip_confusion),
    }
    report["meets_target"] = report["clip_macro_f1"] >= TARGET_MACRO_F1

    print(json.dumps({k: v for k, v in report.items() if k != "per_class"}, indent=2))
    print("\nper-class (clip level)")
    for row in report["per_class"]:
        print(
            f"  {row['genre']:<10} f1={row['f1']:<6} "
            f"precision={row['precision']:<6} recall={row['recall']:<6} n={row['support']}"
        )
    print_confusion(clip_confusion)

    output = checkpoint.parent / "test_report.json"
    output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"\nwritten: {output}")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--checkpoint", type=Path, default=DEFAULT_CHECKPOINT)
    parser.add_argument("--data-root", default=None)
    parser.add_argument("--segments-per-clip", type=int, default=10)
    args = parser.parse_args()
    evaluate(args.checkpoint, args.data_root, args.segments_per_clip)
