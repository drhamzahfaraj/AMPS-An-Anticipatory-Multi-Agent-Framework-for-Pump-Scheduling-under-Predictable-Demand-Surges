"""Run centralized + adaptive multi-agent trigger optimization on one network."""
import sys, time, json, os, wntr
from trigger_opt import optimize, _baseline_params, _evaluate_triggers
from adaptive_agents import describe_decomposition

def clean(o):
    if isinstance(o, dict): return {k: clean(v) for k,v in o.items()}
    if isinstance(o, list): return [clean(v) for v in o]
    if hasattr(o, 'item'): return o.item()
    return o

def make_loader(path):
    def loader():
        wn=wntr.network.WaterNetworkModel(path)
        wn.options.time.duration=24*3600; wn.options.time.hydraulic_timestep=3600; wn.options.time.report_timestep=3600
        wn.options.hydraulic.demand_model='PDA'; wn.options.hydraulic.minimum_pressure=14.0; wn.options.hydraulic.required_pressure=21.0
        return wn
    return loader

def run(path, name, iters=6, pop=5):
    ld=make_loader(path)
    bp,_=_baseline_params(ld)
    c0,e0,s0=_evaluate_triggers(ld, bp, surge=1.0)
    floor=max(0.0, s0-0.3)
    decomp=describe_decomposition(ld(), coupling_threshold=20)
    res={'baseline_energy':round(e0,1),'baseline_sat':round(s0,2),
         'n_controllable':decomp['n_controllable_pumps'],'n_agents':decomp['n_agents']}
    for mode in ['centralized','multi_agent']:
        t0=time.time()
        r=optimize(ld, mode=mode, surge=1.0, iters=iters, pop=pop, seed=0, sat_floor=floor)
        r['saving_pct']=round((e0-r['energy_kwh'])/e0*100,2)
        r['wall_s']=round(time.time()-t0,1)
        res[mode]=clean(r)
    fn='trigger_multinetwork.json'
    out=json.load(open(fn)) if os.path.exists(fn) else {}
    out[name]=clean(res); json.dump(out, open(fn,'w'), indent=2)
    print(f"{name}: baseline {e0:.0f}kWh@{s0:.1f}% | n_agents={res['n_agents']} | "
          f"centralized {res['centralized']['saving_pct']:+.1f}% | multi_agent {res['multi_agent']['saving_pct']:+.1f}%")
    return res

if __name__=='__main__':
    run(sys.argv[1], sys.argv[2])
