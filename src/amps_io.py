"""
AMPS controller I/O: structured inputs and outputs.

Produces the three artifacts discussed in the paper:
  OUTPUT 1 (policy)   : per controllable pump -> agent, tank, low/high trigger,
                        per condition (normal/surge). The deployable solution.
  OUTPUT 2 (schedule) : per pump per hour -> status, tank level, flow, head.
                        The realized trajectory when the policy meets dynamics.
  SUMMARY (metrics)   : energy, cost (SAR/USD), demand satisfaction, switches.

We report a high-quality, near-optimal solution found by structured policy
search -- not a proven global optimum.
"""
import json
import csv
import numpy as np
import wntr
from amps_env import (load_ky10, evaluate, RHO, G, PUMP_EFF, TARIFF_SAR,
                      SAR_PER_USD)
from trigger_opt import _trigger_controls, _apply_triggers
from adaptive_agents import derive_agents
import scenarios as sc


def decode_policy(theta, pumps, pairs, agent_of, surge_signal):
    """theta -> per-pump (low, high) at the given surge signal, with agent IDs."""
    rows = []
    for i, p in enumerate(pumps):
        w_lo, b_lo, w_hi, b_hi = theta[4 * i:4 * i + 4]
        lo = b_lo + w_lo * surge_signal
        hi = b_hi + w_hi * surge_signal
        rows.append({"pump": p, "agent": agent_of[p], "tank": pairs[p]["tank"],
                     "low_threshold_m": round(float(lo), 3),
                     "high_threshold_m": round(float(hi), 3),
                     "condition": "surge" if surge_signal else "normal"})
    return rows


def run_and_export(loader, theta, surge_signal=0, surge_factor=1.0,
                   out_prefix="amps_solution"):
    wn = loader()
    if surge_factor != 1.0:
        sc.apply_surge(wn, surge_factor)
    pairs = _trigger_controls(wn)
    agents, _ = derive_agents(wn)
    agent_of = {p: ai for ai, grp in enumerate(agents) for p in grp}
    pumps = [p for grp in agents for p in grp]

    # ---- OUTPUT 1: policy ----
    policy = decode_policy(theta, pumps, pairs, agent_of, surge_signal)
    # apply policy thresholds and simulate
    params = {r["pump"]: (r["low_threshold_m"], r["high_threshold_m"]) for r in policy}
    clamped = {}
    for p, (lo, hi) in params.items():
        t = wn.get_node(pairs[p]["tank"])
        lo = float(np.clip(lo, t.min_level + 0.1, t.max_level - 0.2))
        hi = float(np.clip(hi, lo + 0.2, t.max_level - 0.05))
        clamped[p] = (lo, hi)
    _apply_triggers(wn, pairs, clamped)
    res = wntr.sim.EpanetSimulator(wn).run_sim()

    # ---- OUTPUT 2: realized schedule (per controllable pump per hour) ----
    flow = res.link["flowrate"]; head = res.node["head"]; status = res.link["status"]
    idx = flow.index
    schedule = []
    for p in pumps:
        pm = wn.get_link(p); sn, en = pm.start_node_name, pm.end_node_name
        tank = pairs[p]["tank"]
        for k, t in enumerate(idx):
            h = int(t / 3600) % 24
            lvl = float(head[tank].iloc[k] - wn.get_node(tank).elevation)
            Q = float(max(flow[p].iloc[k], 0.0))
            H = float(max(head[en].iloc[k] - head[sn].iloc[k], 0.0))
            schedule.append({"hour": h, "pump": p, "agent": agent_of[p],
                             "status": int(status[p].iloc[k] > 0),
                             "tank": tank, "tank_level_m": round(lvl, 2),
                             "flow_m3s": round(Q, 4), "head_m": round(H, 2)})

    # ---- SUMMARY: metrics ----
    m = evaluate(wn, label=out_prefix)
    summary = {k: (v.item() if hasattr(v, "item") else v) for k, v in m.items()}

    # export
    json.dump({"policy": policy, "summary": summary},
              open(f"{out_prefix}_policy.json", "w"), indent=2)
    with open(f"{out_prefix}_schedule.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(schedule[0].keys())); w.writeheader()
        w.writerows(schedule)
    return policy, schedule, summary


if __name__ == "__main__":
    # demo on ky10 with a static (baseline-initialized) policy
    from amps_controller import _baseline_theta
    wn = load_ky10(); pairs = _trigger_controls(wn)
    agents, _ = derive_agents(wn)
    pumps = [p for grp in agents for p in grp]
    theta = np.array(_baseline_theta(load_ky10, pumps, pairs))
    pol, sched, summ = run_and_export(load_ky10, theta, out_prefix="demo_ky10")
    print("POLICY (per pump):")
    for r in pol: print(" ", r)
    print("SUMMARY:", summ)
    print(f"schedule rows: {len(sched)} (pumps x 24h)")
