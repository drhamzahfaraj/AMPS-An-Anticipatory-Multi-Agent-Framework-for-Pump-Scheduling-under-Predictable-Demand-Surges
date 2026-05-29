"""
SYNTHETIC computational-scalability test (labeled).

PURPOSE AND HONEST SCOPE: this test does NOT claim real-world energy savings on
large networks. It measures how the framework's COMPUTATIONAL cost scales:
specifically, whether the online decision cost stays bounded as the number of
pumps grows toward city scale (50, 100, 200), and how the derived agent count and
per-agent problem size behave. The networks are SYNTHETIC and are used only to
probe computational scaling, not to report deployment performance. Real-world
performance evidence comes only from the public benchmark networks
(scaling_real.json).

Design: each synthetic network is a set of independent pump->tank->demand
branches off a reservoir. This is a deliberately simple, transparent structure
whose only purpose is to exercise the solver and the decomposition at scale.
"""
import time
import json
import numpy as np
import wntr


def build_synth(n_pumps, seed=0):
    rng = np.random.default_rng(seed)
    wn = wntr.network.WaterNetworkModel()
    wn.add_reservoir("R", base_head=100.0)
    # one tank + one junction + one pump per branch (realistic: pumps>=tanks here 1:1
    # for transparency; ratio explored separately)
    for i in range(n_pumps):
        tname, jname, pname = f"T{i}", f"J{i}", f"P{i}"
        wn.add_tank(tname, elevation=50.0, init_level=5.0, min_level=1.0,
                    max_level=10.0, diameter=15.0)
        wn.add_junction(jname, base_demand=0.01, elevation=40.0)
        wn.add_pipe(f"pipe_t{i}", tname, jname, length=300, diameter=0.3)
        # pump from reservoir to tank
        wn.add_curve(f"c{i}", "HEAD", [(0.05, 60)])
        wn.add_pump(pname, "R", tname, pump_type="HEAD", pump_parameter=f"c{i}")
        # attach tank-level trigger controls so the pump is 'controllable'
        from wntr.network.controls import (Control, ControlAction,
                                           ValueCondition)
        tank = wn.get_node(tname); link = wn.get_link(pname)
        wn.add_control(f"{pname}_lo", Control(
            ValueCondition(tank, "level", "<", 3.0),
            [ControlAction(link, "status", 1)], name=f"{pname}_lo"))
        wn.add_control(f"{pname}_hi", Control(
            ValueCondition(tank, "level", ">", 8.0),
            [ControlAction(link, "status", 0)], name=f"{pname}_hi"))
    wn.options.time.duration = 24 * 3600
    wn.options.time.hydraulic_timestep = 3600
    wn.options.time.report_timestep = 3600
    wn.options.hydraulic.demand_model = "PDA"
    wn.options.hydraulic.minimum_pressure = 5.0
    wn.options.hydraulic.required_pressure = 15.0
    return wn


def time_scaling(sizes=(50, 100, 200), seed=0):
    results = []
    for n in sizes:
        wn = build_synth(n, seed)
        # time the hydraulic solve (the unit of online cost)
        t0 = time.time()
        try:
            wntr.sim.EpanetSimulator(wn).run_sim()
            solve_s = time.time() - t0
            ok = True
        except Exception as e:
            solve_s = float("nan"); ok = False
        # decomposition timing (topological clustering)
        from adaptive_agents import describe_decomposition
        t1 = time.time()
        try:
            d = describe_decomposition(wn, coupling_threshold=20)
            decomp_s = time.time() - t1
            n_agents = d["n_agents"]; n_ctrl = d["n_controllable_pumps"]
        except Exception:
            decomp_s = float("nan"); n_agents = -1; n_ctrl = -1
        # online decision cost model: one forward pass per agent. We report the
        # NUMBER of agents (decision units), since per-agent inference is O(1).
        results.append({"pumps": n, "controllable": n_ctrl, "n_agents": n_agents,
                        "solve_s": round(solve_s, 3) if ok else None,
                        "decomp_s": round(decomp_s, 3),
                        "note": "synthetic; computational scaling only"})
        print(f"pumps={n:4d} ctrl={n_ctrl:4d} agents={n_agents:3d} "
              f"solve={solve_s:.3f}s decomp={decomp_s:.3f}s")
    return results


if __name__ == "__main__":
    res = time_scaling()
    json.dump(res, open("scaling_synthetic.json", "w"), indent=2)
    print("saved scaling_synthetic.json")
