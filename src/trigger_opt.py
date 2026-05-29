"""
Trigger-level pump-scheduling optimizer (centralized and multi-agent variants).

Rationale (paper): rather than optimizing 312 binary on/off variables, we
optimize the tank-level trigger thresholds that govern each tank-controlled
pump (low=turn-on, high=turn-off). This (a) shrinks the search space ~50x,
(b) keeps every candidate feasible by construction (the network always obeys
its own control logic), and (c) transfers across networks since the
parameterization scales with the number of controlled pumps, not pump x horizon.

Two variants:
  - centralized: one optimizer tunes ALL trigger pairs jointly (CMA-ES-style).
  - multi_agent: pumps are divided across agents; each agent tunes only its own
    trigger pair, co-evaluated on the shared network (cooperative coevolution).
This directly tests whether dividing the task across agents helps or whether
hydraulic coupling causes coordination loss.
"""
import numpy as np
import wntr
from amps_env import load_ky10, evaluate


def _trigger_controls(wn):
    """Return list of (pump, tank, low_attr_control, high_attr_control) by parsing
    existing tank-trigger controls. Each controlled pump has a low (open) and
    high (close) threshold."""
    pairs = {}  # pump -> {'tank':..., 'low':ctrl_name, 'high':ctrl_name}
    for cn in wn.control_name_list:
        c = wn.get_control(cn)
        s = str(c)
        # parse "IF TANK <t> LEVEL BELOW/ABOVE <v> THEN PUMP <p> STATUS IS OPEN/CLOSED"
        if "PUMP" not in s or "TANK" not in s:
            continue
        toks = s.split()
        tank = toks[2]
        pump = toks[toks.index("PUMP") + 1]
        kind = "low" if "BELOW" in s else "high"
        pairs.setdefault(pump, {"tank": tank})[kind] = cn
    # keep only pumps that have both a low and high trigger
    return {p: d for p, d in pairs.items() if "low" in d and "high" in d}


def _apply_triggers(wn, pairs, params):
    """params: dict pump -> (low_level, high_level). Rewrite the threshold values
    on the existing controls."""
    from wntr.network.controls import (Control, ControlAction,
                                        ValueCondition)
    for pump, (low, high) in params.items():
        d = pairs[pump]
        tank = wn.get_node(d["tank"])
        link = wn.get_link(pump)
        # remove old controls, add new with tuned thresholds
        wn.remove_control(d["low"]); wn.remove_control(d["high"])
        c_low = Control(ValueCondition(tank, "level", "<", low),
                        [ControlAction(link, "status", 1)], name=d["low"])
        c_high = Control(ValueCondition(tank, "level", ">", high),
                         [ControlAction(link, "status", 0)], name=d["high"])
        wn.add_control(d["low"], c_low); wn.add_control(d["high"], c_high)
    return wn


def _evaluate_triggers(loader, params, surge, scenario_fn=None):
    wn = loader()
    if scenario_fn is not None:
        scenario_fn(wn)
    pairs = _trigger_controls(wn)
    # clamp params to each tank's physical range
    clamped = {}
    for p, (lo, hi) in params.items():
        t = wn.get_node(pairs[p]["tank"])
        lo = float(np.clip(lo, t.min_level + 0.1, t.max_level - 0.2))
        hi = float(np.clip(hi, lo + 0.2, t.max_level - 0.05))  # high must exceed low
        clamped[p] = (lo, hi)
    _apply_triggers(wn, pairs, clamped)
    try:
        m = evaluate(wn, label="trig")
    except Exception:
        return 1e9, 1e9, 0.0
    sat = m["demand_satisfaction_pct"]
    if not (0.0 <= sat <= 100.5):
        return 1e9, 1e9, 0.0
    return m["cost_sar_day"], m["energy_kwh_day"], sat


def _baseline_params(loader):
    wn = loader()
    pairs = _trigger_controls(wn)
    params = {}
    for p, d in pairs.items():
        c_low = str(wn.get_control(d["low"])); c_high = str(wn.get_control(d["high"]))
        lo = float(c_low.split("BELOW")[1].split("THEN")[0])
        hi = float(c_high.split("ABOVE")[1].split("THEN")[0])
        params[p] = (lo, hi)
    return params, pairs


def optimize(loader, mode="centralized", surge=1.0, scenario_fn=None,
             iters=20, pop=10, seed=0, sat_floor=99.0):
    """mode in {'centralized','multi_agent'}. Returns best params + metrics."""
    rng = np.random.default_rng(seed)
    base_params, pairs = _baseline_params(loader)
    pumps = list(base_params.keys())

    def cost_of(params):
        c, e, s = _evaluate_triggers(loader, params, surge, scenario_fn)
        return c + 200000.0 * max(0.0, sat_floor - s), c, e, s

    # represent params as vector [lo_p0, hi_p0, lo_p1, hi_p1, ...]
    def to_vec(prm): return np.array([v for p in pumps for v in prm[p]])
    def to_prm(vec): return {p: (vec[2*i], vec[2*i+1]) for i, p in enumerate(pumps)}

    x0 = to_vec(base_params)
    best_x = x0.copy(); best = cost_of(base_params); best_f = best[0]
    sigma = 0.8  # search std in metres

    if mode == "centralized":
        # simple (mu, lambda) evolution strategy over the full vector
        for it in range(iters):
            pops = best_x + sigma * rng.standard_normal((pop, len(x0)))
            evals = [cost_of(to_prm(v)) for v in pops]
            fi = int(np.argmin([e[0] for e in evals]))
            if evals[fi][0] < best_f:
                best_x, best, best_f = pops[fi].copy(), evals[fi], evals[fi][0]
            sigma *= 0.93  # anneal
    elif mode == "multi_agent":
        # cooperative coevolution: each agent owns one pump's (lo,hi); optimize
        # agents in round-robin, holding the others fixed (co-evaluated on shared net)
        for it in range(iters):
            for ai, p in enumerate(pumps):
                cur = to_prm(best_x)
                trials = []
                for _ in range(pop):
                    cand = dict(cur)
                    lo, hi = cur[p]
                    cand[p] = (lo + sigma * rng.standard_normal(),
                               hi + sigma * rng.standard_normal())
                    trials.append(cand)
                evals = [cost_of(t) for t in trials]
                fi = int(np.argmin([e[0] for e in evals]))
                if evals[fi][0] < best_f:
                    best_x, best, best_f = to_vec(trials[fi]).copy(), evals[fi], evals[fi][0]
            sigma *= 0.93
    _, c, e, s = best
    return {"mode": mode, "n_agents": len(pumps) if mode == "multi_agent" else 1,
            "cost_sar": round(c, 2), "energy_kwh": round(e, 1),
            "demand_sat_pct": round(s, 2), "seed": seed}
