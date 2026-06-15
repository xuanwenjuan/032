import base64
import io
import numpy as np
from PIL import Image
from typing import List, Optional


def matrix_to_base64(matrix: List[List[float]], colormap: str = "jet") -> str:
    arr = np.array(matrix, dtype=np.float64)
    arr_norm = (arr - arr.min()) / (arr.max() - arr.min() + 1e-10)

    cmaps = {
        "jet": _jet_colormap,
        "hot": _hot_colormap,
        "viridis": _viridis_colormap
    }
    cmap_fn = cmaps.get(colormap, _jet_colormap)
    rgb = cmap_fn(arr_norm)

    img = Image.fromarray((rgb * 255).astype(np.uint8))
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    img_bytes = buffer.getvalue()
    return base64.b64encode(img_bytes).decode("utf-8")


def _jet_colormap(x: np.ndarray) -> np.ndarray:
    r = np.clip(1.5 - np.abs(4 * x - 3), 0, 1)
    g = np.clip(1.5 - np.abs(4 * x - 2), 0, 1)
    b = np.clip(1.5 - np.abs(4 * x - 1), 0, 1)
    return np.stack([r, g, b], axis=-1)


def _hot_colormap(x: np.ndarray) -> np.ndarray:
    r = np.clip(1.5 * x / 0.75, 0, 1)
    g = np.clip(1.5 * (x - 0.33) / 0.67, 0, 1)
    b = np.clip(2 * (x - 0.67), 0, 1)
    return np.stack([r, g, b], axis=-1)


def _viridis_colormap(x: np.ndarray) -> np.ndarray:
    t = x
    r = 0.267 + t * (0.082 + t * (-0.538 + t * 1.265))
    g = 0.0049 + t * (1.404 + t * (-0.214 + t * (-0.227)))
    b = 0.329 + t * (1.514 + t * (-2.012 + t * 0.682))
    return np.stack([
        np.clip(r, 0, 1),
        np.clip(g, 0, 1),
        np.clip(b, 0, 1)
    ], axis=-1)


def drawn_mask_to_edema_regions(mask: List[List[int]], conductivity_factor: float = 2.0) -> List[dict]:
    regions = []
    arr = np.array(mask, dtype=np.int32)
    visited = np.zeros_like(arr, dtype=bool)
    grid_h, grid_w = arr.shape

    for i in range(grid_h):
        for j in range(grid_w):
            if arr[i, j] > 0 and not visited[i, j]:
                pixels = []
                stack = [(i, j)]
                while stack:
                    x, y = stack.pop()
                    if 0 <= x < grid_h and 0 <= y < grid_w and arr[x, y] > 0 and not visited[x, y]:
                        visited[x, y] = True
                        pixels.append((x, y))
                        for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                            stack.append((x + dx, y + dy))

                if pixels:
                    pixels_arr = np.array(pixels)
                    cx = int(np.mean(pixels_arr[:, 0]))
                    cy = int(np.mean(pixels_arr[:, 1]))
                    dists = np.sqrt(np.sum((pixels_arr - np.array([cx, cy])) ** 2, axis=1))
                    radius = max(1, int(np.ceil(np.max(dists))))
                    regions.append({
                        "center_x": cx,
                        "center_y": cy,
                        "radius": radius,
                        "conductivity_factor": conductivity_factor
                    })

    return regions
