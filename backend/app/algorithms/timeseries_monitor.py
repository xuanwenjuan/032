import numpy as np
from typing import List, Dict, Any, Optional, Tuple
from app.algorithms.reconstruction import (
    run_multifrequency_simulation,
    run_single_freq_simulation,
    FREQUENCIES
)
from app.algorithms.forward_solver import (
    create_brain_mask,
    ColeColeModel
)


def linear_regression(x: np.ndarray, y: np.ndarray) -> Tuple[float, float, float]:
    n = len(x)
    x_mean = np.mean(x)
    y_mean = np.mean(y)
    numerator = np.sum((x - x_mean) * (y - y_mean))
    denominator = np.sum((x - x_mean) ** 2)
    slope = numerator / denominator if denominator > 0 else 0.0
    intercept = y_mean - slope * x_mean
    r2 = 1.0
    if n > 2 and denominator > 0:
        ss_tot = np.sum((y - y_mean) ** 2)
        ss_res = np.sum((y - (slope * x + intercept)) ** 2)
        r2 = 1 - ss_res / ss_tot if ss_tot > 0 else 0.0
    return slope, intercept, r2


def simulate_temporal_edema_progression(
    grid_size: int = 16,
    num_scans: int = 10,
    interval_seconds: int = 30,
    initial_regions: Optional[List[Dict[str, Any]]] = None,
    expansion_rate: float = 0.08
) -> Dict[str, Any]:
    brain_mask = create_brain_mask(grid_size)
    cc = ColeColeModel()

    if initial_regions is None or len(initial_regions) == 0:
        initial_regions = [{
            "center_x": grid_size // 2,
            "center_y": grid_size // 3,
            "radius": 2,
            "conductivity_factor": 2.0
        }]

    scans = []
    edema_avg_conductivity = []
    edema_volume = []
    global_avg_conductivity = []
    times_minutes = []

    for scan_idx in range(num_scans):
        t_min = scan_idx * interval_seconds / 60.0
        times_minutes.append(t_min)

        current_regions = []
        for region in initial_regions:
            cx = region.get("center_x", grid_size // 2)
            cy = region.get("center_y", grid_size // 2)
            r0 = region.get("radius", 2)
            current_radius = min(
                int(np.floor(r0 + expansion_rate * scan_idx)),
                grid_size // 2 - 1
            )
            factor = region.get("conductivity_factor", 2.0)
            enhanced_factor = factor * (1 + 0.02 * scan_idx)
            current_regions.append({
                "center_x": cx,
                "center_y": cy,
                "radius": current_radius,
                "conductivity_factor": enhanced_factor
            })

        mf_result = run_multifrequency_simulation(grid_size, current_regions)

        fused = np.array(mf_result["fused_reconstruction"])

        edema_mask = np.zeros_like(fused, dtype=bool)
        for region in current_regions:
            cx = region["center_x"]
            cy = region["center_y"]
            r = region["radius"]
            for i in range(grid_size):
                for j in range(grid_size):
                    if np.sqrt((i - cx) ** 2 + (j - cy) ** 2) <= r:
                        edema_mask[i, j] = True
        edema_mask = edema_mask & brain_mask

        if edema_mask.sum() > 0:
            avg_edema_sigma = float(np.mean(fused[edema_mask]))
        else:
            avg_edema_sigma = 0.0
        edema_avg_conductivity.append(avg_edema_sigma)

        edema_volume.append(int(edema_mask.sum()))

        if brain_mask.sum() > 0:
            global_avg = float(np.mean(fused[brain_mask]))
        else:
            global_avg = 0.0
        global_avg_conductivity.append(global_avg)

        scan_data = {
            "scan_index": scan_idx,
            "time_minutes": t_min,
            "regions": current_regions,
            "reconstructions": mf_result["reconstructions"],
            "fused_reconstruction": mf_result["fused_reconstruction"],
            "edema_avg_conductivity": avg_edema_sigma,
            "edema_volume_pixels": int(edema_mask.sum()),
            "global_avg_conductivity": global_avg
        }
        scans.append(scan_data)

    x = np.array(times_minutes)
    y_sigma = np.array(edema_avg_conductivity)
    y_vol = np.array(edema_volume, dtype=np.float64)

    slope_sigma, intercept_sigma, r2_sigma = linear_regression(x, y_sigma)
    slope_vol, intercept_vol, r2_vol = linear_regression(x, y_vol)

    predict_time = 30.0
    predict_sigma = slope_sigma * predict_time + intercept_sigma
    predict_vol = int(slope_vol * predict_time + intercept_vol)

    severity = "MILD"
    if slope_sigma > 0.008:
        severity = "SEVERE"
    elif slope_sigma > 0.004:
        severity = "MODERATE"

    warning_messages = []
    if severity == "SEVERE":
        warning_messages.append("⚠️ 严重警告：水肿快速扩展中！电导率增长速度显著高于正常范围")
        warning_messages.append("建议：立即通知神经外科团队，考虑手术干预")
    elif severity == "MODERATE":
        warning_messages.append("⚠️ 警告：水肿呈中度扩展趋势")
        warning_messages.append("建议：加强监测频率，考虑使用脱水药物")
    else:
        warning_messages.append("✅ 水肿扩展速度在可控范围内")
        warning_messages.append("建议：保持常规监测")

    if slope_vol > 0.5:
        warning_messages.append("⚠️ 注意：水肿体积增长速度较快")

    sigma_per_frequency = {}
    for freq_name in FREQUENCIES.keys():
        freq_sigma_series = []
        for scan in scans:
            recon = np.array(scan["reconstructions"][freq_name])
            mask = np.zeros_like(recon, dtype=bool)
            for region in scan["regions"]:
                cx, cy, r = region["center_x"], region["center_y"], region["radius"]
                for i in range(grid_size):
                    for j in range(grid_size):
                        if np.sqrt((i - cx) ** 2 + (j - cy) ** 2) <= r:
                            mask[i, j] = True
            mask = mask & brain_mask
            if mask.sum() > 0:
                freq_sigma_series.append(float(np.mean(recon[mask])))
            else:
                freq_sigma_series.append(0.0)
        sigma_per_frequency[freq_name] = freq_sigma_series

    return {
        "num_scans": num_scans,
        "interval_seconds": interval_seconds,
        "times_minutes": times_minutes,
        "scans": scans,
        "time_series": {
            "edema_avg_conductivity": edema_avg_conductivity,
            "edema_volume_pixels": edema_volume,
            "global_avg_conductivity": global_avg_conductivity,
            "per_frequency_edema_sigma": sigma_per_frequency
        },
        "prediction": {
            "conductivity_slope_per_min": round(slope_sigma, 6),
            "conductivity_intercept": round(intercept_sigma, 6),
            "conductivity_r2": round(r2_sigma, 4),
            "volume_slope_per_min": round(slope_vol, 4),
            "volume_intercept": round(intercept_vol, 4),
            "volume_r2": round(r2_vol, 4),
            "predicted_30min_conductivity": round(predict_sigma, 4),
            "predicted_30min_volume_pixels": predict_vol,
            "severity_level": severity
        },
        "warnings": warning_messages
    }
