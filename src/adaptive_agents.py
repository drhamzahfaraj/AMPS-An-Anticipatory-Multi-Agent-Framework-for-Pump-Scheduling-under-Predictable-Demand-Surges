"""
Adaptive agent decomposition for the AMPS framework.

The number of agents n is NOT fixed. It is derived from network structure by
clustering the controllable (tank-triggered) pumps according to hydraulic
coupling. The governing factors:

  1. Controllability: only tank-triggered pumps are agent-controllable.
  2. Hydraulic coupling: pumps whose tanks are topologically close (strongly
     coupled) are grouped into ONE agent to preserve coordination; pumps that
     are far apart (weakly coupled) become SEPARATE agents to gain parallelism.
  3. Scale: larger, more dispersed networks naturally yield more agents.

n therefore ranges from 1 (single tightly-coupled cluster) up to the number of
controllable pumps (all weakly coupled). This makes the decomposition a derived
property of the network rather than an assumption.
"""
import numpy as np
import networkx as nx
import wntr
from trigger_opt import _trigger_controls


def derive_agents(wn, coupling_threshold=20):
    """Cluster controllable pumps into agents by hydraulic (topological) distance
    between the tanks they control. Returns list of agent pump-groups and the
    distance matrix used (for reporting/justification).

    coupling_threshold: tanks within this many hops are 'strongly coupled' and
    share an agent. Chosen relative to network diameter (documented in paper).
    """
    pairs = _trigger_controls(wn)
    pumps = list(pairs.keys())
    if len(pumps) <= 1:
        return [pumps], np.zeros((len(pumps), len(pumps)))
    tanks = [pairs[p]["tank"] for p in pumps]
    G = wn.to_graph().to_undirected()
    n = len(pumps)
    D = np.zeros((n, n))
    for i in range(n):
        for j in range(i + 1, n):
            try:
                d = nx.shortest_path_length(G, tanks[i], tanks[j])
            except Exception:
                d = 9999
            D[i, j] = D[j, i] = d
    # agglomerative clustering by threshold: union pumps closer than threshold
    parent = list(range(n))
    def find(a):
        while parent[a] != a:
            parent[a] = parent[parent[a]]; a = parent[a]
        return a
    def union(a, b):
        parent[find(a)] = find(b)
    for i in range(n):
        for j in range(i + 1, n):
            if D[i, j] <= coupling_threshold:
                union(i, j)
    clusters = {}
    for i in range(n):
        clusters.setdefault(find(i), []).append(pumps[i])
    return list(clusters.values()), D


def describe_decomposition(wn, coupling_threshold=20):
    agents, D = derive_agents(wn, coupling_threshold)
    pairs = _trigger_controls(wn)
    diameter_proxy = float(D.max()) if D.size and D.max() > 0 else 0.0
    return {
        "n_controllable_pumps": len(pairs),
        "n_agents": len(agents),
        "agents": agents,
        "coupling_threshold": coupling_threshold,
        "max_pairwise_distance": diameter_proxy,
        "rationale": ("agents derived by clustering controllable pumps within "
                      f"{coupling_threshold} hops; n={len(agents)} emerges from "
                      "network coupling structure"),
    }


if __name__ == "__main__":
    from amps_env import load_ky10
    import json
    print(json.dumps(describe_decomposition(load_ky10()), indent=2, default=str))
