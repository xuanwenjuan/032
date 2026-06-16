import numpy as np
from typing import Optional, List, Dict, Any, Tuple
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


def l_curve_parameter_selection(
    J: np.ndarray,
    delta_V: np.ndarray,
    lambda_candidates: Optional[np.ndarray] = None,
    num_candidates: int = 20
) -> Tuple[float, np.ndarray, np.ndarray, np.ndarray]:
    if lambda_candidates is None:
        sigma_max = np.linalg.svd(J, compute_uv=False)[0] if J.shape[0] > 0 and J.shape[1] > 0 else 1.0
        lambda_min = np.log10(sigma_max * 1e-6) if sigma_max > 0 else -6
        lambda_max = np.log10(sigma_max * 1e2) if sigma_max > 0 else 2
        lambda_candidates = np.logspace(lambda_min, lambda_max, num_candidates)

    residuals = []
    solution_norms = []
    solutions = []

    m, n = J.shape
    I = np.eye(n)

    for lam in lambda_candidates:
        A = J.T @ J + (lam ** 2) * I
        b = J.T @ delta_V
        try:
            x = np.linalg.solve(A, b)
        except np.linalg.LinAlgError:
            x = np.linalg.lstsq(A, b, rcond=None)[0]
        residual = np.linalg.norm(J @ x - delta_V)
        sol_norm = np.linalg.norm(x)
        residuals.append(residual)
        solution_norms.append(sol_norm)
        solutions.append(x)

    residuals = np.array(residuals)
    solution_norms = np.array(solution_norms)
    solutions = np.array(solutions)

    log_res = np.log10(residuals + 1e-12)
    log_sol = np.log10(solution_norms + 1e-12)

    if len(log_res) >= 3:
        curvature = np.zeros(len(log_res))
        for i in range(1, len(log_res) - 1):
            d_log_res_f = log_res[i + 1] - log_res[i]
            d_log_sol_f = log_sol[i + 1] - log_sol[i]
            d_log_res_b = log_res[i] - log_res[i - 1]
            d_log_sol_b = log_sol[i] - log_sol[i - 1]
            d2_log_res = d_log_res_f - d_log_res_b
            d2_log_sol = d_log_sol_f - d_log_sol_b
            numerator = d_log_res_f * d2_log_sol - d_log_sol_f * d2_log_res
            denominator = (d_log_res_f ** 2 + d_log_sol_f ** 2) ** 1.5 + 1e-12
            curvature[i] = numerator / denominator if denominator != 0 else 0
        curvature[0] = curvature[1] if len(curvature) > 1 else 0
        curvature[-1] = curvature[-2] if len(curvature) > 1 else 0
        best_idx = int(np.argmax(curvature))
    else:
        best_idx = len(lambda_candidates) // 2

    best_lambda = float(lambda_candidates[best_idx])
    return best_lambda, lambda_candidates, curvature, solutions[best_idx]


