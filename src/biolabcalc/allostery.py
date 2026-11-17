"""
Module: biolabcalc.allostery
Component: Deterministic Allosteric Pathway Tracer & GNM Cross-Correlation Engine
Architectural Role: Pure-Python residue interaction graph (RIG) builder,
Gaussian Network Model (GNM) Kirchhoff Laplacian solver via Jacobi eigenvalue
decomposition, Yen's K-shortest communication paths, and Perturbation Response
Scanning (PRS) effector/sensor profiling.
"""

from __future__ import annotations

import heapq
import math
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple, Union


# ============================================================================
# Frozen Domain Dataclasses
# ============================================================================

@dataclass(frozen=True)
class ResidueNode:
    resid: int
    resname: str
    chain: str
    x: float
    y: float
    z: float
    prs_effectiveness: float = 0.0
    prs_sensitivity: float = 0.0


@dataclass(frozen=True)
class AllostericPath:
    source_resid: int
    sink_resid: int
    path_residues: Tuple[int, ...]
    total_cost: float
    bottleneck_residue: int

    def __post_init__(self):
        if isinstance(self.path_residues, (list, set, tuple)):
            object.__setattr__(self, "path_residues", tuple(self.path_residues))


@dataclass(frozen=True)
class AllostericNetworkResult:
    source_resid: int
    sink_resid: int
    paths: Tuple[AllostericPath, ...]
    hotspot_residues: Tuple[int, ...]
    prs_effectors: Tuple[int, ...]
    prs_sensors: Tuple[int, ...]
    nodes: Tuple[ResidueNode, ...] = ()

    def __post_init__(self):
        for f in ("paths", "hotspot_residues", "prs_effectors", "prs_sensors", "nodes"):
            val = getattr(self, f, ())
            if isinstance(val, (list, set, tuple)):
                object.__setattr__(self, f, tuple(val))


# ============================================================================
# Pure-Python PDB Parser
# ============================================================================

def parse_pdb_ca_coordinates(pdb_text_or_path: Union[str, Path]) -> Tuple[ResidueNode, ...]:
    """
    Parse C-alpha (CA) atom coordinates from PDB text content or a file path.
    """
    content: str
    if isinstance(pdb_text_or_path, Path):
        try:
            if pdb_text_or_path.is_file():
                content = pdb_text_or_path.read_text(encoding="utf-8", errors="replace")
            else:
                content = str(pdb_text_or_path)
        except OSError:
            content = str(pdb_text_or_path)
    else:
        raw_s = str(pdb_text_or_path)
        if "\n" not in raw_s and "\r" not in raw_s and len(raw_s) < 260:
            try:
                p = Path(raw_s)
                if p.is_file():
                    content = p.read_text(encoding="utf-8", errors="replace")
                else:
                    content = raw_s
            except OSError:
                content = raw_s
        else:
            content = raw_s

    nodes: List[ResidueNode] = []
    seen_res: Set[Tuple[str, int]] = set()

    for line in content.splitlines():
        if line.startswith("ENDMDL"):
            break
        if line.startswith("ATOM  "):
            alt_loc = line[16:17] if len(line) > 16 else " "
            if alt_loc not in (" ", "A", "1"):
                continue
            atom_name = line[12:16].strip()
            if atom_name == "CA":
                resname = line[17:20].strip()
                chain = line[21:22].strip() or "A"
                try:
                    resid = int(line[22:26].strip())
                    x = float(line[30:38].strip())
                    y = float(line[38:46].strip())
                    z = float(line[46:54].strip())
                except (ValueError, IndexError):
                    continue

                if (chain, resid) not in seen_res:
                    seen_res.add((chain, resid))
                    nodes.append(ResidueNode(
                        resid=resid,
                        resname=resname,
                        chain=chain,
                        x=x,
                        y=y,
                        z=z,
                    ))

    return tuple(nodes)


# ============================================================================
# Jacobi Eigenvalue Decomposition (Pure Python)
# ============================================================================

