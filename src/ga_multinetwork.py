"""
Network-agnostic warm-started GA for cross-network generalization.

Generalizes the ky10 GA to any public benchmark network: extracts that
network's own feasible baseline schedule as the warm-start seed, then optimizes
energy cost under the validated PDA evaluation while holding demand satisfaction
at the network's baseline service level. This is the SAME method applied
unchanged across networks -- which is the generalization evidence.
"""
import os
import numpy as np
import wntr
from amps_env import RHO, G, PUMP_EFF, TARIFF_SAR, SAR_PER_USD

N_HOURS = 24


def _load(path):
    wn = wntr.network.WaterNetworkModel(path)
    wn.options.time.duration = 24 * 3600
    wn.options.time.hydraulic_timestep = 3600
    wn.options.time.report_timestep = 3600
    wn.options.hydraulic.demand_model = "PDA"
    wn.options.hydraulic.minimum_pressure = 14.0
    wn.options.hydraulic.required_pressure = 21.0
    return wn


def _evaluate(path, schedule, pumps):
    wn = _load(path)
    from wntr.network.controls import Control, ControlAction, SimTimeCondition
    for cn in list(wn.control_name_list):
        wn.remove_control(cn)
    for pi, p in enumerate(pumps):
        link = wn.get_link(p)
        for h in range(N_HOURS):
            wn.add_control(f"g_{pi}_{h}", Control(
                SimTimeCondition(wn, "=", h * 3600),
                [ControlAction(link, "status", int(schedule[pi, h]))],
                name=f"g_{pi}_{h}"))
    try:
        res = wntr.sim.EpanetSimulator(wn).run_sim()
    except Exception:
        return 1e9, 1e9, 0.0
    flow = res.link["flowrate"]; head = res.node["head"]
    idx = flow.index; dt_h = (idx[1] - idx[0]) / 3600.0
    hours = ((idx / 3600.0).astype(int)) % 24
    E = 0.0; C = 0.0
    for p in pumps:
        pm = wn.get_link(p); sn, en = pm.start_node_name, pm.end_node_name
        Q = flow[p].clip(lower=0); H = (head[en] - head[sn]).clip(lower=0)
        e = (RHO * G * Q * H / PUMP_EFF / 1000.0) * dt_h
        E += e.sum(); C += float((e.values * TARIFF_SAR[hours]).sum())
    deliv = res.node["demand"][wn.junction_name_list].clip(lower=0).values.sum()
    exp = wntr.metrics.expected_demand(wn)[wn.junction_name_list].values.sum()
    sat = 100.0 * deliv / exp if exp > 0 else 0.0
    if not (0.0 <= sat <= 100.5):
        return 1e9, 1e9, 0.0
    return float(C), float(E), float(sat)


def _baseline_schedule(path, pumps):
    wn = _load(path)
    res = wntr.sim.EpanetSimulator(wn).run_sim()
    status = res.link["status"]
    sched = np.ones((len(pumps), N_HOURS), dtype=int)
    for pi, p in enumerate(pumps):
        st = (status[p].values > 0).astype(int)
        sched[pi, :min(N_HOURS, len(st))] = st[:N_HOURS]
    return sched


def run_ga_network(path, name, pop=12, gens=6, seed=0, sat_margin=0.3):
    rng = np.random.default_rng(seed)
    wn0 = _load(path)
    pumps = wn0.pump_name_list
    n = len(pumps)
    # baseline service level -> feasibility floor
    _, base_E, base_sat = _evaluate(path, _baseline_schedule(path, pumps), pumps)
    floor = base_sat - sat_margin
    base_ch = _baseline_schedule(path, pumps).reshape(-1)

    def fit(ch):
        c, e, s = _evaluate(path, ch.reshape(n, N_HOURS), pumps)
        return -(c + 200000.0 * max(0.0, floor - s)), c, e, s

    P = np.tile(base_ch, (pop, 1))
    for k in range(1, pop):
        flip = rng.random(n * N_HOURS) < 0.05 * (1 + k / pop)
        P[k] = np.where(flip, 1 - P[k], P[k])
    F = [fit(ch) for ch in P]
    bi = max(range(pop), key=lambda i: F[i][0]); best_ch, best = P[bi].copy(), F[bi]
    for g in range(gens):
        newP = []
        for _ in range(pop):
            i, j = rng.integers(pop), rng.integers(pop)
            newP.append(P[i if F[i][0] > F[j][0] else j].copy())
        newP = np.array(newP)
        for k in range(0, pop - 1, 2):
            if rng.random() < 0.8:
                pt = rng.integers(1, n * N_HOURS)
                newP[k, pt:], newP[k+1, pt:] = newP[k+1, pt:].copy(), newP[k, pt:].copy()
        mask = rng.random((pop, n * N_HOURS)) < 0.02
        newP = np.where(mask, 1 - newP, newP)
        newP[0] = best_ch
        P = newP; F = [fit(ch) for ch in P]
        ci = max(range(pop), key=lambda i: F[i][0])
        if F[ci][0] > best[0]:
            best_ch, best = P[ci].copy(), F[ci]
    _, c, e, s = best
    saving = 100.0 * (base_E - e) / base_E
    return {"network": name, "pumps": n,
            "baseline_energy_kwh": round(base_E, 1), "baseline_sat_pct": round(base_sat, 2),
            "ga_energy_kwh": round(e, 1), "ga_cost_sar": round(c, 2),
            "ga_cost_usd": round(c / SAR_PER_USD, 2), "ga_sat_pct": round(s, 2),
            "energy_saving_pct": round(saving, 2), "seed": seed}
