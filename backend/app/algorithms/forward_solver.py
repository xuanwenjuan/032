import numpy as np
from typing import List, Tuple, Optional
from app.core.config import settings


class ElectrodeConfig:
    def __init__(self, grid_size: int = 16, num_electrodes: int = 16):
        self.grid_size = grid_size
        self.num_electrodes = num_electrodes
        self.electrode_positions = self._place_electrodes()

    def _place_electrodes(self) -> List[Tuple[int, int]]:
        positions = []
        center = self.grid_size / 2
        radius = self.grid_size / 2 - 0.5
        for i in range(self.num_electrodes):
            angle = 2 * np.pi * i / self.num_electrodes
            x = int(round(center + radius * np.cos(angle)))
            y = int(round(center + radius * np.sin(angle)))
            x = max(0, min(self.grid_size - 1, x))
            y = max(0, min(self.grid_size - 1, y))
            positions.append((x, y))
        return positions


def create_brain_mask(grid_size: int = 16) -> np.ndarray:
    mask = np.zeros((grid_size, grid_size), dtype=bool)
    center = grid_size / 2
    radius = grid_size / 2 - 0.5
    for i in range(grid_size):
        for j in range(grid_size):
            dist = np.sqrt((i - center + 0.5) ** 2 + (j - center + 0.5) ** 2)
            if dist <= radius:
                mask[i, j] = True
    return mask


def create_conductivity_map(
    grid_size: int = 16,
    edema_regions: Optional[List[dict]] = None,
    base_conductivity: float = 0.5,
    edema_conductivity_factor: float = 2.0
) -> np.ndarray:
    brain_mask = create_brain_mask(grid_size)
    sigma = np.zeros((grid_size, grid_size), dtype=np.float64)
    sigma[brain_mask] = base_conductivity

    if edema_regions:
        for region in edema_regions:
            cx = region.get('center_x', grid_size // 2)
            cy = region.get('center_y', grid_size // 2)
            radius = region.get('radius', 2)
            factor = region.get('conductivity_factor', edema_conductivity_factor)
            for i in range(grid_size):
                for j in range(grid_size):
                    dist = np.sqrt((i - cx) ** 2 + (j - cy) ** 2)
                    if dist <= radius and brain_mask[i, j]:
                        sigma[i, j] = base_conductivity * factor
    return sigma


class ForwardSolverFDM:
    def __init__(self, grid_size: int = 16, frequency: float = 1e6):
        self.grid_size = grid_size
        self.frequency = frequency
        self.omega = 2 * np.pi * frequency
        self.mu0 = 4 * np.pi * 1e-7
        self.brain_mask = create_brain_mask(grid_size)
        self.electrode_config = ElectrodeConfig(grid_size)
        self.dx = 0.01 / grid_size

    def solve(self, sigma: np.ndarray, current_pair: Tuple[int, int]) -> np.ndarray:
        N = self.grid_size
        A = np.zeros((N * N, N * N), dtype=np.complex128)
        b = np.zeros(N * N, dtype=np.complex128)
        I = 1.0

        src_idx, sink_idx = current_pair
        src_pos = self.electrode_config.electrode_positions[src_idx]
        sink_pos = self.electrode_config.electrode_positions[sink_idx]

        for i in range(N):
            for j in range(N):
                idx = i * N + j
                if not self.brain_mask[i, j]:
                    A[idx, idx] = 1.0
                    b[idx] = 0.0
                    continue

                sigma_center = sigma[i, j]
                if sigma_center < 1e-10:
                    sigma_center = 1e-10

                neighbors = [(i-1, j), (i+1, j), (i, j-1), (i, j+1)]
                diag = 0.0

                for ni, nj in neighbors:
                    if 0 <= ni < N and 0 <= nj < N and self.brain_mask[ni, nj]:
                        sigma_neighbor = sigma[ni, nj]
                        if sigma_neighbor < 1e-10:
                            sigma_neighbor = 1e-10
                        sigma_avg = (sigma_center + sigma_neighbor) / 2
                        coeff = sigma_avg / (self.dx ** 2)
                        n_idx = ni * N + nj
                        A[idx, n_idx] = -coeff
                        diag += coeff
                    else:
                        sigma_boundary = sigma_center * 0.5
                        coeff = sigma_boundary / (self.dx ** 2)
                        diag += coeff

                A[idx, idx] = diag + 1j * self.omega * self.mu0 * 1e-3

                if (i, j) == src_pos:
                    b[idx] = I / (self.dx ** 2)
                elif (i, j) == sink_pos:
                    b[idx] = -I / (self.dx ** 2)

        try:
            phi = np.linalg.solve(A, b)
        except np.linalg.LinAlgError:
            phi = np.linalg.lstsq(A, b, rcond=None)[0]

        return phi.reshape(N, N)

    def compute_measurements(self, sigma: np.ndarray) -> np.ndarray:
        num_elec = self.electrode_config.num_electrodes
        measurements = []

        for src in range(num_elec):
            for sink in range(src + 1, num_elec):
                phi = self.solve(sigma, (src, sink))
                for meas in range(num_elec):
                    if meas != src and meas != sink:
                        pos = self.electrode_config.electrode_positions[meas]
                        measurements.append(np.real(phi[pos[0], pos[1]]))

        return np.array(measurements)
