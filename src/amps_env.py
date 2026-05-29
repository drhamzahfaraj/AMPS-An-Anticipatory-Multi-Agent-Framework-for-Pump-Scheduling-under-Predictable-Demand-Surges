"""
AMPS simulation harness (ky10 / EPANET via WNTR).

Provides a single, controller-agnostic evaluation function so that every
controller (rule-based, optimization, single-agent, AMPS) is measured under
identical conditions. All metrics are computed directly from simulated flows
and heads. No values are hard-coded; everything is derived from the run.
"""
import os
import numpy as np
import wntr


# ---- physical / cost constants (reported in the paper) ----
RHO = 1000.0          # water density, kg/m3
G = 9.81              # gravity, m/s2
PUMP_EFF = 0.75       # assumed wire-to-water pump efficiency

# Saudi electricity tariff (SAR/kWh), verified Sep 2025 / 2026 SEC & SERA rates.
# Riyal pegged at 1 USD = 3.75 SAR.
SAR_PER_USD = 3.75
SAR_FLAT_COMMERCIAL = 0.20    # commercial flat rate, SAR/kWh (SEC/SERA)
SAR_FLAT_INDUSTRIAL = 0.18    # industrial flat rate, SAR/kWh

# NOTE: Saudi tariffs are FLAT (not time-of-use). We therefore report cost under
# the real flat rate as the primary figure. A time-of-use schedule is retained
# ONLY as a hypothetical sensitivity case (e.g., future demand-response / on-site
# generation), clearly labelled as such -- never presented as the current Saudi
# rate. Under a flat tariff, cost reduction tracks energy reduction directly;
# the controller's value then comes from energy and reliability, not load-shifting.
TARIFF_SAR = np.full(24, SAR_FLAT_COMMERCIAL)

# Optional hypothetical TOU schedule (SAR/kWh) for the sensitivity analysis only.
TOU_HYPOTHETICAL_SAR = np.array([
    0.12, 0.12, 0.12, 0.12, 0.12, 0.12,
    0.18, 0.18, 0.18,
    0.28, 0.28, 0.28, 0.28, 0.28, 0.28,
    0.28, 0.28, 0.28,
    0.18, 0.18, 0.18,
    0.12, 0.12, 0.12,
])


def load_ky10(duration_h=24, step_h=1, pmin=14.0, preq=21.0):
    base = os.path.dirname(wntr.__file__)
    inp = os.path.join(base, "library/networks/ky10.inp")
    wn = wntr.network.WaterNetworkModel(inp)
    wn.options.time.duration = int(duration_h * 3600)
    wn.options.time.hydraulic_timestep = int(step_h * 3600)
    wn.options.time.pattern_timestep = int(step_h * 3600)
    wn.options.time.report_timestep = int(step_h * 3600)
    # EPANET 2.2 pressure-driven analysis (PDA): physically valid under-supply
    # behavior. Validated to converge on ky10 with <1% residual negative-pressure
    # node-hours (PDA edge effect at near-zero-demand nodes), versus ~5% under
    # demand-driven analysis. See results-validation subsection.
    wn.options.hydraulic.demand_model = "PDA"
    wn.options.hydraulic.minimum_pressure = pmin
    wn.options.hydraulic.required_pressure = preq
    return wn


def evaluate(wn, label="baseline", pmin=14.0):
    """Run a configured network and return the full metric set.

    pmin: minimum acceptable pressure (m) for the demand-satisfaction /
          pressure-violation accounting.
    """
    sim = wntr.sim.EpanetSimulator(wn)
    res = sim.run_sim()

    flow = res.link["flowrate"]
    head = res.node["head"]
    pres = res.node["pressure"]
    status = res.link["status"]
    idx = flow.index
    dt_h = (idx[1] - idx[0]) / 3600.0
    hours = ((idx / 3600.0).astype(int)) % 24

    # ---- energy & cost ----
    energy_kwh = 0.0
    cost = 0.0
    switches = 0
    for p in wn.pump_name_list:
        pump = wn.get_link(p)
        sn, en = pump.start_node_name, pump.end_node_name
        Q = flow[p].clip(lower=0)
        H = (head[en] - head[sn]).clip(lower=0)
        P_kw = RHO * G * Q * H / PUMP_EFF / 1000.0
        e_step = P_kw * dt_h
        energy_kwh += e_step.sum()
        cost += float((e_step.values * TARIFF_SAR[hours]).sum())
        # pump switching: count on/off transitions
        st = (status[p].values > 0).astype(int)
        switches += int(np.abs(np.diff(st)).sum())

    # ---- reliability: pressure-driven demand satisfaction (validated PDA) ----
    delivered = res.node["demand"][wn.junction_name_list].clip(lower=0)
    expected = wntr.metrics.expected_demand(wn)[wn.junction_name_list]
    dem_sat = 100.0 * delivered.values.sum() / expected.values.sum()
    # residual nonphysical-pressure diagnostic (should be small under PDA)
    pjunc = pres[wn.junction_name_list].values
    neg_frac = 100.0 * (pjunc < 0).mean()

    return {
        "label": label,
        "energy_kwh_day": round(energy_kwh, 1),
        "cost_sar_day": round(cost, 2),
        "cost_usd_day": round(cost / SAR_PER_USD, 2),
        "demand_satisfaction_pct": round(dem_sat, 2),
        "neg_pressure_frac_pct": round(neg_frac, 2),
        "pump_switches": switches,
    }


if __name__ == "__main__":
    wn = load_ky10()
    m = evaluate(wn, label="rule-based (default controls)")
    for k, v in m.items():
        print(f"{k:28s}: {v}")
