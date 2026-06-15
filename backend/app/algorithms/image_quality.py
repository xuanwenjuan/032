import numpy as np
from typing import Dict, Any, Tuple, List


def compute_mse(original: np.ndarray, reconstructed: np.ndarray, mask: np.ndarray = None) -> float:
    if mask is not None:
        o = original[mask]
        r = reconstructed[mask]
    else:
        o = original.flatten()
        r = reconstructed.flatten()
    if len(o) == 0:
        return 0.0
    return float(np.mean((o - r) ** 2))


def compute_rmse(original: np.ndarray, reconstructed: np.ndarray, mask: np.ndarray = None) -> float:
    return float(np.sqrt(compute_mse(original, reconstructed, mask)))


def compute_mae(original: np.ndarray, reconstructed: np.ndarray, mask: np.ndarray = None) -> float:
    if mask is not None:
        o = original[mask]
        r = reconstructed[mask]
    else:
        o = original.flatten()
        r = reconstructed.flatten()
    if len(o) == 0:
        return 0.0
    return float(np.mean(np.abs(o - r)))


def compute_ssim(
    original: np.ndarray,
    reconstructed: np.ndarray,
    mask: np.ndarray = None,
    K1: float = 0.01,
    K2: float = 0.03,
    L: float = None
) -> float:
    if mask is not None:
        o = original[mask].astype(np.float64)
        r = reconstructed[mask].astype(np.float64)
    else:
        o = original.flatten().astype(np.float64)
        r = reconstructed.flatten().astype(np.float64)
    if len(o) < 2:
        return 1.0
    if L is None:
        L = max(o.max(), r.max()) - min(o.min(), r.min())
        if L == 0:
            L = 1.0
    C1 = (K1 * L) ** 2
    C2 = (K2 * L) ** 2
    mu_o = np.mean(o)
    mu_r = np.mean(r)
    sigma_o2 = np.var(o, ddof=0)
    sigma_r2 = np.var(r, ddof=0)
    sigma_or = np.mean((o - mu_o) * (r - mu_r))
    numerator = (2 * mu_o * mu_r + C1) * (2 * sigma_or + C2)
    denominator = (mu_o ** 2 + mu_r ** 2 + C1) * (sigma_o2 + sigma_r2 + C2)
    if denominator == 0:
        return 1.0
    return float(numerator / denominator)


def compute_psnr(original: np.ndarray, reconstructed: np.ndarray, mask: np.ndarray = None) -> float:
    mse = compute_mse(original, reconstructed, mask)
    if mse <= 1e-12:
        return 100.0
    if mask is not None:
        peak = float(original[mask].max())
    else:
        peak = float(original.max())
    if peak <= 0:
        peak = 1.0
    return float(20 * np.log10(peak / np.sqrt(mse)))


def compute_correlation(original: np.ndarray, reconstructed: np.ndarray, mask: np.ndarray = None) -> float:
    if mask is not None:
        o = original[mask]
        r = reconstructed[mask]
    else:
        o = original.flatten()
        r = reconstructed.flatten()
    if len(o) < 2:
        return 1.0
    std_o = np.std(o)
    std_r = np.std(r)
    if std_o == 0 or std_r == 0:
        return 0.0
    return float(np.corrcoef(o, r)[0, 1])


def compute_all_metrics(
    original: np.ndarray,
    reconstructed: np.ndarray,
    mask: np.ndarray = None
) -> Dict[str, float]:
    return {
        "mse": compute_mse(original, reconstructed, mask),
        "rmse": compute_rmse(original, reconstructed, mask),
        "mae": compute_mae(original, reconstructed, mask),
        "ssim": compute_ssim(original, reconstructed, mask),
        "psnr": compute_psnr(original, reconstructed, mask),
        "correlation": compute_correlation(original, reconstructed, mask)
    }


def quality_score(metrics: Dict[str, float]) -> float:
    w_ssim = 0.4
    w_corr = 0.3
    w_rmse = 0.2
    w_psnr = 0.1
    ssim_score = max(0.0, min(1.0, metrics["ssim"]))
    corr_score = max(0.0, min(1.0, metrics["correlation"]))
    rmse_norm = 1.0 / (1.0 + metrics["rmse"] * 10)
    rmse_score = max(0.0, min(1.0, rmse_norm))
    psnr_norm = min(1.0, metrics["psnr"] / 60.0)
    psnr_score = max(0.0, min(1.0, psnr_norm))
    return float(w_ssim * ssim_score + w_corr * corr_score + w_rmse * rmse_score + w_psnr * psnr_score)
