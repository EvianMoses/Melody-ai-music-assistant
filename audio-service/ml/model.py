"""Mel-spectrogram CNN for genre classification (ML-AUD-003).

A spectrogram *is* an image -- frequency on one axis, time on the other -- so a
small convolutional network is the appropriate architecture, and the plan
explicitly permits "a pretrained audio model **or** spectrogram-based network".
This is the latter, chosen over fine-tuning something like AST for two reasons:

* it trains to a reportable result on CPU within the submission window, where a
  transformer would not, and an unmeasured model is worth nothing (ML-AUD-005);
* every layer is inspectable, which is the point of the exercise.

The mel transform lives *inside* the module rather than in the data loader. That
is the single most useful decision here: it makes the checkpoint self-contained,
so training and serving cannot drift apart on `n_mels` or `hop_length`. A
preprocessing mismatch between the two is the classic silent failure -- the
model still returns confident answers, they are just wrong.
"""

from __future__ import annotations

import torch
from torch import nn
import torchaudio

from .labels import GENRES

# Shared by training and inference. Changing any of these invalidates existing
# checkpoints, which is why they live next to the model and not in a config file
# somebody could edit independently.
SAMPLE_RATE = 22_050
SEGMENT_SECONDS = 3.0
SEGMENT_SAMPLES = int(SAMPLE_RATE * SEGMENT_SECONDS)
N_FFT = 2048
HOP_LENGTH = 512
N_MELS = 128


class _ConvBlock(nn.Module):
    """Conv -> BatchNorm -> ReLU -> MaxPool.

    BatchNorm before the activation, which matters more than usual here: mel
    magnitudes vary by orders of magnitude between a quiet jazz clip and a
    mastered metal one, and without normalization the loudest genre dominates
    the early gradients.
    """

    def __init__(self, in_channels: int, out_channels: int) -> None:
        super().__init__()
        self.block = nn.Sequential(
            nn.Conv2d(in_channels, out_channels, kernel_size=3, padding=1, bias=False),
            nn.BatchNorm2d(out_channels),
            nn.ReLU(inplace=True),
            nn.MaxPool2d(2),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.block(x)


class GenreCNN(nn.Module):
    """Waveform in, genre logits out.

    Taking a raw waveform rather than a precomputed spectrogram keeps the
    contract simple: callers never need to know the transform parameters.
    """

    def __init__(self, num_classes: int = len(GENRES), dropout: float = 0.3) -> None:
        super().__init__()
        self.mel = torchaudio.transforms.MelSpectrogram(
            sample_rate=SAMPLE_RATE,
            n_fft=N_FFT,
            hop_length=HOP_LENGTH,
            n_mels=N_MELS,
        )
        # Log scale: hearing is logarithmic in amplitude, and linear mel power
        # gives a handful of huge values and a sea of near-zeros.
        self.to_db = torchaudio.transforms.AmplitudeToDB(top_db=80.0)

        self.features = nn.Sequential(
            _ConvBlock(1, 32),
            _ConvBlock(32, 64),
            _ConvBlock(64, 128),
            _ConvBlock(128, 128),
        )
        # Global pooling instead of a flatten: the classifier then depends on
        # *what* is present, not on where in the 3 seconds it happened, and the
        # network accepts a segment of any length at inference time.
        self.pool = nn.AdaptiveAvgPool2d(1)
        self.head = nn.Sequential(
            nn.Flatten(),
            nn.Dropout(dropout),
            nn.Linear(128, num_classes),
        )

    def forward(self, waveform: torch.Tensor) -> torch.Tensor:
        """`waveform`: (batch, samples) mono at SAMPLE_RATE."""
        if waveform.dim() == 2:
            waveform = waveform.unsqueeze(1)  # (batch, 1, samples)
        spectrogram = self.to_db(self.mel(waveform))
        # Per-example standardization. Without it the model can learn mastering
        # loudness as a genre cue, which generalizes to nothing.
        mean = spectrogram.mean(dim=(2, 3), keepdim=True)
        std = spectrogram.std(dim=(2, 3), keepdim=True).clamp_min(1e-5)
        spectrogram = (spectrogram - mean) / std

        return self.head(self.pool(self.features(spectrogram)))


def load_checkpoint(path, device: str = "cpu") -> tuple[GenreCNN, dict]:
    """Restore a trained model plus the metadata saved with it.

    `weights_only=True` because a checkpoint is untrusted input as soon as it is
    downloaded rather than trained locally: the legacy pickle path can execute
    arbitrary code on load.
    """
    payload = torch.load(path, map_location=device, weights_only=True)
    model = GenreCNN(num_classes=len(payload.get("genres", GENRES)))
    model.load_state_dict(payload["state_dict"])
    model.eval()
    metadata = {key: value for key, value in payload.items() if key != "state_dict"}
    return model, metadata
