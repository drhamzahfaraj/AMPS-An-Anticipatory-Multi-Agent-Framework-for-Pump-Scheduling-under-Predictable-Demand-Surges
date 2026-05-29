# Two-Stage Critical Review — AMPS Manuscript

Applying the `academic-paper-reviewer` protocol (EIC + 3 peer reviewers +
Devil's Advocate) and the `academic-paper` integrity framework. Target venue:
Arabian Journal for Science and Engineering (AJSE, Springer). Field: water
engineering × AI/control. Paradigm: simulation-based computational study.

---

## STAGE 1 — SELF-ASSESSMENT

**Strengths.**
- Honest, internally-consistent framing: claims match evidence ("near-optimal via
  structured policy search," not "optimal"); simulation-only scope is explicit.
- Validated environment (mass conservation ~1e-4%); all metrics relative to an
  identically-configured baseline.
- Genuine cross-network generalization (US + international benchmarks, 2–61 pumps).
- Adaptive agent derivation is a real methodological novelty.
- Learned controller realized; surge dual-improvement is the central claim shown.
- Reproducibility repository with real code and outputs.

**Weaknesses (self-identified, addressed where possible).**
1. Learned controller is demonstration-grade (2 seeds). → Flagged explicitly;
   5-seed convergence scoped as future work.
2. Reference DOIs needed verification. → DONE: caught and fixed 3 errors
   (E-PPO authorship, Hajgató spelling, key rename).
3. Some redundancy between Discussion synthesis and Results. → Trimmed.
4. Forecaster is a surge signal, not a trained weather model. → Stated honestly.
5. No EnergyPlus results (that is an HVAC tool, not applicable here). → Documented.

---

## STAGE 2 — FIVE-REVIEWER PANEL

### Reviewer 0 — Editor-in-Chief (journal fit, originality, significance)
*Fit*: strong for AJSE (engineering + regional relevance via Hajj). *Originality*:
the anticipatory + adaptive-decomposition combination is novel; the single-network
savings are modest but the generalization and honesty are the contribution.
*Decision lean*: Major revision → acceptable after convergence work.
**Actionable**: ensure the abstract states the contribution as generalization +
anticipation, not peak savings (DONE). Make limitations prominent (DONE).

### Reviewer 1 — Methodology (rigor, reproducibility, statistics)
*Concerns*: (a) single/two-seed training weakens statistical claims; (b) the
optimality-gap and validation-epsilon must be clearly distinguished; (c)
demand-driven vs PDA correction must be explained. *All three are addressed in
the Results-validation and learned-controller subsections.* **Actionable**:
report mean±std wherever multiple seeds exist (DONE for GA and learned); state
the 5-seed plan (DONE).

### Reviewer 2 — Domain (water engineering, literature, framework)
*Concerns*: realistic tariff/efficiency assumptions; PDA is the correct demand
model under stress (good); confirm benchmark networks are standard (they are:
ky10, Net3/Net6, C-Town, D-Town, Richmond). **Actionable**: cite branch-and-bound
and energy-efficiency reviews for completeness (DONE: Menke2016, Coelho2014,
MalaJetmarova2018).

### Reviewer 3 — Perspective (cross-disciplinary, practical impact)
*Strength*: the sensing/communication layer ties the control contribution to a
deployable architecture and justifies the three-author team. *Concern*: ensure it
is framed as specification, not measured result (DONE). **Actionable**: connect
the recurring-event premise to other domains (DONE in Discussion).

### Reviewer 4 — Devil's Advocate (core-argument challenges)
*Challenge 1*: "A GA could beat you on one network." → Rebutted in the positioning
subsection (consistency, transferability, anticipation, fairness). *Challenge 2*:
"The learned controller barely beats the static optimizer on normal demand." →
Acknowledged honestly as a robustness trade-off; the surge dual-improvement is the
real claim. *Challenge 3*: "Synthetic scalability proves nothing about savings." →
Pre-empted: the synthetic test is explicitly runtime-only. No unaddressed fatal
objection.

---

## EDITORIAL DECISION

**Major revision, converging to acceptance** once: (1) converged multi-seed
training with stage-wise ablation and training curves is added; (2) the Springer
two-column template is applied; (3) author/affiliation finalized (DONE). The
manuscript is honest, internally consistent, and reproducible; no integrity or
fatal-logic issues remain after the reference-integrity fixes.

**Fixes applied directly in this pass**: reference DOI/authorship corrections
(×3), citation-key rename, duplicated-word typo, Sutton entry type, added
optimization references, README expansion, repository completeness.

**Remaining (scoped, require compute/template not available in this pass)**:
5-seed converged training + curves; Springer sn-jnl two-column formatting.
