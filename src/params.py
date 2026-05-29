"""
Verified real-world parameters for the AMPS study (single source of truth).

Every value here is from a cited public source. Used by the simulation, the
manuscript, and the repository so all three stay consistent. Idealizations and
their direction of effect are documented in the manuscript's
"Idealizations and real-world implications" subsection.
"""

PARAMS = {
    "electricity": {
        "tariff_commercial_sar_per_kwh": 0.20,   # SEC / SERA flat commercial rate
        "tariff_industrial_sar_per_kwh": 0.18,   # SEC / SERA flat industrial rate
        "sar_per_usd": 3.75,                      # SAMA currency peg
        "tariff_is_flat": True,                   # NOTE: flat, not time-of-use
        "source": "Saudi Electricity Company / SERA tariff schedule; SAMA peg",
    },
    "demand": {
        "per_capita_l_per_day": 235,              # connected-network average
        "water_tariff_usd_per_m3": 0.03,          # water+sanitation average
        "municipal_share_pct": 13,                # of national water use
        "annual_demand_growth_pct": 4.3,          # 1999-2004 average
        "source": "Water supply and sanitation in Saudi Arabia (GAStat / MOWE figures)",
    },
    "hajj_surge": {
        "avg_daily_pumping_m3": 750000,           # holy sites, average Hajj day
        "peak_daily_pumping_m3": 1000000,         # Arafat Day / Eid peak
        "surge_multiplier": 1.33,                 # peak / average
        "source": "Saudi Water Authority Hajj-readiness releases",
    },
    "hydraulic": {
        "pump_efficiency": 0.75,                  # IDEALIZED: constant (see limitations)
        "min_pressure_m": 14.0,                   # PDA minimum service pressure
        "required_pressure_m": 21.0,              # PDA required pressure
        "water_density_kg_m3": 1000.0,
        "gravity_m_s2": 9.81,
    },
    "datasets_public": {
        "kapsarc_consumption_by_region": "https://datasource.kapsarc.org/explore/dataset/the-amount-of-drinking-water-consumption-of-areas-from-all-sources-2014/",
        "kapsarc_per_capita": "https://datasource.kapsarc.org/explore/assets/per_capita_average_water_use_in_saudi_regions/",
        "swa_open_data": "https://www.swa.gov.sa/en/open-data-library",
        "mewa_open_data": "https://od.data.gov.sa",
        "benchmark_network": "ky10 (public EPANET benchmark, via WNTR)",
    },
}

if __name__ == "__main__":
    import json
    print(json.dumps(PARAMS, indent=2))
