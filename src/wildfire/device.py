"""Compute-device selection: CUDA (any NVIDIA GPU) -> MPS (Apple Silicon) -> CPU."""

from __future__ import annotations

import functools


@functools.lru_cache(maxsize=1)
def pick_device() -> str:
    """Return the best available torch/ultralytics device string.

    Order: CUDA -> MPS -> CPU. Falls back to "cpu" if torch is not importable,
    so the rest of the app can still be inspected without a torch install.
    """
    try:
        import torch
    except Exception:  # torch missing or broken install
        return "cpu"

    if torch.cuda.is_available():
        return "cuda:0"
    mps = getattr(torch.backends, "mps", None)
    if mps is not None and mps.is_available():
        return "mps"
    return "cpu"


def device_label() -> str:
    """Human-readable device description for logs/UI (e.g. 'cuda:0 (<GPU name>)')."""
    dev = pick_device()
    try:
        import torch

        if dev.startswith("cuda"):
            return f"{dev} ({torch.cuda.get_device_name(0)})"
    except Exception:
        pass
    return dev