def _jacobi_eigenvalue_decomposition(
    A: List[List[float]],
    max_iter: int = 100,
    tol: float = 1e-9,
) -> Tuple[List[float], List[List[float]]]:
    """
    Computes all eigenvalues and eigenvectors of a real symmetric matrix A
    using pure-Python Jacobi rotations.
    
    Returns:
        eigenvalues: List of floats
        eigenvectors: List of column vectors (V[i][k] is component i of eigenvector k)
    """
    n = len(A)
    # Copy A
    D = [row[:] for row in A]
    # Initialize V as identity matrix
    V = [[1.0 if i == j else 0.0 for j in range(n)] for i in range(n)]

    for _ in range(max_iter):
        # Find maximum off-diagonal element
        max_val = 0.0
        p, q = 0, 1
        for i in range(n - 1):
            for j in range(i + 1, n):
                val = abs(D[i][j])
                if val > max_val:
                    max_val = val
                    p, q = i, j

        if max_val < tol:
            break

        # Compute rotation angle
        diff = D[q][q] - D[p][p]
        if abs(D[p][q]) < 1e-15:
            continue
        theta = 0.5 * math.atan2(2.0 * D[p][q], diff)
        c = math.cos(theta)
        s = math.sin(theta)

        # Update D
        d_pp = D[p][p]
        d_qq = D[q][q]
        d_pq = D[p][q]

        D[p][p] = c * c * d_pp - 2.0 * s * c * d_pq + s * s * d_qq
        D[q][q] = s * s * d_pp + 2.0 * s * c * d_pq + c * c * d_qq
        D[p][q] = 0.0
        D[q][p] = 0.0

        for k in range(n):
            if k != p and k != q:
                d_kp = D[k][p]
                d_kq = D[k][q]
                D[k][p] = c * d_kp - s * d_kq
                D[p][k] = D[k][p]
                D[k][q] = s * d_kp + c * d_kq
                D[q][k] = D[k][q]

        # Update eigenvectors V
        for k in range(n):
            v_kp = V[k][p]
            v_kq = V[k][q]
            V[k][p] = c * v_kp - s * v_kq
            V[k][q] = s * v_kp + c * v_kq

    eigenvalues = [D[i][i] for i in range(n)]
    return eigenvalues, V


def _compute_gnm_pseudo_inverse(
    K: List[List[float]],
) -> List[List[float]]:
    """
    Computes the Moore-Penrose pseudo-inverse of the Kirchhoff Laplacian matrix K.
    K is positive semi-definite with at least one zero eigenvalue (rigid body translation).
    """
    n = len(K)
    eigenvalues, V = _jacobi_eigenvalue_decomposition(K)

    # K_pinv = sum_{lambda_k > 1e-8} (1 / lambda_k) * v_k * v_k^T
    K_pinv = [[0.0] * n for _ in range(n)]

    for k in range(n):
        lam = eigenvalues[k]
        if lam > 1e-8:
            inv_lam = 1.0 / lam
            for i in range(n):
                vi = V[i][k]
                for j in range(n):
                    K_pinv[i][j] += inv_lam * vi * V[j][k]

    return K_pinv


# ============================================================================
# Shortest Path & Yen's K-Shortest Loopless Paths Algorithm
# ============================================================================

def _dijkstra_shortest_path(
    nodes: Sequence[int],
    adj: Dict[int, Dict[int, float]],
    source: int,
    sink: int,
    excluded_nodes: Set[int],
    excluded_edges: Set[Tuple[int, int]],
) -> Optional[Tuple[List[int], float]]:
    """Finds the shortest path between source and sink avoiding excluded nodes and edges."""
    if source in excluded_nodes or sink in excluded_nodes:
        return None

    distances: Dict[int, float] = {source: 0.0}
    predecessors: Dict[int, Optional[int]] = {source: None}
    pq = [(0.0, source)]
    visited: Set[int] = set()

    while pq:
        curr_dist, u = heapq.heappop(pq)
        if u in visited:
            continue
        visited.add(u)

        if u == sink:
            break

        for v, weight in adj.get(u, {}).items():
            if v in excluded_nodes or (u, v) in excluded_edges or (v, u) in excluded_edges:
                continue
            alt = curr_dist + weight
            if alt < distances.get(v, float("inf")):
                distances[v] = alt
                predecessors[v] = u
                heapq.heappush(pq, (alt, v))

    if sink not in distances:
        return None

    # Reconstruct path
    path = []
    curr: Optional[int] = sink
    while curr is not None:
        path.append(curr)
        curr = predecessors.get(curr)
    path.reverse()
    return path, distances[sink]


