"""
Genetic-algorithm (GA) optimization baseline for pump scheduling on ky10.

Rationale (documented in the paper): pump scheduling is a black-box,
combinatorial, nonconvex problem -- each candidate schedule requires a full
EPANET hydraulic solve, so gradient/convex methods do not apply. GA is the
standard metaheuristic baseline in the pump-scheduling literature (e.g., the
comparison method in Tang et al. 2025), chosen here for direct commensurability
with prior work. The GA is the BASELINE, not the proposed AMPS method.

Encoding: binary chromosome of length (n_pumps x n_hours); gene = pump on/off
in that hour. Fitness = -(energy cost) - penalty x (unmet-demand fraction),
so the GA is pushed toward low cost WITHOUT sacrificing demand satisfaction.
All evaluation uses the same validated PDA harness as every other controller.
"""
import os
import numpy as np
import wntr
from amps_env import (load_ky10, RHO, G, PUMP_EFF, TARIFF_SAR, SAR_PER_USD)
import scenarios as sc

N_HOURS = 24


def _apply_schedule(wn, schedule, pumps):
    """Apply a binary schedule (n_pumps x 24) as time-based pump controls."""
    from wntr.network.controls import Control, ControlAction, SimTimeCondition
    # clear existing controls so the GA schedule fully governs the pumps
    for cn in list(wn.control_name_list):
        wn.remove_control(cn)
    for pi, p in enumerate(pumps):
        link = wn.get_link(p)
        for h in range(N_HOURS):
            act = ControlAction(link, "status", int(schedule[pi, h]))
            cond = SimTimeCondition(wn, "=", h * 3600)
            wn.add_control(f"ga_{pi}_{h}", Control(cond, [act], name=f"ga_{pi}_{h}"))
    return wn


def _evaluate_schedule(schedule, pumps, surge):
    """Return (cost_sar, energy_kwh, demand_satisfaction_pct) using the SAME
    validated harness evaluation as every other controller, so all numbers come
    from one trusted code path."""
    from amps_env import evaluate
    wn = load_ky10()
    if surge != 1.0:
        sc.apply_surge(wn, surge)
    _apply_schedule(wn, schedule, pumps)
    try:
        m = evaluate(wn, label="ga")
    except Exception:
        return 1e9, 1e9, 0.0  # infeasible solve -> heavily penalized
    sat = m["demand_satisfaction_pct"]
    # guard: a physically impossible satisfaction indicates a non-converged solve;
    # treat as infeasible rather than reporting it.
    if not (0.0 <= sat <= 100.5):
        return 1e9, 1e9, 0.0
    return m["cost_sar_day"], m["energy_kwh_day"], sat


def run_ga(surge=1.0, pop=24, gens=15, seed=0, sat_floor=99.0, penalty=5000.0,
           warm_start=True):
    rng = np.random.default_rng(seed)
    wn0 = load_ky10()
    pumps = wn0.pump_name_list
    n = len(pumps)

    def fitness(ch):
        sched = ch.reshape(n, N_HOURS)
        cost, energy, sat = _evaluate_schedule(sched, pumps, surge)
        unmet = max(0.0, sat_floor - sat)        # shortfall below the floor
        return -(cost + penalty * unmet), cost, energy, sat

    # initialize population
    if warm_start and os.path.exists("warmstart_schedule.npy"):
        # seed from the feasible rule-based schedule, with mutated copies for diversity
        base = np.load("warmstart_schedule.npy").reshape(-1)
        P = np.tile(base, (pop, 1))
        # keep first individual exact; perturb the rest
        for k in range(1, pop):
            flip = rng.random(n * N_HOURS) < 0.05 * (1 + k / pop)
            P[k] = np.where(flip, 1 - P[k], P[k])
    else:
        P = (rng.random((pop, n * N_HOURS)) < 0.7).astype(int)

    fit = [fitness(ch) for ch in P]
    best = max(range(pop), key=lambda i: fit[i][0])
    best_ch, best_rec = P[best].copy(), fit[best]

    for g in range(gens):
        # tournament selection
        newP = []
        for _ in range(pop):
            i, j = rng.integers(pop), rng.integers(pop)
            winner = i if fit[i][0] > fit[j][0] else j
            newP.append(P[winner].copy())
        newP = np.array(newP)
        # single-point crossover
        for k in range(0, pop - 1, 2):
            if rng.random() < 0.8:
                pt = rng.integers(1, n * N_HOURS)
                newP[k, pt:], newP[k + 1, pt:] = (
                    newP[k + 1, pt:].copy(), newP[k, pt:].copy())
        # bit-flip mutation
        mask = rng.random((pop, n * N_HOURS)) < 0.02
        newP = np.where(mask, 1 - newP, newP)
        # elitism: keep best
        newP[0] = best_ch
        P = newP
        fit = [fitness(ch) for ch in P]
        cur = max(range(pop), key=lambda i: fit[i][0])
        if fit[cur][0] > best_rec[0]:
            best_ch, best_rec = P[cur].copy(), fit[cur]
    _, cost, energy, sat = best_rec
    return {"cost_sar": round(cost, 2), "cost_usd": round(cost / SAR_PER_USD, 2),
            "energy_kwh": round(energy, 1), "demand_satisfaction_pct": round(sat, 2)}


if __name__ == "__main__":
    import json, time
    out = {}
    for surge, name in [(1.0, "normal"), (1.33, "surge")]:
        runs = []
        t0 = time.time()
        for s in range(3):  # 3 seeds for a quick first pass; expand to 5 later
            r = run_ga(surge=surge, pop=20, gens=10, seed=s)
            runs.append(r); print(f"  [{name} seed {s}] {r}")
        # aggregate mean +/- std
        keys = ["cost_sar", "energy_kwh", "demand_satisfaction_pct"]
        agg = {k: (round(float(np.mean([r[k] for r in runs])), 2),
                   round(float(np.std([r[k] for r in runs])), 2)) for k in keys}
        out[name] = {"runs": runs, "mean_std": agg, "wall_s": round(time.time() - t0, 1)}
        print(f"{name}: mean+/-std {agg}  ({out[name]['wall_s']}s)\n")
    json.dump(out, open("ga_results.json", "w"), indent=2)
    print("Saved ga_results.json")
