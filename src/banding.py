"""
Banding: an offline-search acceleration for large networks.

Idea: instead of optimizing one unit per agent, group controllable pumps into a
small number of BANDS (by tank capacity / operating level), and optimize one
shared threshold-offset per band. This reduces the number of optimization
variables from O(controllable pumps) to O(bands), accelerating the offline search
at large scale.

HONEST SCOPE: banding speeds up the OFFLINE optimization, not the deployed
controller (whose per-decision cost is already one inference per agent). It trades
resolution for speed: pumps in the same band share a control offset, so we expect
a quality cost in exchange for fewer evaluations. We measure BOTH sides.
"""
import time
import numpy as np
import wntr
from amps_env import evaluate
from trigger_opt import _trigger_controls, _apply_triggers, _baseline_params


def assign_bands(wn, pairs, n_bands):
    """Assign controllable pumps to n_bands by their tank's mid operating level."""
    pumps = list(pairs.keys())
    levels = []
    for p in pumps:
        t = wn.get_node(pairs[p]["tank"])
        levels.append((t.min_level + t.max_level) / 2.0)
    order = np.argsort(levels)
    bands = {}
    for rank, idx in enumerate(order):
        b = int(rank * n_bands / len(pumps))
        bands.setdefault(b, []).append(pumps[idx])
    return list(bands.values())


def optimize_banded(loader, n_bands, iters=8, pop=6, seed=0, sat_floor=99.0):
    """Optimize one shared (low,high) offset per band. Returns metrics + timing."""
    rng = np.random.default_rng(seed)
    wn0 = loader()
    pairs = _trigger_controls(wn0)
    base, _ = _baseline_params(loader)
    bands = assign_bands(wn0, pairs, n_bands)

    def evaluate_offsets(offsets):
        # offsets: per-band (d_low, d_high) applied to each pump's baseline triggers
        params = {}
        for bi, grp in enumerate(bands):
            dlo, dhi = offsets[2 * bi], offsets[2 * bi + 1]
            for p in grp:
                lo0, hi0 = base[p]
                params[p] = (lo0 + dlo, hi0 + dhi)
        wn = loader()
        clamped = {}
        for p, (lo, hi) in params.items():
            t = wn.get_node(pairs[p]["tank"])
            lo = float(np.clip(lo, t.min_level + 0.1, t.max_level - 0.2))
            hi = float(np.clip(hi, lo + 0.2, t.max_level - 0.05))
            clamped[p] = (lo, hi)
        _apply_triggers(wn, pairs, clamped)
        try:
            m = evaluate(wn, label="band")
        except Exception:
            return 1e9, 1e9, 0.0
        s = m["demand_satisfaction_pct"]
        if not (0.0 <= s <= 100.5):
            return 1e9, 1e9, 0.0
        return m["cost_sar_day"], m["energy_kwh_day"], s

    dim = 2 * len(bands)
    best_x = np.zeros(dim)
    bc, be, bs = evaluate_offsets(best_x)
    best_f = bc + 200000.0 * max(0.0, sat_floor - bs)
    sigma = 0.8
    n_evals = 1
    t0 = time.time()
    for it in range(iters):
        cands = best_x + sigma * rng.standard_normal((pop, dim))
        for c in cands:
            cc, ce, cs = evaluate_offsets(c)
            n_evals += 1
            f = cc + 200000.0 * max(0.0, sat_floor - cs)
            if f < best_f:
                best_f, best_x, bc, be, bs = f, c.copy(), cc, ce, cs
        sigma *= 0.9
    wall = time.time() - t0
    return {"n_bands": len(bands), "energy_kwh": round(be, 1),
            "demand_sat_pct": round(bs, 2), "evals": n_evals,
            "wall_s": round(wall, 1)}


if __name__ == "__main__":
    import os, json
    base = os.path.dirname(wntr.__file__)
    def loader():
        wn = wntr.network.WaterNetworkModel(os.path.join(base, "library/networks/Net6.inp"))
        wn.options.time.duration = 24 * 3600
        wn.options.time.hydraulic_timestep = 3600
        wn.options.time.report_timestep = 3600
        wn.options.hydraulic.demand_model = "PDA"
        wn.options.hydraulic.minimum_pressure = 14.0
        wn.options.hydraulic.required_pressure = 21.0
        return wn
    # baseline (no banding = full per-agent would be ~12 units on Net6) vs banding
    results = {}
    for nb in [3, 6, 12]:
        r = optimize_banded(loader, n_bands=nb, iters=5, pop=4, seed=0, sat_floor=95.0)
        results[f"bands_{nb}"] = r
        print(f"bands={r['n_bands']:2d}: energy={r['energy_kwh']} sat={r['demand_sat_pct']}% "
              f"evals={r['evals']} wall={r['wall_s']}s")
    json.dump(results, open("banding_results.json", "w"), indent=2)
    print("saved banding_results.json")