def _yen_k_shortest_paths(
    nodes: Sequence[int],
    adj: Dict[int, Dict[int, float]],
    source: int,
    sink: int,
    k_paths: int = 5,
) -> List[Tuple[List[int], float]]:
    """
    Yen's algorithm for finding the loopless K-shortest communication paths
    between source and sink on an allosteric residue network graph.
    """
    first_path = _dijkstra_shortest_path(nodes, adj, source, sink, set(), set())
    if not first_path:
        return []

    A = [first_path]
    B: List[Tuple[float, List[int]]] = []

    for k in range(1, k_paths):
        prev_path = A[k - 1][0]

        for i in range(len(prev_path) - 1):
            spur_node = prev_path[i]
            root_path = prev_path[: i + 1]

            excluded_edges: Set[Tuple[int, int]] = set()
            for p_tuple in A:
                p = p_tuple[0]
                if len(p) > i and p[: i + 1] == root_path:
                    excluded_edges.add((p[i], p[i + 1]))

            excluded_nodes = set(root_path[:-1])

            spur_res = _dijkstra_shortest_path(nodes, adj, spur_node, sink, excluded_nodes, excluded_edges)
            if spur_res is not None:
                spur_path, _ = spur_res
                total_candidate = root_path[:-1] + spur_path
                # Calculate total cost
                cost = 0.0
                for u, v in zip(total_candidate[:-1], total_candidate[1:]):
                    cost += adj[u][v]
                # Push to B if unique
                candidate_tuple = (total_candidate, cost)
                if not any(b_path == total_candidate for _, b_path in B) and not any(a_path == total_candidate for a_path, _ in A):
                    heapq.heappush(B, (cost, total_candidate))

        if not B:
            break

        cost, next_path = heapq.heappop(B)
        A.append((next_path, cost))

    return A


# ============================================================================
# Main Allosteric Pathway Tracer
# ============================================================================

