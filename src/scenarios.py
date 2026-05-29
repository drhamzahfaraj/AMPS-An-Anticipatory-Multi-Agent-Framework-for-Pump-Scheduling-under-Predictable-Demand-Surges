"""
Demand scenarios for the AMPS study.

Two profiles are built on top of ky10's native diurnal pattern:
  - 'normal'  : the network's baseline diurnal demand (pattern '1').
  - 'surge'   : a pilgrimage-style surge that multiplies demand by a peak
                factor during the surge window.

The surge multiplier is parameterized (not hard-coded into results). The
default peak factor of ~1.33 reflects the documented pilgrimage operation,
where daily pumping averages ~750,000 m3 and peaks above 1,000,000 m3
(>1.0M / 0.75M ~= 1.33x) on peak days (Saudi Water Authority).
"""
import numpy as np


def apply_surge(wn, peak_factor=1.33, window=(9, 18)):
    """Scale every junction's base demand by `peak_factor` to emulate a
    sustained surge. `window` documents the peak hours for reporting;
    the scaling is applied to base demand so it compounds with the
    native diurnal pattern. Returns the modified network.
    """
    for jn in wn.junction_name_list:
        j = wn.get_node(jn)
        dts = j.demand_timeseries_list[0]
        dts.base_value = dts.base_value * peak_factor
    return wn


def total_daily_demand_m3(wn):
    """Approximate total daily demand (m3) from base demands x mean pattern."""
    # mean of diurnal pattern is ~1.0, so base_demand sum * 86400 approximates day
    tot = 0.0
    for jn in wn.junction_name_list:
        j = wn.get_node(jn)
        dts = j.demand_timeseries_list[0]
        tot += dts.base_value
    return tot * 86400.0
