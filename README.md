# AMPS: An Anticipatory Multi-Agent Framework for Pump Scheduling under Predictable Demand Surges

Reproducible code, data, and results for the AMPS manuscript (submitted to the
Arabian Journal for Science and Engineering).

---

## Author metadata

| Author | Affiliation | Role | ORCID |
|--------|-------------|------|-------|
| **Hamzah Faraj** (corresponding) `f.hamzah@t.edu.sa` | Department of Science and Technology, Ranyah College, Taif University, Taif 21944, Saudi Arabia | Framework, learning methodology, software, writing (CS/AI) | 0009-0009-8832-0407 |
| **Abdullah H. Alshahri** `aalshahri@tu.edu.sa` | Department of Civil Engineering, Faculty of Engineering, Taif University, P.O. Box 11099, Taif 21974, Saudi Arabia | Hydraulic modelling, network selection, water-engineering interpretation | 0000-0002-5570-0296 |
| **Mohamed S. Soliman** `soliman@tu.edu.sa` | Department of Electrical Engineering, College of Engineering, Taif University, Taif 21944, Saudi Arabia | Sensing & communication layer specification | 0000-0002-9431-4195 |

---

## Abstract

Water distribution networks serving regions with predictable, calendar-driven
demand surges, most acutely the Saudi Hajj and Umrah pilgrimage, face a control
problem that conventional rule-based and reactive optimization methods handle
poorly: at peak demand the system becomes supply-constrained and loses delivered
water rather than merely consuming more energy. AMPS is an anticipatory
multi-agent framework that couples (1) a calendar-aware demand forecaster, (2) a
cooperative multi-agent controller whose number of agents is derived from network
coupling structure rather than fixed, and (3) a physics-based feasibility layer
that enforces hydraulic and service constraints within the simulation. The
controller learns a state-conditioned trigger-level policy, a high-quality
near-optimal solution obtained by structured policy search, that adapts to an
anticipatory surge signal. Across public benchmark networks of differing origin
and scale, the adaptive decomposition consistently matches or exceeds a
centralized optimizer (energy reductions up to 16.7% at held demand
satisfaction), and the learned controller improves on the rule-based baseline in
both energy and reliability under surge. All experiments are simulation-based on
public benchmarks with a validated hydraulic environment (mass conservation to
~1e-4%).

---

## Contribution

1. **Anticipatory control for calendar-predictable surges** — folding a surge
   signal into the controller state so it acts before the event, generalizing the
   Hajj case to a worldwide class of scheduled-surge problems.
2. **Adaptive multi-agent decomposition** — the number of agents is derived from
   hydraulic coupling, not fixed; it grows sublinearly with network size.
3. **Transferable trigger-level formulation** — feasible-by-construction policy
   search that generalizes across networks where binary-schedule GA does not.
4. **Honest, commensurable benchmarking** — single validated environment, held
   service level, no fabricated numbers, full reproducibility.

---

## Methodology: mechanism of energy savings

Energy/cost reduction does NOT come from time-of-use load shifting (Saudi tariffs
are flat). It comes from three mechanisms:

1. **Smarter storage use** — optimizing tank-level trigger thresholds so pumps run
   at higher aggregate efficiency and avoid unnecessary cycling.
2. **Coordination across pumps** — multi-agent decomposition lets coupled pumps
   avoid simultaneous inefficient operation.
3. **Anticipatory pre-positioning** — under a forecast surge, the state-conditioned
   policy fills storage ahead of the peak, holding service without a brute-force
   energy spike.

Pipeline: forecast (surge signal) -> per-agent trigger policy -> feasibility
projection -> realized schedule. Online cost is one inference per agent; expensive
search is offline.

---

## Repository structure

```
amps/
  README.md                 # this file
  LICENSE                   # MIT
  requirements.txt
  main.tex, references.bib  # manuscript source
  configs/experiment.json   # experiment configuration
  src/                      # all simulation code (12 modules)
  results/                  # all generated outputs (JSON/CSV)
  figures/                  # generated figures (PDF)
```

Key modules: `params.py` (verified parameters), `amps_env.py` (PDA harness),
`scenarios.py` (surge), `trigger_opt.py` (centralized + multi-agent),
`adaptive_agents.py` (derived agent count), `amps_controller.py` (learned policy),
`amps_io.py` (policy/schedule/metrics output), `banding.py` (offline acceleration),
`scaling_synthetic.py` (runtime scalability), `ga_baseline.py`/`ga_multinetwork.py`
(GA baselines), `run_trigger_net.py` (per-network runner).

---

## Dataset

- **Networks** (public benchmarks): ky10 (USA, 13 pumps), Net3 (USA, 2), Net6
  (USA, 61), C-Town (international BWN, 11), D-Town (BWN-II, 11), Richmond (UK, 7).
  ky10/Net3/Net6 ship with WNTR; C-Town/D-Town/Richmond via WaterBenchmarkHub.
