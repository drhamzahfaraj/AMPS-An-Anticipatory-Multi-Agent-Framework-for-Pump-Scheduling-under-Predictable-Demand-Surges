"""
Learned AMPS controller.

This realizes the framework's central claim: instead of a STATIC trigger setting
(the optimizer baseline), each agent learns a POLICY that maps its observed state
-- including the anticipatory signal (whether a surge is forecast) -- to its
pump's trigger thresholds. The controller is therefore state-conditioned and
anticipatory: it can apply different thresholds in normal vs. surge conditions,
which a static optimizer cannot.

Policy (per agent p): theta_p = [w_lo, b_lo, w_hi, b_hi]
   low_p  = clip( b_lo + w_lo * surge_signal , tank_range )
   high_p = clip( b_hi + w_hi * surge_signal , tank_range )
where surge_signal in {0,1} (or a continuous forecast level) is provided by the
anticipation stage. With w=0 the policy reduces to a static trigger (the
baseline), so the learned controller strictly generalizes the optimizer.

Training: cooperative, shared-reward evolution strategy (a simple, stable policy
search appropriate to the small per-agent parameter vectors and the expensive
black-box EPANET evaluation). Agents are derived adaptively (adaptive_agents).
Reported numbers are whatever training produces; no curve is fabricated.
"""
import numpy as np
import wntr
from amps_env import load_ky10, evaluate, SAR_PER_USD
from trigger_opt import _trigger_controls, _apply_triggers
from adaptive_agents import derive_agents
import scenarios as sc


def _eval_policy(loader, theta, pumps, pairs, surge_signal, surge_factor):
    """Apply the state-conditioned trigger policy and evaluate via PDA harness."""
    wn = loader()
    if surge_factor != 1.0:
        sc.apply_surge(wn, surge_factor)
    # decode policy -> per-pump (low, high) given the surge signal
    params = {}
    for i, p in enumerate(pumps):
        w_lo, b_lo, w_hi, b_hi = theta[4 * i:4 * i + 4]
        lo = b_lo + w_lo * surge_signal
        hi = b_hi + w_hi * surge_signal
        params[p] = (lo, hi)
    # clamp to physical tank ranges
    clamped = {}
    for p, (lo, hi) in params.items():
        t = wn.get_node(pairs[p]["tank"])
        lo = float(np.clip(lo, t.min_level + 0.1, t.max_level - 0.2))
        hi = float(np.clip(hi, lo + 0.2, t.max_level - 0.05))
        clamped[p] = (lo, hi)
    _apply_triggers(wn, pairs, clamped)
    try:
        m = evaluate(wn, label="amps")
    except Exception:
        return 1e9, 1e9, 0.0
    sat = m["demand_satisfaction_pct"]
    if not (0.0 <= sat <= 100.5):
        return 1e9, 1e9, 0.0
    return m["cost_sar_day"], m["energy_kwh_day"], sat


def _baseline_theta(loader, pumps, pairs):
    """Initialize policy at the baseline static triggers, w=0 (so it starts as
    the feasible baseline and learns to improve / specialize)."""
    wn = loader()
    theta = np.zeros(4 * len(pumps))
    for i, p in enumerate(pumps):
        c_low = str(wn.get_control(pairs[p]["low"]))
        c_high = str(wn.get_control(pairs[p]["high"]))
        lo = float(c_low.split("BELOW")[1].split("THEN")[0])
        hi = float(c_high.split("ABOVE")[1].split("THEN")[0])
        theta[4 * i:4 * i + 4] = [0.0, lo, 0.0, hi]  # w=0 -> static at baseline
    return theta


def train_amps(loader, iters=12, pop=8, seed=0, sat_floor=99.0,
               surge_factor=1.33, sigma=0.6):
    """Train across BOTH normal (signal=0) and surge (signal=1) so the policy
    learns state-conditioned behavior. Shared-reward evolution strategy."""
    rng = np.random.default_rng(seed)
    wn0 = loader()
    pairs = _trigger_controls(wn0)
    agents, _ = derive_agents(wn0)
    pumps = [p for grp in agents for p in grp]
    if not pumps:
        return None
    theta = _baseline_theta(loader, pumps, pairs)

    def joint_cost(th):
        # evaluate on both conditions; objective = mean penalized cost
        total = 0.0
        recs = {}
        for sig, fac, floor in [(0.0, 1.0, sat_floor), (1.0, surge_factor, sat_floor - 5.0)]:
            c, e, s = _eval_policy(loader, th, pumps, pairs, sig, fac)
            total += c + 200000.0 * max(0.0, floor - s)
            recs[("normal" if sig == 0 else "surge")] = (c, e, s)
        return total, recs

    best_th = theta.copy()
    best_f, best_recs = joint_cost(theta)
    history = [best_f]
    s = sigma
    for it in range(iters):
        cands = best_th + s * rng.standard_normal((pop, len(theta)))
        evals = [joint_cost(c) for c in cands]
        fi = int(np.argmin([e[0] for e in evals]))
        if evals[fi][0] < best_f:
            best_th, best_f, best_recs = cands[fi].copy(), evals[fi][0], evals[fi][1]
        history.append(best_f)
        s *= 0.9  # anneal
    return {"theta": best_th.tolist(), "n_agents": len(agents),
            "records": {k: {"cost_sar": round(v[0], 2),
                            "energy_kwh": round(v[1], 1),
                            "demand_sat_pct": round(v[2], 2)}
                        for k, v in best_recs.items()},
            "train_history": [round(float(h), 1) for h in history], "seed": seed}
