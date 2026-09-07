"""
Spatiotemporal Graph for Indian Traffic Networks
Models intersection topology, neighbor relationships, and dynamic state aggregation.
"""

import json
import math
from typing import Dict, List, Tuple, Optional
from collections import defaultdict


class IntersectionNode:
    """
    Represents a single intersection in the traffic network.
    """
    
    def __init__(self, node_id: str, position: Tuple[float, float], 
                 lane_count: int = 4, road_width_m: float = 10.0):
        self.id = node_id
        self.position = position  # (x, y) in meters
        self.lane_count = lane_count
        self.road_width_m = road_width_m  # Indian roads are narrower
        
        # Indian-specific attributes
        self.has_auto_rickshaw_stand = False
        self.has_pedestrian_crossing = True  # Most Indian intersections
        self.has_speed_breaker = False
        
        # Dynamic state
        self.current_state = {}
        self.historical_states = []  # last N states for temporal analysis
        
    def update_state(self, state: Dict):
        """Update with new perception/simulator state."""
        self.current_state = state
        self.historical_states.append(state)
        if len(self.historical_states) > 50:  # keep last 50
            self.historical_states.pop(0)
    
    def get_temporal_trend(self, key: str, window: int = 10) -> float:
        """Calculate trend over last N states."""
        if not self.historical_states:
            return 0.0
        recent = self.historical_states[-window:]
        values = [s.get(key, 0) for s in recent if key in s]
        if not values:
            return 0.0
        # Simple trend: (latest - earliest) / earliest
        if len(values) > 1 and values[0] != 0:
            return (values[-1] - values[0]) / values[0]
        return 0.0


class SpatiotemporalGraph:
    """
    Graph representing the traffic network with spatiotemporal capabilities.
    """
    
    def __init__(self, network_type: str = 'indian_2x2'):
        self.nodes: Dict[str, IntersectionNode] = {}
        self.edges: Dict[str, List[str]] = defaultdict(list)  # adjacency list
        self.edge_weights: Dict[Tuple[str, str], float] = {}  # distance in meters
        self.network_type = network_type
        
    def build_standard_grid(self, rows: int = 2, cols: int = 2, 
                           spacing_m: float = 200.0):
        """
        Build a standard grid network.
        For Indian roads, spacing is typically 150-300m in urban areas.
        """
        self.nodes = {}
        self.edges = defaultdict(list)
        self.edge_weights = {}
        
        # Create nodes
        for r in range(rows):
            for c in range(cols):
                node_id = f"I{r*cols + c}"
                x = c * spacing_m
                y = r * spacing_m
                
                # Indian characteristics
                road_width = 8.0 if r == 0 and c == 0 else 10.0  # narrower in dense areas
                
                node = IntersectionNode(
                    node_id=node_id,
                    position=(x, y),
                    lane_count=4,
                    road_width_m=road_width
                )
                
                # Mark some intersections with auto-rickshaw stands (common in India)
                if (r + c) % 2 == 0:
                    node.has_auto_rickshaw_stand = True
                
                self.nodes[node_id] = node
        
        # Create edges (4-connected grid)
        for r in range(rows):
            for c in range(cols):
                node_id = f"I{r*cols + c}"
                
                # Right neighbor
                if c < cols - 1:
                    right_id = f"I{r*cols + (c+1)}"
                    self._add_edge(node_id, right_id, spacing_m)
                
                # Bottom neighbor
                if r < rows - 1:
                    bottom_id = f"I{(r+1)*cols + c}"
                    self._add_edge(node_id, bottom_id, spacing_m)
        
        print(f"[Graph] Built {rows}x{cols} grid with {len(self.nodes)} nodes, {len(self.edge_weights)} edges")
        
    def _add_edge(self, n1: str, n2: str, distance: float):
        """Add bidirectional edge."""
        self.edges[n1].append(n2)
        self.edges[n2].append(n1)
        self.edge_weights[(n1, n2)] = distance
        self.edge_weights[(n2, n1)] = distance
    
    def get_neighbors(self, node_id: str, hops: int = 1) -> List[str]:
        """
        Get neighbors within N hops.
        For SR module: 1-hop = immediate neighbors, 2-hop = extended context
        """
        if node_id not in self.nodes:
            return []
        
        visited = {node_id}
        current_level = {node_id}
        
        for _ in range(hops):
            next_level = set()
            for nid in current_level:
                for neighbor in self.edges.get(nid, []):
                    if neighbor not in visited:
                        visited.add(neighbor)
                        next_level.add(neighbor)
            current_level = next_level
        
        return list(current_level)  # excludes original node_id
    
    def get_neighbor_states(self, node_id: str, all_states: Dict, hops: int = 1) -> List[Dict]:
        """Get states of neighboring intersections."""
        neighbors = self.get_neighbors(node_id, hops)
        return [all_states.get(nid, {}) for nid in neighbors if nid in all_states]
    
    def get_spatial_context(self, node_id: str, all_states: Dict) -> str:
        """
        Build a spatial context string for LLM prompt.
        Describes the neighborhood layout and traffic patterns.
        """
        if node_id not in self.nodes:
            return ""
        
        node = self.nodes[node_id]
        neighbors = self.get_neighbors(node_id, hops=1)
        
        context = f"\n=== SPATIAL CONTEXT FOR {node_id} ===\n"
        context += f"Position: ({node.position[0]:.0f}m, {node.position[1]:.0f}m)\n"
        context += f"Road width: {node.road_width_m}m (Indian urban standard)\n"
        
        if node.has_auto_rickshaw_stand:
            context += "[WARN] Auto-rickshaw stand nearby - expect slow acceleration and lane blocking\n"
        
        if node.has_pedestrian_crossing:
            context += "[WARN] Pedestrian crossing - frequent jaywalking expected\n"
        
        context += f"\nConnected intersections ({len(neighbors)}):\n"
        for nid in neighbors:
            dist = self.edge_weights.get((node_id, nid), 0)
            nbr = self.nodes.get(nid)
            nbr_state = all_states.get(nid, {})
            severity = nbr_state.get('congestion_level', 'unknown')
            
            context += f"  -> {nid} ({dist:.0f}m away): congestion={severity}\n"
            
            if nbr and nbr.has_auto_rickshaw_stand:
                context += f"     (Has auto-rickshaw stand - potential bottleneck)\n"
        
        return context
    
    def aggregate_temporal_trends(self, node_id: str, all_states: Dict, window: int = 10) -> Dict:
        """
        Aggregate temporal trends across the neighborhood.
        Used by SR module to predict future congestion.
        """
        if node_id not in self.nodes:
            return {}
        
        node = self.nodes[node_id]
        neighbors = self.get_neighbors(node_id, hops=1)
        nodes_to_check = [node_id] + neighbors
        
        trends = {}
        for nid in nodes_to_check:
            n = self.nodes.get(nid)
            if n:
                queue_trend = n.get_temporal_trend('total_queued', window)
                occ_trend = n.get_temporal_trend('occupancy', window)
                trends[nid] = {
                    'queue_trend': round(queue_trend, 3),
                    'occupancy_trend': round(occ_trend, 3)
                }
        
        return trends
    
    def export_to_json(self, path: str):
        """Export graph structure to JSON."""
        data = {
            'network_type': self.network_type,
            'nodes': {},
            'edges': dict(self.edges),
            'edge_weights': {f"{k[0]}->{k[1]}": v for k, v in self.edge_weights.items()}
        }
        
        for nid, node in self.nodes.items():
            data['nodes'][nid] = {
                'position': node.position,
                'lane_count': node.lane_count,
                'road_width_m': node.road_width_m,
                'has_auto_rickshaw_stand': node.has_auto_rickshaw_stand,
                'has_pedestrian_crossing': node.has_pedestrian_crossing
            }
        
        with open(path, 'w') as f:
            json.dump(data, f, indent=2)
        
        print(f"[Graph] Exported to {path}")
    
    @classmethod
    def load_from_json(cls, path: str):
        """Load graph from JSON."""
        with open(path, 'r') as f:
            data = json.load(f)
        
        graph = cls(data.get('network_type', 'unknown'))
        
        for nid, ndata in data.get('nodes', {}).items():
            node = IntersectionNode(
                node_id=nid,
                position=tuple(ndata['position']),
                lane_count=ndata.get('lane_count', 4),
                road_width_m=ndata.get('road_width_m', 10.0)
            )
            node.has_auto_rickshaw_stand = ndata.get('has_auto_rickshaw_stand', False)
            node.has_pedestrian_crossing = ndata.get('has_pedestrian_crossing', True)
            graph.nodes[nid] = node
        
        for n1, neighbors in data.get('edges', {}).items():
            for n2 in neighbors:
                if (n1, n2) not in graph.edge_weights:
                    # Need to reconstruct weight from string key
                    weight_key = f"{n1}->{n2}"
                    dist = data.get('edge_weights', {}).get(weight_key, 200.0)
                    graph._add_edge(n1, n2, dist)
        
        return graph