def trace_allosteric_paths(
    pdb_text_or_path: Union[str, Path],
    source_resid: int,
    sink_resid: int,
    cutoff_angstroms: float = 7.0,
    k_paths: int = 5,
) -> AllostericNetworkResult:
    """
    Deterministic Allosteric Pathway Tracer.
    
    1. Parses C-alpha coordinates from PDB.
    2. Builds GNM Kirchhoff matrix K and computes pseudo-inverse K^dagger via Jacobi decomposition.
    3. Transforms GNM cross-correlations C_ij into path lengths d_ij = -ln(|C_ij|).
    4. Extracts top-K communication routes using Yen's loopless K-shortest paths algorithm.
    5. Computes Perturbation Response Scanning (PRS) effector and sensor profiles.
    """
    nodes = parse_pdb_ca_coordinates(pdb_text_or_path)
    if not nodes:
        raise ValueError("No valid C-alpha (CA) atoms found in provided PDB input.")

    resid_list = [n.resid for n in nodes]
    if source_resid not in resid_list:
        raise ValueError(f"Source residue ID {source_resid} not found in PDB structure.")
    if sink_resid not in resid_list:
        raise ValueError(f"Sink residue ID {sink_resid} not found in PDB structure.")

    N = len(nodes)
    cutoff_sq = cutoff_angstroms * cutoff_angstroms

    # Build GNM Kirchhoff matrix K
    K = [[0.0] * N for _ in range(N)]
    contact_pairs: Set[Tuple[int, int]] = set()

    for i in range(N):
        deg = 0.0
        xi, yi, zi = nodes[i].x, nodes[i].y, nodes[i].z
        for j in range(N):
            if i != j:
                xj, yj, zj = nodes[j].x, nodes[j].y, nodes[j].z
                dist_sq = (xi - xj) ** 2 + (yi - yj) ** 2 + (zi - zj) ** 2
                if dist_sq <= cutoff_sq:
                    K[i][j] = -1.0
                    deg += 1.0
                    contact_pairs.add((i, j))
        K[i][i] = deg

    # Compute pseudo-inverse via Jacobi decomposition
    K_pinv = _compute_gnm_pseudo_inverse(K)

    # Compute Cross-Correlations C_ij and edge weights
    # C_ij = K_pinv[i][j] / sqrt(K_pinv[i][i] * K_pinv[j][j])
    adj: Dict[int, Dict[int, float]] = {n.resid: {} for n in nodes}

    for (i, j) in contact_pairs:
        diag_i = K_pinv[i][i]
        diag_j = K_pinv[j][j]
        denom = math.sqrt(max(diag_i * diag_j, 1e-12))
        c_ij = abs(K_pinv[i][j]) / denom
        c_ij = min(1.0, max(c_ij, 1e-12))
        # Edge weight: higher correlation = shorter transfer distance
        weight = -math.log(c_ij)

        u = nodes[i].resid
        v = nodes[j].resid
        adj[u][v] = weight
        adj[v][u] = weight

    # Perturbation Response Scanning (PRS)
    # Effector profile: sum of responses when node i is perturbed
    # Sensor profile: sum of responses of node j when others are perturbed
    prs_effectors_raw: List[Tuple[float, int]] = []
    prs_sensors_raw: List[Tuple[float, int]] = []
    updated_nodes: List[ResidueNode] = []

    for i in range(N):
        eff_sum = sum(abs(K_pinv[i][j]) for j in range(N)) / N
        sens_sum = sum(abs(K_pinv[j][i]) for j in range(N)) / N

        prs_effectors_raw.append((eff_sum, nodes[i].resid))
        prs_sensors_raw.append((sens_sum, nodes[i].resid))

        updated_nodes.append(ResidueNode(
            resid=nodes[i].resid,
            resname=nodes[i].resname,
            chain=nodes[i].chain,
            x=nodes[i].x,
            y=nodes[i].y,
            z=nodes[i].z,
            prs_effectiveness=round(eff_sum, 4),
            prs_sensitivity=round(sens_sum, 4),
        ))

    prs_effectors_raw.sort(reverse=True)
    prs_sensors_raw.sort(reverse=True)

    top_effectors = tuple(r for _, r in prs_effectors_raw[: max(3, N // 5)])
    top_sensors = tuple(r for _, r in prs_sensors_raw[: max(3, N // 5)])

    # Extract top-K shortest loopless paths
    yen_paths = _yen_k_shortest_paths(resid_list, adj, source_resid, sink_resid, k_paths=k_paths)

    allost_paths: List[AllostericPath] = []
    residue_frequencies: Dict[int, int] = {}

    for path, cost in yen_paths:
        # Intermediate residues
        intermediates = path[1:-1]
        for r in intermediates:
            residue_frequencies[r] = residue_frequencies.get(r, 0) + 1

        # Bottleneck: intermediate residue with highest transfer cost on this path
        bottleneck = path[0]
        max_edge = 0.0
        for u, v in zip(path[:-1], path[1:]):
            edge_w = adj.get(u, {}).get(v, 0.0)
            if edge_w > max_edge:
                max_edge = edge_w
                bottleneck = v if v != sink_resid else u

        allost_paths.append(AllostericPath(
            source_resid=source_resid,
            sink_resid=sink_resid,
            path_residues=tuple(path),
            total_cost=round(cost, 3),
            bottleneck_residue=bottleneck,
        ))

    # Identify allosteric hotspot residues (highest frequency across communication routes + top effectors)
    hotspots = sorted(
        residue_frequencies.keys(),
        key=lambda r: (residue_frequencies[r], 1 if r in top_effectors else 0),
        reverse=True,
    )
    if not hotspots and allost_paths:
        hotspots = [allost_paths[0].bottleneck_residue]

    return AllostericNetworkResult(
        source_resid=source_resid,
        sink_resid=sink_resid,
        paths=tuple(allost_paths),
        hotspot_residues=tuple(hotspots),
        prs_effectors=top_effectors,
        prs_sensors=top_sensors,
        nodes=tuple(updated_nodes),
    )
