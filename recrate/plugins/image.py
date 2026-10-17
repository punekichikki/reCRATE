"""Image plugin: label masks, object counts and segmentation metrics.

Owner: Person 4. The metric (object-level F1 over IoU thresholds, as in Caicedo et al. 2019)
is implemented and tested with numpy only. File loading and profiling are left as TODOs because
they need tifffile / scikit-image (install with `pip install -e ".[image]"`).
"""
from typing import Any

import numpy as np

from .base import Comparison, DataPlugin
from .tabular import compare_values

DEFAULT_THRESHOLDS = tuple(round(0.50 + 0.05 * i, 2) for i in range(9))  # 0.50, 0.55, ..., 0.90


def iou_matrix(truth: np.ndarray, pred: np.ndarray) -> np.ndarray:
    """IoU between every true object and every predicted object. Label 0 is background.

    Returns an array of shape (n_true, n_pred), rows/cols ordered by sorted label value.
    """
    if truth.shape != pred.shape:
        raise ValueError(f"shape mismatch: {truth.shape} vs {pred.shape}")
    t_ids = np.unique(truth[truth > 0])
    p_ids = np.unique(pred[pred > 0])
    if len(t_ids) == 0 or len(p_ids) == 0:
        return np.zeros((len(t_ids), len(p_ids)))
    t_idx = {v: i for i, v in enumerate(t_ids)}
    p_idx = {v: i for i, v in enumerate(p_ids)}
    inter = np.zeros((len(t_ids), len(p_ids)))
    both = (truth > 0) & (pred > 0)
    pairs, counts = np.unique(np.stack([truth[both], pred[both]], axis=1), axis=0, return_counts=True)
    for (t, p), n in zip(pairs, counts):
        inter[t_idx[t], p_idx[p]] = n
    t_area = np.array([(truth == v).sum() for v in t_ids])[:, None]
    p_area = np.array([(pred == v).sum() for v in p_ids])[None, :]
    return inter / (t_area + p_area - inter)


def f1_at_thresholds(truth: np.ndarray, pred: np.ndarray, thresholds=DEFAULT_THRESHOLDS) -> dict:
    """Object-level F1 at each IoU threshold, and their mean.

    With thresholds >= 0.5 each object can match at most one other, so a match is simply IoU > t.
    """
    iou = iou_matrix(truth, pred)
    n_true, n_pred = iou.shape
    out = {}
    for t in thresholds:
        tp = int((iou > t).sum())
        fp, fn = n_pred - tp, n_true - tp
        out[t] = 2 * tp / (2 * tp + fp + fn) if (tp + fp + fn) else 1.0
    return {"per_threshold": out, "mean_f1": float(np.mean(list(out.values()))), "n_true": n_true, "n_pred": n_pred}


def count_objects(labels: np.ndarray) -> int:
    return int(len(np.unique(labels[labels > 0])))


class ImagePlugin(DataPlugin):
    name = "image"
    EXTENSIONS = (".tif", ".tiff", ".png")

    def can_handle(self, path: str) -> bool:
        return path.lower().endswith(self.EXTENSIONS)

    def load(self, path: str) -> Any:
        # TODO(Person 4): tifffile.imread for TIFF; skimage.io.imread for PNG.
        # BBBC039 masks are colour PNGs with one colour per nucleus: decode to a label matrix.
        raise NotImplementedError("Image loading needs the [image] extra; see TODO in plugins/image.py")

    def profile(self, image: Any) -> dict:
        # TODO(Person 4): shape, dtype / bit depth, intensity range, pixel size from metadata.
        raise NotImplementedError

    def extract(self, data: Any, output_key) -> Any:
        outputs = data["outputs"] if isinstance(data, dict) and "outputs" in data else data
        return [outputs[k] for k in output_key] if isinstance(output_key, list) else outputs[output_key]

    def has_outputs(self, data: Any, output_key) -> bool:
        keys = output_key if isinstance(output_key, list) else [output_key]
        return all(k in data.get("outputs", {}) for k in keys)

    def compare(self, observed: Any, claim: dict) -> Comparison:
        # Scalars derived from images (mean F1, counts) compare like any number.
        return compare_values(observed, claim["rc:expectedValue"], claim["rc:comparison"],
                              tolerance=claim.get("rc:toleranceValue", 0.0),
                              decimal_places=claim.get("rc:decimalPlaces"),
                              interval=claim.get("rc:interval", 0.95))

    # TODO(Person 4): independent_checks -> count objects from reference masks; re-implemented
    # F1 vs the repo's evaluation.py; Otsu re-segmentation count; pixel-size check.
    # TODO(Person 4): check_compatibility -> pixel size, bit depth, channel, intensity range.