- **Demand**: native diurnal pattern (normal) + x1.33 surge (pilgrimage
  average-to-peak ratio, Saudi Water Authority).
- **Real parameters** (`params.py`): tariff SAR 0.20/kWh (flat), 1 USD = 3.75 SAR,
  per-capita 235 L/day (ky10 ~ 34,800 resident-equivalents).
- **Public Saudi data referenced**: KAPSARC consumption datasets; SWA/MEWA portals.
- **Train/eval split**: hyperparameters/reward weights tuned on a validation split;
  test scenarios held out to prevent leakage.

---

## Key results and findings

| Finding | Evidence |
|---------|----------|
| Surge is a RELIABILITY problem, not energy | ky10: energy +3.8% but demand satisfaction 99.6%->94.3% under x1.33 surge |
| Simulation VALIDATED | mass conservation ~2.5e-4% mean relative error (all networks) |
| Multi-agent >= centralized everywhere | see ablation table |
| Agent count grows SUBLINEARLY | Net6: 60 controllable pumps -> 12 agents |
| Learned controller: anticipatory payoff | C-Town surge 5,009+/-28 kWh @99.2% vs baseline 5,289 kWh @99.19% (better on both) |
| Learned controller optimality gap | C-Town normal: 13.8% above the best optimizer (3,813 vs 3,352 kWh) -- the price of joint surge+normal robustness |
| ky10 baseline (reference for surge characterization) | normal 3,831 kWh / SAR 766 / USD 204 @ 99.6%; surge (x1.33) 3,975 kWh @ 94.34% |

### Ablation / benchmarking table

| Method | Network | Energy/cost saving | Source |
|--------|---------|--------------------|--------|
| Rule-based | all | 0% (reference) | this work |
| Centralized trigger-opt | ky10 | +0.8% | this work |
| Adaptive multi-agent | ky10 | +1.2% | this work |
| Centralized trigger-opt | C-Town | +14.0% | this work |
| Adaptive multi-agent | C-Town | +16.7% | this work |
| Adaptive multi-agent | D-Town | +8.7% | this work |
| Adaptive multi-agent | Net3 | +27.7% | this work |
| Learned AMPS (normal) | C-Town | -5.3% energy @99.5% | this work |
| Learned AMPS (surge) | C-Town | energy & service both improved | this work |
| E-PPO | benchmark (diff. setup) | up to ~11.1% | Hu et al. 2023 (Systems) |
| PPO real-time | benchmark (diff. setup) | competitive vs GA/robust-opt | Pei et al. 2025 (JWRPM) |
| MADDPG pump+valve | benchmark (diff. setup) | outperforms GA/PSO/DE | Hu et al. 2023 (Water Supply) |
| GA scheduling | benchmark (diff. setup) | up to ~25% | Luna et al. 2019 |

Cross-study percentages are NOT directly comparable (different networks,
baselines, service levels). AMPS's contribution is consistency, transferability,
and anticipation under a single validated environment.

---

## Running experiments

```bash
pip install -r requirements.txt
cd src
python amps_env.py                          # rule-based baseline + validation (ky10)
python run_trigger_net.py <net.inp> <Name>  # centralized vs adaptive multi-agent
python scaling_synthetic.py                 # synthetic runtime scalability
python banding.py                           # offline-search dimension reduction
python amps_io.py                           # controller output schema
```
Results write to `../results/`; figures to `../figures/`. International networks
download via `water-benchmark-hub`.

---

## Limitations

- **Simulation-only**: no physical deployment; sensing/communication is a
  specification, not a measured result.
- **Learned controller is demonstration-grade**: two seeds; converged 5-seed
  training with stage-wise ablation and curves is future work.
- **Public benchmarks, not a proprietary municipal model**: scenarios are
  representative, not literal.
- **Constant pump efficiency** and **uniform spatial surge** are declared
  idealizations.
- **Synthetic scalability** measures runtime only, no real-world savings claim.

---

## A note on EnergyPlus

EnergyPlus is a building energy / HVAC simulation tool; it does not model water
distribution hydraulics. This study uses EPANET 2.2 (via WNTR), the
domain-appropriate engine, so there are no EnergyPlus results to include.
EnergyPlus would be relevant only to a separate HVAC study; it appears in
unrelated prior work the authors consulted for rigor patterns, not for water
modelling.

---

## License
MIT — see `LICENSE`.

## Acknowledgments
The authors thank Taif University for institutional support. Hydraulic simulation
uses EPANET 2.2 via the open-source WNTR library; international benchmark networks
are provided through WaterBenchmarkHub. Saudi water-consumption context draws on
public KAPSARC and MEWA open datasets.

## Citation
Citation details will be added upon publication.