class TikhonovRegularizedReconstruction:
    def __init__(
        self,
        grid_size: int = 16,
        use_l_curve: bool = True,
        fixed_lambda: float = 0.1
    ):
        self.grid_size = grid_size
        self.brain_mask = create_brain_mask(grid_size)
        self.electrode_config = ElectrodeConfig(grid_size)
        self.num_electrodes = self.electrode_config.num_electrodes
        self.sensitivity_matrix = self._build_sensitivity_matrix()
        self.use_l_curve = use_l_curve
        self.fixed_lambda = fixed_lambda
        self.last_lambda = None
        self.lambda_candidates = None
        self.l_curve_curvature = None

    def _build_sensitivity_matrix(self) -> np.ndarray:
        N = self.grid_size
        num_elec = self.num_electrodes
        num_pixels = N * N
        brain_indices = np.where(self.brain_mask.flatten())[0]
        num_brain_pixels = len(brain_indices)

        if num_brain_pixels == 0:
            return np.zeros((num_elec * (num_elec - 1) * (num_elec - 2) // 2, num_pixels))

        rows_list = []
        electrode_positions = self.electrode_config.electrode_positions
        grid_ij = np.array([(i, j) for i in range(N) for j in range(N)])

        for src in range(num_elec):
            p_src = np.array(electrode_positions[src])
            for sink in range(src + 1, num_elec):
                p_sink = np.array(electrode_positions[sink])
                for meas in range(num_elec):
                    if meas == src or meas == sink:
                        continue
                    p_meas = np.array(electrode_positions[meas])
                    row_contrib = np.zeros(num_pixels)
                    for pidx in brain_indices:
                        i, j = grid_ij[pidx]
                        p_pix = np.array([i, j])
                        d_src = np.linalg.norm(p_pix - p_src) + 1.0
                        d_sink = np.linalg.norm(p_pix - p_sink) + 1.0
                        d_meas = np.linalg.norm(p_pix - p_meas) + 1.0
                        midpoint = (p_src + p_sink) / 2
                        d_mid = np.linalg.norm(p_pix - midpoint) + 1.0
                        weight = (1.0 / (d_src * d_sink)) * (1.0 / d_meas) * (1.0 / d_mid)
                        row_contrib[pidx] = weight
                    row_norm = np.linalg.norm(row_contrib)
                    if row_norm > 1e-12:
                        row_contrib = row_contrib / row_norm
                    rows_list.append(row_contrib)

        sensitivity_matrix = np.array(rows_list)

        return sensitivity_matrix

    def _tikhonov_solve(self, J: np.ndarray, delta_V: np.ndarray, lam: float) -> np.ndarray:
        m, n = J.shape
        I = np.eye(n)
        A = J.T @ J + (lam ** 2) * I
        b = J.T @ delta_V
        try:
            x = np.linalg.solve(A, b)
        except np.linalg.LinAlgError:
            x = np.linalg.lstsq(A, b, rcond=None)[0]
        return x

    def _adaptive_sigma_filter(self, recon_2d: np.ndarray) -> np.ndarray:
        N = self.grid_size
        filtered = recon_2d.copy()
        for i in range(N):
            for j in range(N):
                if not self.brain_mask[i, j]:
                    continue
                neighbors = []
                for di in [-1, 0, 1]:
                    for dj in [-1, 0, 1]:
                        if di == 0 and dj == 0:
                            continue
                        ni, nj = i + di, j + dj
                        if 0 <= ni < N and 0 <= nj < N and self.brain_mask[ni, nj]:
                            neighbors.append(recon_2d[ni, nj])
                if neighbors:
                    local_std = np.std(neighbors)
                    local_mean = np.mean(neighbors)
                    current = recon_2d[i, j]
                    threshold = local_std * 2.0
                    if abs(current - local_mean) > threshold:
                        filtered[i, j] = local_mean
        return filtered

    def reconstruct(
        self,
        measured_data: np.ndarray,
        reference_data: Optional[np.ndarray] = None
    ) -> np.ndarray:
        N = self.grid_size
        num_pixels = N * N

        if reference_data is None:
            reference_data = np.zeros_like(measured_data)

        delta_V = measured_data - reference_data
        max_v = np.max(np.abs(delta_V))
        if max_v > 1e-10:
            delta_V_norm = delta_V / max_v
        else:
            delta_V_norm = delta_V
            max_v = 1.0

        J = self.sensitivity_matrix

        if self.use_l_curve:
            try:
                best_lambda, lambdas, curvature, _ = l_curve_parameter_selection(
                    J, delta_V_norm, num_candidates=20
                )
                self.last_lambda = best_lambda
                self.lambda_candidates = lambdas.tolist()
                self.l_curve_curvature = curvature.tolist()
            except Exception:
                best_lambda = self.fixed_lambda
                self.last_lambda = best_lambda
        else:
            best_lambda = self.fixed_lambda
            self.last_lambda = best_lambda

        x = self._tikhonov_solve(J, delta_V_norm, best_lambda)

        recon_1d = x * max_v
        recon_2d = recon_1d.reshape(N, N)

        recon_2d[~self.brain_mask] = 0

        recon_2d = self._adaptive_sigma_filter(recon_2d)

        recon_2d[~self.brain_mask] = 0

        min_val = np.min(recon_2d[self.brain_mask]) if np.any(self.brain_mask) else 0
        max_val = np.max(recon_2d[self.brain_mask]) if np.any(self.brain_mask) else 1

        if max_val - min_val > 1e-10:
            recon_normalized = (recon_2d - min_val) / (max_val - min_val)
        else:
            recon_normalized = np.zeros_like(recon_2d)

        recon_normalized[~self.brain_mask] = 0

        return recon_normalized


LinearBackProjection = TikhonovRegularizedReconstruction


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

    reconstructor = TikhonovRegularizedReconstruction(grid_size, use_l_curve=True)
    reconstruction = reconstructor.reconstruct(measurements, reference_measurements)

    return {
        "true_conductivity": sigma.tolist(),
        "reconstructed_conductivity": reconstruction.tolist(),
        "regularization": {
            "lambda": reconstructor.last_lambda,
            "algorithm": "Tikhonov",
            "l_curve_enabled": reconstructor.use_l_curve,
            "lambda_candidates": reconstructor.lambda_candidates,
            "curvature": reconstructor.l_curve_curvature
        }
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
    regularization_info = {}
    cc = ColeColeModel()

    for freq_name, freq_val in FREQUENCIES.items():
        result = run_single_freq_simulation(grid_size, edema_regions, freq_val)
        freq_results[freq_name] = result["reconstructed_conductivity"]
        true_maps[freq_name] = result["true_conductivity"]
        regularization_info[freq_name] = result["regularization"]

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
        "regularization": regularization_info,
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

    reconstructor = TikhonovRegularizedReconstruction(grid_size, use_l_curve=True)
    reconstruction = reconstructor.reconstruct(measurements, reference_measurements)

    return {
        "true_conductivity": sigma.tolist(),
        "reconstructed_conductivity": reconstruction.tolist(),
        "measurements": measurements.tolist(),
        "reference_measurements": reference_measurements.tolist(),
        "grid_size": grid_size,
        "regularization": {
            "lambda": reconstructor.last_lambda,
            "algorithm": "Tikhonov",
            "l_curve_enabled": reconstructor.use_l_curve,
            "lambda_candidates": reconstructor.lambda_candidates,
            "curvature": reconstructor.l_curve_curvature
        }
    }
