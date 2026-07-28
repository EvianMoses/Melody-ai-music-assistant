"""Training loop for the genre classifier (ML-AUD-004).

Run inside the audio-service container, where torch and torchaudio live::

    docker compose run --rm audio-service python -m ml.train
    docker compose run --rm audio-service python -m ml.train --epochs 40 --lr 5e-4

Everything that decides the outcome is a named constant or a CLI flag, and all
of it is written into the checkpoint, so a stored prediction can be traced back
to the exact configuration that produced it.

**Preprocessing** (in `model.py`, deliberately inside the network): mono,
22.05 kHz, 3 s segments, 128-bin mel spectrogram at n_fft 2048 / hop 512,
amplitude to dB with an 80 dB floor, then per-example standardization.

**Augmentation**, all label-preserving:
* random segment offset per epoch (`dataset.SegmentDataset`)
* gain jitter ±30% (same)
* SpecAugment-style frequency and time masking (below)

Pitch-shift and time-stretch are deliberately *not* used: they alter the key and
tempo that partly define a genre, so they would teach the model to ignore a real
signal.

**Model selection.** The checkpoint kept is the one with the best *validation*
macro-F1, never the last epoch and never anything computed on test. The test
split is read exactly once, by `evaluate.py`, after training has finished.
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import torch
import torchaudio
from torch import nn
from torch.utils.data import DataLoader

from . import dataset as data_module
from .labels import GENRES, MODEL_VERSION, TARGET_MACRO_F1
from .model import GenreCNN

DEFAULT_CHECKPOINT = Path(__file__).resolve().parent / "checkpoints" / "genre_cnn.pt"

# Hyperparameters (ML-AUD-004). Defaults chosen for a CPU-only run on ~7000
# training segments; every one is overridable from the command line.
DEFAULTS = {
    "epochs": 30,
    "batch_size": 64,
    "lr": 1e-3,
    "weight_decay": 1e-4,
    "label_smoothing": 0.1,
    "segments_per_clip": 10,
    "patience": 8,
    "seed": 1337,
}


class SpecAugment(nn.Module):
    """Frequency and time masking applied to the batch during training.

    Applied to the *waveform-derived* spectrogram inside the training step
    rather than in the dataset, because the spectrogram only exists once the
    model has computed it. Masking teaches the network not to depend on any
    single band or instant -- the audio analogue of random erasing.
    """

    def __init__(self, freq_mask: int = 16, time_mask: int = 24) -> None:
        super().__init__()
        self.freq = torchaudio.transforms.FrequencyMasking(freq_mask_param=freq_mask)
        self.time = torchaudio.transforms.TimeMasking(time_mask_param=time_mask)

    def forward(self, spectrogram: torch.Tensor) -> torch.Tensor:
        return self.time(self.freq(spectrogram))


def macro_f1(confusion: torch.Tensor) -> float:
    """Macro-F1 from a confusion matrix (rows = true, cols = predicted).

    Computed here rather than imported so the training container needs no
    scikit-learn, and so the definition is visible: per-class F1, then an
    unweighted mean, which is what makes a neglected genre count as much as a
    popular one.
    """
    f1_scores = []
    for index in range(confusion.size(0)):
        true_positive = confusion[index, index].item()
        predicted = confusion[:, index].sum().item()
        actual = confusion[index, :].sum().item()
        precision = true_positive / predicted if predicted else 0.0
        recall = true_positive / actual if actual else 0.0
        f1_scores.append(
            2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
        )
    return sum(f1_scores) / len(f1_scores)


@torch.no_grad()
def evaluate_split(model: GenreCNN, loader: DataLoader, device: str) -> tuple[float, float, torch.Tensor]:
    model.eval()
    confusion = torch.zeros(len(GENRES), len(GENRES), dtype=torch.long)
    correct = total = 0
    for waveforms, labels in loader:
        logits = model(waveforms.to(device))
        predictions = logits.argmax(dim=1).cpu()
        for true_label, predicted in zip(labels, predictions):
            confusion[true_label.item(), predicted.item()] += 1
        correct += int((predictions == labels).sum())
        total += labels.numel()
    accuracy = correct / total if total else 0.0
    return accuracy, macro_f1(confusion), confusion


def train(args: argparse.Namespace) -> dict:
    torch.manual_seed(args.seed)
    device = "cuda" if torch.cuda.is_available() else "cpu"

    genres_dir = data_module.resolve_dataset_dir(args.data_root)
    clips = data_module.index_clips(genres_dir)
    data_module.assert_no_leakage(clips)
    print("clips per split:", json.dumps(data_module.split_summary(clips), indent=2))

    splits = data_module.build_splits(
        genres_dir, segments_per_clip=args.segments_per_clip, seed=args.seed
    )
    loaders = {
        name: DataLoader(
            subset,
            batch_size=args.batch_size,
            shuffle=(name == "train"),
            num_workers=args.workers,
            drop_last=(name == "train"),
        )
        for name, subset in splits.items()
    }

    model = GenreCNN().to(device)
    spec_augment = SpecAugment().to(device)
    # Label smoothing: GTZAN's labels are known to contain errors, so training
    # the model to be *certain* about them would fit the noise.
    criterion = nn.CrossEntropyLoss(label_smoothing=args.label_smoothing)
    optimizer = torch.optim.AdamW(
        model.parameters(), lr=args.lr, weight_decay=args.weight_decay
    )
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=args.epochs)

    best_f1 = 0.0
    best_epoch = -1
    history: list[dict] = []
    started = time.time()

    for epoch in range(args.epochs):
        model.train()
        running_loss = 0.0
        batches = 0
        for waveforms, labels in loaders["train"]:
            waveforms, labels = waveforms.to(device), labels.to(device)

            # Masking has to happen after the mel transform, so the forward pass
            # is split here rather than calling model(waveform) directly.
            spectrogram = model.to_db(model.mel(waveforms.unsqueeze(1)))
            mean = spectrogram.mean(dim=(2, 3), keepdim=True)
            std = spectrogram.std(dim=(2, 3), keepdim=True).clamp_min(1e-5)
            spectrogram = spec_augment((spectrogram - mean) / std)
            logits = model.head(model.pool(model.features(spectrogram)))

            loss = criterion(logits, labels)
            optimizer.zero_grad(set_to_none=True)
            loss.backward()
            optimizer.step()
            running_loss += loss.item()
            batches += 1
        scheduler.step()

        val_accuracy, val_f1, _ = evaluate_split(model, loaders["val"], device)
        history.append(
            {
                "epoch": epoch,
                "train_loss": round(running_loss / max(1, batches), 4),
                "val_accuracy": round(val_accuracy, 4),
                "val_macro_f1": round(val_f1, 4),
                "lr": round(scheduler.get_last_lr()[0], 6),
            }
        )
        print(json.dumps(history[-1]))

        if val_f1 > best_f1:
            best_f1, best_epoch = val_f1, epoch
            args.checkpoint.parent.mkdir(parents=True, exist_ok=True)
            torch.save(
                {
                    "state_dict": model.state_dict(),
                    "genres": list(GENRES),
                    "model_version": MODEL_VERSION,
                    "val_macro_f1": round(val_f1, 4),
                    "val_accuracy": round(val_accuracy, 4),
                    "epoch": epoch,
                    "hyperparameters": {
                        key: getattr(args, key)
                        for key in DEFAULTS
                        if hasattr(args, key)
                    },
                    "trained_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                },
                args.checkpoint,
            )
        elif epoch - best_epoch >= args.patience:
            print(f"early stop: no val improvement for {args.patience} epochs")
            break

    summary = {
        "best_val_macro_f1": round(best_f1, 4),
        "best_epoch": best_epoch,
        "target_macro_f1": TARGET_MACRO_F1,
        "meets_target": best_f1 >= TARGET_MACRO_F1,
        "minutes": round((time.time() - started) / 60, 1),
        "checkpoint": str(args.checkpoint),
        "history": history,
    }
    print(json.dumps({k: v for k, v in summary.items() if k != "history"}, indent=2))
    (args.checkpoint.parent / "training_history.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )
    return summary


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    for name, value in DEFAULTS.items():
        parser.add_argument(f"--{name.replace('_', '-')}", type=type(value), default=value)
    parser.add_argument("--data-root", default=None, help="Where GTZAN lives/downloads to.")
    parser.add_argument("--checkpoint", type=Path, default=DEFAULT_CHECKPOINT)
    parser.add_argument("--workers", type=int, default=2)
    return parser


if __name__ == "__main__":
    train(build_parser().parse_args())
