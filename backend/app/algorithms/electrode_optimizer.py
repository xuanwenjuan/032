import numpy as np
import random
from typing import List, Tuple, Dict, Any, Optional
from app.algorithms.forward_solver import ElectrodeConfig, create_brain_mask, create_conductivity_map
from app.algorithms.image_quality import compute_all_metrics, quality_score


class ElectrodeOptimizerGA:
    def __init__(
        self,
        grid_size: int = 16,
        num_total_electrodes: int = 16,
        num_pairs_to_select: int = 8,
        population_size: int = 30,
        generations: int = 15,
        mutation_rate: float = 0.2,
        crossover_rate: float = 0.7,
        seed: int = 42
    ):
        self.grid_size = grid_size
        self.num_total_electrodes = num_total_electrodes
        self.num_pairs_to_select = num_pairs_to_select
        self.population_size = population_size
        self.generations = generations
        self.mutation_rate = mutation_rate
        self.crossover_rate = crossover_rate
        self.electrode_config = ElectrodeConfig(grid_size, num_total_electrodes)
        self.brain_mask = create_brain_mask(grid_size)
        self.all_pairs = self._generate_all_pairs()
        random.seed(seed)
        np.random.seed(seed)

    def _generate_all_pairs(self) -> List[Tuple[int, int]]:
        pairs = []
        for src in range(self.num_total_electrodes):
            for sink in range(src + 1, self.num_total_electrodes):
                pairs.append((src, sink))
        return pairs

    def _pair_coverage_score(self, pair_indices: List[int]) -> float:
        selected_pairs = [self.all_pairs[i] for i in pair_indices]
        coverage_map = np.zeros((self.grid_size, self.grid_size), dtype=np.float64)
        electrode_positions = self.electrode_config.electrode_positions
        for (src, sink) in selected_pairs:
            p_src = electrode_positions[src]
            p_sink = electrode_positions[sink]
            for i in range(self.grid_size):
                for j in range(self.grid_size):
                    if self.brain_mask[i, j]:
                        d_src = np.sqrt((i - p_src[0]) ** 2 + (j - p_src[1]) ** 2)
                        d_sink = np.sqrt((i - p_sink[0]) ** 2 + (j - p_sink[1]) ** 2)
                        line_dist = self._point_to_line_distance(
                            i, j, p_src[0], p_src[1], p_sink[0], p_sink[1]
                        )
                        local_coverage = (1.0 / (d_src + 1.5) + 1.0 / (d_sink + 1.5))
                        local_coverage *= 1.0 / (1.0 + line_dist)
                        coverage_map[i, j] += local_coverage
        brain_pixels = coverage_map[self.brain_mask]
        if len(brain_pixels) == 0:
            return 0.0
        mean_coverage = float(np.mean(brain_pixels))
        std_coverage = float(np.std(brain_pixels))
        uniformity = 1.0 / (1.0 + std_coverage / (mean_coverage + 1e-6))
        min_coverage = float(np.min(brain_pixels))
        return 0.4 * mean_coverage + 0.4 * uniformity + 0.2 * min_coverage

    def _point_to_line_distance(self, px, py, x1, y1, x2, y2) -> float:
        dx, dy = x2 - x1, y2 - y1
        if dx == 0 and dy == 0:
            return np.sqrt((px - x1) ** 2 + (py - y1) ** 2)
        t = max(0.0, min(1.0, ((px - x1) * dx + (py - y1) * dy) / (dx * dx + dy * dy + 1e-9)))
        proj_x = x1 + t * dx
        proj_y = y1 + t * dy
        return float(np.sqrt((px - proj_x) ** 2 + (py - proj_y) ** 2))

    def _angular_spread_score(self, pair_indices: List[int]) -> float:
        selected_pairs = [self.all_pairs[i] for i in pair_indices]
        angles = []
        electrode_positions = self.electrode_config.electrode_positions
        for (src, sink) in selected_pairs:
            p_src = electrode_positions[src]
            p_sink = electrode_positions[sink]
            center = self.grid_size / 2
            mid_x = (p_src[0] + p_sink[0]) / 2 - center
            mid_y = (p_src[1] + p_sink[1]) / 2 - center
            angle = np.arctan2(mid_y, mid_x)
            angles.append(angle)
        if len(angles) < 2:
            return 0.5
        angles = sorted(angles)
        diffs = []
        for i in range(len(angles)):
            next_a = angles[(i + 1) % len(angles)]
            d = abs(next_a - angles[i])
            if d > np.pi:
                d = 2 * np.pi - d
            diffs.append(d)
        ideal = 2 * np.pi / len(angles)
        diff_arr = np.array(diffs)
        spread = 1.0 - float(np.std(diff_arr) / (ideal + 1e-6))
        return max(0.0, min(1.0, spread))

    def _electrode_balance_score(self, pair_indices: List[int]) -> float:
        usage = np.zeros(self.num_total_electrodes, dtype=np.float64)
        for idx in pair_indices:
            src, sink = self.all_pairs[idx]
            usage[src] += 1
            usage[sink] += 1
        if usage.sum() == 0:
            return 0.0
        mean_u = np.mean(usage)
        std_u = np.std(usage)
        balance = 1.0 / (1.0 + std_u / (mean_u + 1e-6))
        zero_electrodes = int(np.sum(usage == 0))
        diversity_penalty = zero_electrodes / self.num_total_electrodes
        return float(max(0.0, balance - 0.5 * diversity_penalty))

    def fitness(self, individual: List[int]) -> float:
        coverage = self._pair_coverage_score(individual)
        spread = self._angular_spread_score(individual)
        balance = self._electrode_balance_score(individual)
        return 0.5 * coverage + 0.3 * spread + 0.2 * balance

    def _random_individual(self) -> List[int]:
        return sorted(random.sample(range(len(self.all_pairs)), self.num_pairs_to_select))

    def _init_population(self) -> List[List[int]]:
        pop = [self._random_individual() for _ in range(self.population_size)]
        default_pairs = list(range(min(self.num_pairs_to_select, len(self.all_pairs))))
        if default_pairs not in pop:
            pop[0] = default_pairs
        return pop

    def _tournament_select(self, pop: List[List[int]], fits: List[float], k: int = 3) -> List[int]:
        candidates = random.sample(list(zip(pop, fits)), k)
        candidates.sort(key=lambda x: x[1], reverse=True)
        return list(candidates[0][0])

    def _crossover(self, p1: List[int], p2: List[int]) -> Tuple[List[int], List[int]]:
        if random.random() > self.crossover_rate:
            return list(p1), list(p2)
        set1, set2 = set(p1), set(p2)
        common = list(set1 & set2)
        only1 = list(set1 - set2)
        only2 = list(set2 - set1)
        random.shuffle(only1)
        random.shuffle(only2)
        n_swap = min(len(only1), len(only2))
        if n_swap > 0:
            swap_count = random.randint(1, n_swap)
            new1 = common + only1[swap_count:] + only2[:swap_count]
            new2 = common + only2[swap_count:] + only1[:swap_count]
        else:
            new1, new2 = list(p1), list(p2)
        new1 = sorted(set(new1))
        new2 = sorted(set(new2))
        while len(new1) > self.num_pairs_to_select:
            new1.pop(random.randrange(len(new1)))
        while len(new1) < self.num_pairs_to_select:
            avail = [i for i in range(len(self.all_pairs)) if i not in new1]
            if avail:
                new1.append(random.choice(avail))
                new1.sort()
            else:
                break
        while len(new2) > self.num_pairs_to_select:
            new2.pop(random.randrange(len(new2)))
        while len(new2) < self.num_pairs_to_select:
            avail = [i for i in range(len(self.all_pairs)) if i not in new2]
            if avail:
                new2.append(random.choice(avail))
                new2.sort()
            else:
                break
        return sorted(new1), sorted(new2)

    def _mutate(self, individual: List[int]) -> List[int]:
        if random.random() > self.mutation_rate:
            return list(individual)
        mutant = list(individual)
        n_mut = random.randint(1, max(1, self.num_pairs_to_select // 3))
        for _ in range(n_mut):
            idx = random.randrange(len(mutant))
            avail = [i for i in range(len(self.all_pairs)) if i not in mutant]
            if avail:
                mutant[idx] = random.choice(avail)
        return sorted(set(mutant))

    def optimize(self) -> Dict[str, Any]:
        population = self._init_population()
        best_history = []
        avg_history = []
        best_individual = None
        best_fitness = -1.0
        for gen in range(self.generations):
            fitnesses = [self.fitness(ind) for ind in population]
            gen_best_f = max(fitnesses)
            gen_best_i = fitnesses.index(gen_best_f)
            gen_avg_f = float(np.mean(fitnesses))
            if gen_best_f > best_fitness:
                best_fitness = gen_best_f
                best_individual = list(population[gen_best_i])
            best_history.append(gen_best_f)
            avg_history.append(gen_avg_f)
            new_pop = []
            new_pop.append(list(best_individual))
            while len(new_pop) < self.population_size:
                p1 = self._tournament_select(population, fitnesses)
                p2 = self._tournament_select(population, fitnesses)
                c1, c2 = self._crossover(p1, p2)
                c1 = self._mutate(c1)
                c2 = self._mutate(c2)
                new_pop.append(c1)
                if len(new_pop) < self.population_size:
                    new_pop.append(c2)
            population = new_pop[:self.population_size]
        selected_pairs = [self.all_pairs[i] for i in best_individual]
        selected_electrodes = sorted(set([e for pair in selected_pairs for e in pair]))
        return {
            "selected_pair_indices": best_individual,
            "selected_pairs": selected_pairs,
            "selected_electrodes": selected_electrodes,
            "electrode_positions": self.electrode_config.electrode_positions,
            "num_selected_pairs": len(selected_pairs),
            "num_unique_electrodes": len(selected_electrodes),
            "fitness_score": float(best_fitness),
            "coverage_score": self._pair_coverage_score(best_individual),
            "spread_score": self._angular_spread_score(best_individual),
            "balance_score": self._electrode_balance_score(best_individual),
            "generation_best_history": best_history,
            "generation_avg_history": avg_history,
            "grid_size": self.grid_size
        }


def evaluate_layout_quality(
    true_conductivity: np.ndarray,
    reconstructed_conductivity: np.ndarray,
    mask: Optional[np.ndarray] = None
) -> Dict[str, Any]:
    if mask is None:
        N = true_conductivity.shape[0]
        mask = create_brain_mask(N)
    metrics = compute_all_metrics(true_conductivity, reconstructed_conductivity, mask)
    return {
        "metrics": metrics,
        "overall_quality_score": quality_score(metrics)
    }


def recommend_electrode_layout(
    grid_size: int = 16,
    num_pairs_to_select: int = 8,
    previous_metrics: Optional[Dict[str, float]] = None
) -> Dict[str, Any]:
    optimizer = ElectrodeOptimizerGA(
        grid_size=grid_size,
        num_pairs_to_select=num_pairs_to_select
    )
    result = optimizer.optimize()
    if previous_metrics:
        result["previous_metrics"] = previous_metrics
        prev_score = quality_score(previous_metrics)
        result["improvement_potential"] = max(0.0, result["fitness_score"] - prev_score)
    return result
