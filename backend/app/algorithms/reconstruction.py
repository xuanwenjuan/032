import numpy as np
from typing import Optional, List, Dict, Any
from app.algorithms.forward_solver import (
    ForwardSolverFDM,
    create_brain_mask,
    create_conductivity_map,
    ElectrodeConfig,
    ColeColeModel
)


FREQUENCIES = {
    "1kHz": 1e3,
    "10kHz": 1e4,
    "100kHz": 1e5
}


class LinearBackProjection:
    def __init__(self, grid_size: int = 16):
        self.grid_size = grid_size
        self.brain_mask = create_brain_mask(grid_size)
        self.electrode_config = ElectrodeConfig(grid_size)
        self.num_electrodes = self.electrode_config.num_electrodes
        self.sensitivity_matrix = self._build_sensitivity_matrix()

    def _build_sensitivity_matrix(self) -> np.ndarray:
        N = self.grid_size
        num_elec = self.num_electrodes
        num_pixels = N * N

        rows_list = []

        for src in range(num_elec):
            for sink in range(src + 1, num_elec):
                for meas in range(num_elec):
                    if meas == src or meas == sink:
                        continue

                    pos = self.electrode_config.electrode_positions[meas]
                    row_contrib = np.zeros(num_pixels)

                    for i in range(N):
                        for j in range(N):
                            if self.brain_mask[i, j]:
                                pidx = i * N + j
                                dist_to_meas = np.sqrt(
                                    (i - pos[0]) ** 2 + (j - pos[1]) ** 2
                                )
                                dist_to_src = np.sqrt(
                                    (i - self.electrode_config.electrode_positions[src][0]) ** 2 +
                                    (j - self.electrode_config.electrode_positions[src][1]) ** 2
                                )
                                dist_to_sink = np.sqrt(
                                    (i - self.electrode_config.electrode_positions[sink][0]) ** 2 +
                                    (j - self.electrode_config.electrode_positions[sink][1]) ** 2
                                )

                                weight_src = 1.0 / (dist_to_src + 1.0)
                                weight_sink = 1.0 / (dist_to_sink + 1.0)
                                weight_meas = 1.0 / (dist_to_meas + 1.0)

                                row_contrib[pidx] = (
                                    weight_src * weight_sink * weight_meas
                                )

                    rows_list.append(row_contrib)

        pixel_contributions = np.array(rows_list)
        norm_factor = np.max(np.abs(pixel_contributions)) + 1e-10
        sensitivity_matrix = pixel_contributions.T / norm_factor

        return sensitivity_matrix

    def reconstruct(
        self,
        measured_data: np.ndarray,
        reference_data: Optional[np.ndarray] = None
    ) -> np.ndarray:
        N = self.grid_size

        if reference_data is None:
            reference_data = np.zeros_like(measured_data)

        delta_V = measured_data - reference_data

        max_v = np.max(np.abs(delta_V))
        if max_v > 1e-10:
            delta_V_norm = delta_V / max_v
        else:
            delta_V_norm = delta_V

        reconstruction = self.sensitivity_matrix @ delta_V_norm

        recon_2d = reconstruction.reshape(N, N)

        recon_2d[~self.brain_mask] = 0

        min_val = np.min(recon_2d[self.brain_mask]) if np.any(self.brain_mask) else 0
        max_val = np.max(recon_2d[self.brain_mask]) if np.any(self.brain_mask) else 1

        if max_val - min_val > 1e-10:
            recon_normalized = (recon_2d - min_val) / (max_val - min_val)
        else:
            recon_normalized = np.zeros_like(recon_2d)

        recon_normalized[~self.brain_mask] = 0

        return recon_normalized


def run_single_freq_simulation(
    grid_size: int,
    edema_regions: list,
    frequency: float
) -> Dict[str, Any]:
    sigma = create_conductivity_map(grid_size, edema_regions, frequency=frequency)
    solver = ForwardSolverFDM(grid_size, frequency=frequency)
    measurements = solver.compute_measurements(sigma)

    base_sigma = create_conductivity_map(grid_size, [], frequency=frequency)
    reference_measurements = solver.compute_measurements(base_sigma)

    reconstructor = LinearBackProjection(grid_size)
    reconstruction = reconstructor.reconstruct(measurements, reference_measurements)

    return {
        "true_conductivity": sigma.tolist(),
        "reconstructed_conductivity": reconstruction.tolist()
    }


def fuse_frequency_images(
    reconstructions: Dict[str, List[List[float]]],
    weights: Optional[Dict[str, float]] = None
) -> List[List[float]]:
    if weights is None:
        weights = {"1kHz": 0.2, "10kHz": 0.5, "100kHz": 0.3}

    freq_keys = list(reconstructions.keys())
    if not freq_keys:
        return []

    N = len(reconstructions[freq_keys[0]])
    fused = np.zeros((N, N), dtype=np.float64)
    total_weight = 0.0

    for freq_key, recon in reconstructions.items():
        w = weights.get(freq_key, 0.0)
        fused += np.array(recon) * w
        total_weight += w

    if total_weight > 0:
        fused = fused / total_weight

    return fused.tolist()


def run_multifrequency_simulation(
    grid_size: int = 16,
    edema_regions: Optional[list] = None
) -> Dict[str, Any]:
    edema_regions = edema_regions or []

    freq_results = {}
    true_maps = {}
    cc = ColeColeModel()

    for freq_name, freq_val in FREQUENCIES.items():
        result = run_single_freq_simulation(grid_size, edema_regions, freq_val)
        freq_results[freq_name] = result["reconstructed_conductivity"]
        true_maps[freq_name] = result["true_conductivity"]

    fused = fuse_frequency_images(freq_results)

    edema_sigma_values = {
        f: cc.conductivity(v, "edema") for f, v in FREQUENCIES.items()
    }
    normal_sigma_values = {
        f: cc.conductivity(v, "normal") for f, v in FREQUENCIES.items()
    }

    return {
        "grid_size": grid_size,
        "reconstructions": freq_results,
        "true_conductivity_maps": true_maps,
        "fused_reconstruction": fused,
        "cole_cole_params": {
            "edema_conductivity": edema_sigma_values,
            "normal_conductivity": normal_sigma_values,
            "edema_factor": {
                f: edema_sigma_values[f] / normal_sigma_values[f]
                for f in FREQUENCIES.keys()
            }
        }
    }


def run_complete_simulation_2d(
    grid_size: int = 16,
    edema_regions: Optional[list] = None
) -> dict:
    sigma = create_conductivity_map(grid_size, edema_regions)
    solver = ForwardSolverFDM(grid_size)
    measurements = solver.compute_measurements(sigma)

    base_sigma = create_conductivity_map(grid_size)
    reference_measurements = solver.compute_measurements(base_sigma)

    reconstructor = LinearBackProjection(grid_size)
    reconstruction = reconstructor.reconstruct(measurements, reference_measurements)

    return {
        "true_conductivity": sigma.tolist(),
        "reconstructed_conductivity": reconstruction.tolist(),
        "measurements": measurements.tolist(),
        "reference_measurements": reference_measurements.tolist(),
        "grid_size": grid_size
    }
