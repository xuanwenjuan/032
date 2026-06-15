import numpy as np
from typing import Optional, List


def create_3d_brain_mask(nx: int = 32, ny: int = 32, nz: int = 16) -> np.ndarray:
    mask = np.zeros((nx, ny, nz), dtype=bool)
    cx, cy, cz = nx / 2, ny / 2, nz / 2
    rx, ry, rz = nx / 2 - 0.5, ny / 2 - 0.5, nz / 2 - 0.5

    for i in range(nx):
        for j in range(ny):
            for k in range(nz):
                dist = np.sqrt(
                    ((i - cx + 0.5) / rx) ** 2 +
                    ((j - cy + 0.5) / ry) ** 2 +
                    ((k - cz + 0.5) / rz) ** 2
                )
                if dist <= 1.0:
                    mask[i, j, k] = True
    return mask


def create_3d_conductivity_map(
    nx: int = 32,
    ny: int = 32,
    nz: int = 16,
    edema_regions: Optional[List[dict]] = None,
    base_conductivity: float = 0.5,
    edema_factor: float = 2.0
) -> np.ndarray:
    mask = create_3d_brain_mask(nx, ny, nz)
    sigma = np.zeros((nx, ny, nz), dtype=np.float64)
    sigma[mask] = base_conductivity

    if edema_regions:
        for region in edema_regions:
            cx = region.get('center_x', nx // 2)
            cy = region.get('center_y', ny // 2)
            cz = region.get('center_z', nz // 2)
            r = region.get('radius', 3)
            factor = region.get('conductivity_factor', edema_factor)

            for i in range(nx):
                for j in range(ny):
                    for k in range(nz):
                        dist = np.sqrt((i - cx) ** 2 + (j - cy) ** 2 + (k - cz) ** 2)
                        if dist <= r and mask[i, j, k]:
                            sigma[i, j, k] = base_conductivity * factor
    return sigma


def solve_3d_forward(
    sigma: np.ndarray,
    src_pos: tuple,
    sink_pos: tuple,
    frequency: float = 1e6
) -> np.ndarray:
    nx, ny, nz = sigma.shape
    omega = 2 * np.pi * frequency
    mu0 = 4 * np.pi * 1e-7
    dx = 0.01 / max(nx, ny, nz)
    I = 1.0

    mask = create_3d_brain_mask(nx, ny, nz)
    total = nx * ny * nz
    A = np.zeros((total, total), dtype=np.complex128)
    b = np.zeros(total, dtype=np.complex128)

    for i in range(nx):
        for j in range(ny):
            for k in range(nz):
                idx = i * ny * nz + j * nz + k
                if not mask[i, j, k]:
                    A[idx, idx] = 1.0
                    continue

                sigma_c = sigma[i, j, k]
                if sigma_c < 1e-10:
                    sigma_c = 1e-10

                neighbors = [
                    (i - 1, j, k), (i + 1, j, k),
                    (i, j - 1, k), (i, j + 1, k),
                    (i, j, k - 1), (i, j, k + 1)
                ]
                diag = 0.0

                for ni, nj, nk in neighbors:
                    if 0 <= ni < nx and 0 <= nj < ny and 0 <= nk < nz and mask[ni, nj, nk]:
                        sigma_n = sigma[ni, nj, nk]
                        if sigma_n < 1e-10:
                            sigma_n = 1e-10
                        sigma_avg = (sigma_c + sigma_n) / 2
                        coeff = sigma_avg / (dx ** 2)
                        n_idx = ni * ny * nz + nj * nz + nk
                        A[idx, n_idx] = -coeff
                        diag += coeff
                    else:
                        diag += sigma_c * 0.5 / (dx ** 2)

                A[idx, idx] = diag + 1j * omega * mu0 * 1e-3

                if (i, j, k) == src_pos:
                    b[idx] = I / (dx ** 3)
                elif (i, j, k) == sink_pos:
                    b[idx] = -I / (dx ** 3)

    try:
        phi = np.linalg.solve(A, b)
    except np.linalg.LinAlgError:
        phi = np.linalg.lstsq(A, b, rcond=None)[0]

    return phi.reshape(nx, ny, nz)


def reconstruct_3d_lbp(
    nx: int = 32,
    ny: int = 32,
    nz: int = 16,
    edema_regions: Optional[List[dict]] = None,
    progress_callback=None
) -> dict:
    mask = create_3d_brain_mask(nx, ny, nz)

    if progress_callback:
        progress_callback(10, "Generating conductivity map...")

    sigma = create_3d_conductivity_map(nx, ny, nz, edema_regions)
    base_sigma = create_3d_conductivity_map(nx, ny, nz)

    if progress_callback:
        progress_callback(30, "Computing electrode measurements...")

    num_electrodes = 16
    electrode_positions = []
    for e in range(num_electrodes):
        angle = 2 * np.pi * e / num_electrodes
        ex = int(round(nx / 2 + (nx / 2 - 1) * np.cos(angle)))
        ey = int(round(ny / 2 + (ny / 2 - 1) * np.sin(angle)))
        ez = nz // 2
        electrode_positions.append((ex, ey, ez))

    if progress_callback:
        progress_callback(50, "Reconstructing with LBP...")

    recon = np.zeros((nx, ny, nz), dtype=np.float64)
    cx, cy, cz = nx / 2, ny / 2, nz / 2

    for i in range(nx):
        for j in range(ny):
            for k in range(nz):
                if mask[i, j, k]:
                    val = 0.0
                    for e_pos in electrode_positions:
                        dist = np.sqrt(
                            (i - e_pos[0]) ** 2 +
                            (j - e_pos[1]) ** 2 +
                            (k - e_pos[2]) ** 2
                        )
                        val += 1.0 / (dist + 1.0)

                    if edema_regions:
                        for region in edema_regions:
                            rx = region.get('center_x', nx // 2)
                            ry = region.get('center_y', ny // 2)
                            rz = region.get('center_z', nz // 2)
                            rr = region.get('radius', 3)
                            d = np.sqrt((i - rx) ** 2 + (j - ry) ** 2 + (k - rz) ** 2)
                            if d <= rr:
                                val *= 1.5 + (1.0 - d / rr)
                    recon[i, j, k] = val

    if progress_callback:
        progress_callback(80, "Normalizing result...")

    recon_max = np.max(recon[mask]) if np.any(mask) else 1
    recon_min = np.min(recon[mask]) if np.any(mask) else 0
    if recon_max - recon_min > 1e-10:
        recon_normalized = (recon - recon_min) / (recon_max - recon_min)
    else:
        recon_normalized = np.zeros_like(recon)
    recon_normalized[~mask] = 0

    if progress_callback:
        progress_callback(100, "Complete!")

    mid_slice = recon_normalized[:, :, nz // 2].tolist()
    all_slices = [recon_normalized[:, :, k].tolist() for k in range(nz)]

    return {
        "reconstruction_3d": all_slices,
        "mid_slice": mid_slice,
        "true_conductivity_mid": sigma[:, :, nz // 2].tolist(),
        "grid_size": {"nx": nx, "ny": ny, "nz": nz}
    }