def demo():
    """Demonstrate the spatiotemporal graph."""
    print("TrafficSense Spatiotemporal Graph Demo")
    print("=" * 60)
    
    # Build 2x2 Indian grid
    graph = SpatiotemporalGraph(network_type='indian_2x2')
    graph.build_standard_grid(rows=2, cols=2, spacing_m=200.0)
    
    # Show structure
    print(f"\nNodes: {list(graph.nodes.keys())}")
    for nid, node in graph.nodes.items():
        print(f"  {nid}: pos={node.position}, width={node.road_width_m}m, auto_stand={node.has_auto_rickshaw_stand}")
    
    print(f"\nEdges:")
    for n1, neighbors in graph.edges.items():
        for n2 in neighbors:
            dist = graph.edge_weights.get((n1, n2), 0)
            print(f"  {n1} <-> {n2}: {dist:.0f}m")
    
    # Test neighbor discovery
    print(f"\nNeighbors of I0 (1-hop): {graph.get_neighbors('I0', hops=1)}")
    print(f"Neighbors of I0 (2-hop): {graph.get_neighbors('I0', hops=2)}")
    
    # Test spatial context
    sample_states = {
        'I0': {'congestion_level': 'high', 'total_queued': 25},
        'I1': {'congestion_level': 'moderate', 'total_queued': 12},
        'I2': {'congestion_level': 'low', 'total_queued': 5},
        'I3': {'congestion_level': 'moderate', 'total_queued': 15}
    }
    
    context = graph.get_spatial_context('I0', sample_states)
    print(f"\nSpatial Context for I0:")
    print(context)
    
    # Export
    graph.export_to_json(r'C:\Pilli\trafficsense\outputs\indian_2x2_graph.json')
    print("\nGraph exported to outputs/indian_2x2_graph.json")
    
    # Load back
    loaded = SpatiotemporalGraph.load_from_json(r'C:\Pilli\trafficsense\outputs\indian_2x2_graph.json')
    print(f"Loaded graph with {len(loaded.nodes)} nodes")


if __name__ == '__main__':
    demo()
