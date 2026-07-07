"""DeepForest dead-tree detector (primary), implementing the common detector interface.

DeepForest is a torchvision/RetinaNet tree-crown detector. We pair its pretrained
crown model (``weecology/deepforest-tree``) with the alive/dead CropModel
(``weecology/cropmodel-deadtrees``): detect all crowns, classify each alive/dead,
keep only the dead ones, and emit them as ``display="Dead Tree"`` detections.

DeepForest does its OWN tiling (predict_tile), so it does not use SAHI. It runs
alongside the SAHI+YOLO fire/smoke detector; the pipeline merges the outputs.

Two DeepForest 2.1.0 quirks are handled here:
  - CropModel.load_model() (PyTorchModelHubMixin) does not rebuild the ResNet on
    newer huggingface_hub; we repair it by calling create_model() and loading the
    HF safetensors weights into crop.model.
  - predict_tile's Lightning rich progress bar crashes on a non-UTF-8 (e.g. GBK)
    Windows console; we disable it via create_trainer(enable_progress_bar=False).
"""

from __future__ import annotations

import inspect
from typing import Callable, Optional

from .config import Settings
from .device import pick_device
from .types import Detection

ProgressFn = Optional[Callable[[str], None]]


def deepforest_available() -> bool:
    """True if the deepforest package can be imported."""
    try:
        import deepforest  # noqa: F401

        return True
    except Exception:
        return False


def _configure_quiet() -> None:
    """Reduce Lightning/rasterio noise and enable Tensor-Core matmul on the GPU."""
    import logging
    import warnings

    try:
        import torch

        torch.set_float32_matmul_precision("high")  # uses RTX 4090 Tensor Cores
    except Exception:
        pass
    for name in ("pytorch_lightning", "lightning.pytorch", "lightning"):
        logging.getLogger(name).setLevel(logging.ERROR)
    warnings.filterwarnings("ignore", category=UserWarning, module="pytorch_lightning")
    warnings.filterwarnings("ignore", module="rasterio")


def _repair_crop_model(crop, repo_id: str) -> None:
    """Rebuild crop.model and load real weights (DeepForest 2.1.0 + new hub bug).

    After CropModel.load_model, crop.model can be a metadata dict instead of the
    ResNet. Rebuild the architecture and load the HF safetensors weights.
    """
    import torch

    if isinstance(getattr(crop, "model", None), torch.nn.Module):
        return  # already fine on this version
    from huggingface_hub import hf_hub_download
    from safetensors.torch import load_file

    num_classes = int(getattr(crop, "num_classes", 2))
    crop.create_model(num_classes=num_classes)
    sd = load_file(hf_hub_download(repo_id, "model.safetensors"))
    model_sd = {k[len("model."):]: v for k, v in sd.items() if k.startswith("model.")}
    crop.model.load_state_dict(model_sd, strict=False)


class DeepForestDeadTreeDetector:
    """Crown detection (DeepForest) + alive/dead classification -> dead-tree boxes."""

    name = "deepforest-deadtree"

    def __init__(self, settings: Settings, device: str | None = None, log: ProgressFn = None):
        self.settings = settings
        self.device = device or pick_device()
        self._log = log
        self._model = None
        self._crop = None
        self._load()

    def _say(self, msg: str) -> None:
        if callable(self._log):
            self._log(msg)

    # ------------------------------------------------------------------ loading
    def _load(self) -> None:
        _configure_quiet()
        from deepforest import main as df_main

        s = self.settings
        self._say(f"[deadtree] loading DeepForest crown model ({s.df_crown_model})...")
        model = df_main.deepforest()
        try:
            model.load_model(s.df_crown_model)
        except Exception:
            if hasattr(model, "use_release"):
                model.use_release()
            else:
                raise
        # Disable the Lightning rich progress bar (crashes on non-UTF-8 consoles)
        # and the logger tip. predict_tile reuses this trainer.
        try:
            model.create_trainer(enable_progress_bar=False, logger=False)
        except Exception:
            pass
        try:
            model.to("cuda" if self.device.startswith("cuda") else self.device)
        except Exception:
            pass
        self._model = model

        # Alive/dead CropModel, with the load repair.
        self._say(f"[deadtree] loading alive/dead classifier ({s.df_dead_model})...")
        try:
            from deepforest.model import CropModel

            crop = CropModel.load_model(s.df_dead_model)
            _repair_crop_model(crop, s.df_dead_model)
            crop.eval()
            self._crop = crop
        except Exception as e:
            self._crop = None
            self._say(
                f"[deadtree] alive/dead classifier failed to load ({e}); "
                "dead-tree detection disabled for this run."
            )

    # ------------------------------------------------------------------ predict
    def _predict_tile(self, image_path: str):
        m = self._model
        s = self.settings
        kwargs = dict(patch_size=s.df_patch_size, patch_overlap=s.df_patch_overlap)
        if self._crop is not None:
            kwargs["crop_model"] = self._crop
        sig = set(inspect.signature(m.predict_tile).parameters)
        if "path" in sig:
            return m.predict_tile(path=image_path, **kwargs)
        if "raster_path" in sig:
            return m.predict_tile(raster_path=image_path, **kwargs)
        return m.predict_tile(image_path, **kwargs)

    @staticmethod
    def _bbox(row):
        if all(c in row and row[c] is not None for c in ("xmin", "ymin", "xmax", "ymax")):
            return (float(row["xmin"]), float(row["ymin"]), float(row["xmax"]), float(row["ymax"]))
        geom = row.get("geometry") if hasattr(row, "get") else None
        if geom is not None and hasattr(geom, "bounds"):
            minx, miny, maxx, maxy = geom.bounds
            return (float(minx), float(miny), float(maxx), float(maxy))
        return None

    def predict(self, image) -> list[Detection]:
        # Without a working alive/dead classifier we cannot identify DEAD trees, so
        # emit nothing rather than flagging every crown (avoids false positives).
        if self._model is None or self._crop is None:
            return []

        df = self._predict_tile(str(image))
        if df is None or len(df) == 0 or "cropmodel_label" not in df.columns:
            return []

        s = self.settings
        dead_label = s.df_dead_label.lower()
        detections: list[Detection] = []
        for _, row in df.iterrows():
            crown_score = float(row.get("score", 1.0) or 1.0)
            if crown_score < s.conf_threshold:
                continue
            if str(row["cropmodel_label"]).lower() != dead_label:
                continue  # keep only crowns classified as dead
            box = self._bbox(row)
            if box is None:
                continue
            score = float(row.get("cropmodel_score", crown_score) or crown_score)
            detections.append(
                Detection(cls_name="dead_tree", display="Dead Tree", score=score, xyxy=box)
            )
        return detections
