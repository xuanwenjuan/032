import numpy as np
from typing import Optional
from app.algorithms.forward_solver import (
    ForwardSolverFDM,
    create_brain_mask,
    create_conductivity_map,
    ElectrodeConfig
)


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
