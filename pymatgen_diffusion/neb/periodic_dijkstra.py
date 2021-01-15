# coding: utf-8
# Copyright (c) Materials Virtual Lab.
# Distributed under the terms of the BSD License.
"""
Dijkstra's path search on a graph where the nodes are on a periodic graph
"""

__author__ = "Jimmy Shen"
__copyright__ = "Copyright 2021, The Materials Project"
__maintainer__ = "Jimmy Shen"
__email__ = "jmmshn@lbl.gov"
__date__ = "April 11, 2019"

import heapq
import numpy as np
import math

from typing import Dict
from networkx.classes.graph import Graph
from collections import defaultdict
from pymatgen.analysis.graphs import StructureGraph


def _get_adjacency_with_images(G: Graph) -> Dict:
    """
    Return an adjacency dictionary with properly oriented "to_image" values.
    Note: the current implementation assumes that the original
    "to_jimage" value always corresponds to a an edge u -> v where u <= v.
    Returns:
        dict: Nested dictionary with [start][end][edge_key][data_field]
    """

    def copy_dict(d):
        # recursively copies the dictionary to resolve the fact that
        # two entries in the dictionary can point to the same mutable object
        # eg. changing p_graph[v][u][0]["to_jimage"] also changes
        # p_graph[u][v][0]["to_jimage"] if G was an undirecte graph.
        if isinstance(d, dict):
            new_d = {}
            for k, v in d.items():
                new_d[k] = copy_dict(v)
            return new_d
        return d

    # the dictionary generated by this are inherently linked so we have to
    # recursively copy the data
    p_graph = copy_dict(dict(G.adjacency()))

    # Make sure all the to_jimages are pointing in the correct direction
    for u in p_graph.keys():
        for v in p_graph[u].keys():
            for k, d in p_graph[u][v].items():
                if u > v:
                    p_graph[u][v][k]["to_jimage"] = tuple(
                        np.multiply(-1, d["to_jimage"])
                    )
    return p_graph


def periodic_dijkstra(
    G: Graph,
    sources: set,
    weight: str = "weight",
    max_image: int = 2,
    target_reached: callable = lambda idx, jimage: False,
) -> (Dict, Dict):
    """
    Find the lowest cost pathway from a source point in the periodic graph.
    Since the search can move many cells away without finding the target
    we have to limit how many cells away from (0,0,0) to search.

    Args:
        G (Graph): The graph object with additional "to_jimage" fields to
                indicate edges across periodic images.
        sources (set): the index of the source node
        target (int, optional): The index of of target node, if None populate all nodes. Defaults to None.
        max_image (int, optional): Defaults to 3.
        target_reached (callable, optional): A function of (site_index, jimage) used to check
            for stop iteration. This function is always called on the top of heap so it might miss the optimal path but
            often can find a "good enough" path very quickly.
    Returns:
        best_ans: a dictionary of the best cost found to periodic node keyed by (site_index, jimage)
        path_parent: dictionary of optimal path parent for each node given in index-image pairs.
    """

    conn_dict = _get_adjacency_with_images(G.to_undirected())
    # pprint(conn_dict[0][4])
    # print('=====')
    # pprint(conn_dict[4][0])

    # use a default dict since we don't know how far out to search
    best_ans = defaultdict(lambda: math.inf)

    path_parent = dict()  # the parent of the current node in the optimal path
    pq = []
    for isource in sources:
        heapq.heappush(pq, (0, (isource, (0, 0, 0))))
    while pq:
        min_val, (cur_idx, cur_image) = heapq.heappop(pq)
        if target_reached(cur_idx, cur_image):
            return best_ans
        if min_val < best_ans[(cur_idx, cur_image)]:
            best_ans[(cur_idx, cur_image)] = min_val
        for next_node, keyed_data in conn_dict[cur_idx].items():
            for k, d in keyed_data.items():
                # get the node index, image pair
                new_image = tuple(np.add(cur_image, d["to_jimage"]))
                next_index_pair = (next_node, new_image)

                if any(abs(i_) > max_image for i_ in new_image):
                    continue

                new_cost = min_val + d[weight]

                if new_cost < best_ans[next_index_pair]:
                    best_ans[next_index_pair] = new_cost
                    path_parent[next_index_pair] = (cur_idx, cur_image)
                    heapq.heappush(pq, (new_cost, next_index_pair))

    # return best_ans, path_parent


def periodic_dijkstra_on_sgraph(
    sgraph: StructureGraph,
    sources: set(),
    weight: str = "weight",
    max_image: int = 1,
    target_reached: callable = lambda idx, jimage: False,
):
    """
    Find the lowest cost pathway from a source point in the periodic graph.
    Since the search can move many cells away without finding the target
    we have to limit how many cells away from (0,0,0) to search.

    Args:
        sgraph (Graph): The StructureGraph object used for path searching
        sources (set): the index of the source node
        target (int, optional): The index of of target node, if None populate all nodes. Defaults to None.
        max_image (int, optional): Defaults to 3.
        target_reached (callable, optional): A function of (site_index, jimage) used to check
            for stop iteration. This function is always called on the top of heap so it might miss the optimal path but
            often can find a "good enough" path very quickly.
    Returns:
        best_ans: a dictionary of the best cost found to periodic node keyed by (site_index, jimage)
        path_parent: dictionary of optimal path parent for each node given in index-image pairs.
    """
    G = sgraph.graph.to_undirected()
    best_ans, path_parent = periodic_dijkstra(
        G,
        sources=sources,
        weight=weight,
        max_image=max_image,
        target_reached=target_reached,
    )
    return best_ans, path_parent


def get_optimal_pathway_rev(path_parent: dict, leaf_node: tuple):
    # follow a leaf node all the way up to source.
    cur = leaf_node
    while cur in path_parent:
        yield cur
        cur = path_parent[cur]
    yield cur
