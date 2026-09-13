import torch
import torch.nn as nn
import numpy as np
from typing import Dict, List, Optional, Tuple, Any, Callable
from dataclasses import dataclass, field
from enum import Enum
import networkx as nx
from omegaconf import DictConfig
import logging
from pathlib import Path
import json

logger = logging.getLogger(__name__)


class NodeType(Enum):
    NEURON = "neuron"
    CHANNEL = "channel"
    LAYER = "layer"
    ATTENTION_HEAD = "attention_head"
    RESIDUAL_STREAM = "residual_stream"


class EdgeType(Enum):
    CORRELATION = "correlation"
    COSINE_SIMILARITY = "cosine"
    MUTUAL_INFORMATION = "mi"
    GRADIENT_FLOW = "gradient"
    HEBBIAN = "hebbian"
    ATTENTION = "attention"
    CAUSAL = "causal"


@dataclass
class GraphConfig:
    node_type: NodeType = NodeType.NEURON
    edge_type: EdgeType = EdgeType.CORRELATION
    correlation_threshold: float = 0.3
    top_k_edges: Optional[int] = None
    sample_batches: int = 100
    sample_seq_len: int = 512
    target_layers: Optional[List[int]] = None
    min_samples_for_corr: int = 50
    symmetric_top_k: bool = True
    aggregate_over_seq: bool = True
    aggregate_over_batch: bool = True


@dataclass
class InteractionGraph:
    nodes: List[str]
    edges: List[Tuple[str, str, float]]
    adjacency_matrix: np.ndarray
    node_metadata: Dict[str, Dict]
    graph_config: GraphConfig
    model_type: str
    extraction_stats: Dict[str, Any]
    
    def to_networkx(self) -> nx.Graph:
        G = nx.Graph()
        G.add_nodes_from(self.nodes)
        for src, tgt, w in self.edges:
            G.add_edge(src, tgt, weight=w)
        for node, meta in self.node_metadata.items():
            G.nodes[node].update(meta)
        return G
    
    def to_dict(self) -> Dict:
        return {
            'nodes': self.nodes,
            'edges': [{'source': s, 'target': t, 'weight': w} for s, t, w in self.edges],
            'adjacency_matrix': self.adjacency_matrix.tolist(),
            'node_metadata': self.node_metadata,
            'graph_config': {
                'node_type': self.graph_config.node_type.value,
                'edge_type': self.graph_config.edge_type.value,
                'correlation_threshold': self.graph_config.correlation_threshold,
                'top_k_edges': self.graph_config.top_k_edges,
            },
            'model_type': self.model_type,
            'extraction_stats': self.extraction_stats,
        }
    
    def save(self, path: str):
        with open(path, 'w') as f:
            json.dump(self.to_dict(), f, indent=2)
    
    @classmethod
    def load(cls, path: str) -> 'InteractionGraph':
        with open(path, 'r') as f:
            data = json.load(f)
        config = GraphConfig(
            node_type=NodeType(data['graph_config']['node_type']),
            edge_type=EdgeType(data['graph_config']['edge_type']),
            correlation_threshold=data['graph_config']['correlation_threshold'],
            top_k_edges=data['graph_config']['top_k_edges'],
        )
        return cls(
            nodes=data['nodes'],
            edges=[(e['source'], e['target'], e['weight']) for e in data['edges']],
            adjacency_matrix=np.array(data['adjacency_matrix']),
            node_metadata=data['node_metadata'],
            graph_config=config,
            model_type=data['model_type'],
            extraction_stats=data['extraction_stats'],
        )


class GraphExtractor:
    def __init__(self, config: GraphConfig):
        self.config = config
        self.activation_buffer = {}
        
    def extract_from_model(self, 
                          model: nn.Module,
                          dataloader: torch.utils.data.DataLoader,
                          device: torch.device,
                          model_type: str = "unknown") -> InteractionGraph:
        logger.info(f"Extracting graph from {model_type} model...")
        
        activations = self._collect_activations(model, dataloader, device)
        
        nodes, node_metadata = self._define_nodes(activations, model_type)
        
        edges, adjacency = self._compute_edges(activations, nodes, node_metadata)
        
        stats = self._compute_extraction_stats(activations, nodes, edges)
        
        graph = InteractionGraph(
            nodes=nodes,
            edges=edges,
            adjacency_matrix=adjacency,
            node_metadata=node_metadata,
            graph_config=self.config,
            model_type=model_type,
            extraction_stats=stats,
        )
        
        logger.info(f"Extracted graph: {len(nodes)} nodes, {len(edges)} edges")
        return graph
    
    def _collect_activations(self, 
                            model: nn.Module,
                            dataloader: torch.utils.data.DataLoader,
                            device: torch.device) -> Dict[str, torch.Tensor]:
        model.eval()
        activations = {}
        counts = {}
        
        with torch.no_grad():
            for batch_idx, batch in enumerate(dataloader):
                if batch_idx >= self.config.sample_batches:
                    break
                    
                if isinstance(batch, dict):
                    input_ids = batch['input_ids'].to(device)
                    attention_mask = batch.get('attention_mask', None)
                    if attention_mask is not None:
                        attention_mask = attention_mask.to(device)
                elif isinstance(batch, (tuple, list)):
                    input_ids = batch[0].to(device)
                    attention_mask = batch[1].to(device) if len(batch) > 1 else None
                else:
                    input_ids = batch.to(device)
                    attention_mask = None
                
                if input_ids.size(1) > self.config.sample_seq_len:
                    input_ids = input_ids[:, :self.config.sample_seq_len]
                    if attention_mask is not None:
                        attention_mask = attention_mask[:, :self.config.sample_seq_len]
                
                outputs = model(input_ids, attention_mask, return_activations=True)
                
                if 'activations' in outputs:
                    for key, act in outputs['activations'].items():
                        if key not in activations:
                            activations[key] = act.cpu()
                            counts[key] = 1
                        else:
                            activations[key] = torch.cat([activations[key], act.cpu()], dim=0)
                            counts[key] += 1
        
        if self.config.aggregate_over_batch:
            for key in activations:
                activations[key] = activations[key].mean(dim=0, keepdim=True)
        
        logger.info(f"Collected activations for {len(activations)} layers/components")
        return activations
    
    def _define_nodes(self, 
                     activations: Dict[str, torch.Tensor],
                     model_type: str) -> Tuple[List[str], Dict[str, Dict]]:
        nodes = []
        node_metadata = {}
        
        for layer_name, act in activations.items():
            
            if self.config.node_type == NodeType.LAYER:
                node_id = f"{model_type}_{layer_name}"
                nodes.append(node_id)
                node_metadata[node_id] = {
                    'layer': layer_name,
                    'type': 'layer',
                    'model_type': model_type,
                    'shape': list(act.shape),
                }
                
            elif self.config.node_type == NodeType.NEURON:
                d_model = act.shape[-1]
                for neuron_idx in range(d_model):
                    node_id = f"{model_type}_{layer_name}_neuron_{neuron_idx}"
                    nodes.append(node_id)
                    node_metadata[node_id] = {
                        'layer': layer_name,
                        'neuron_idx': neuron_idx,
                        'type': 'neuron',
                        'model_type': model_type,
                    }
                    
            elif self.config.node_type == NodeType.CHANNEL:
                d_model = act.shape[-1]
                channel_size = 64
                n_channels = d_model // channel_size
                for ch in range(n_channels):
                    node_id = f"{model_type}_{layer_name}_channel_{ch}"
                    nodes.append(node_id)
                    node_metadata[node_id] = {
                        'layer': layer_name,
                        'channel_idx': ch,
                        'neuron_range': [ch*channel_size, (ch+1)*channel_size],
                        'type': 'channel',
                        'model_type': model_type,
                    }
                    
            elif self.config.node_type == NodeType.ATTENTION_HEAD:
                if 'attention' in layer_name.lower() or 'attn' in layer_name.lower():
                    n_heads = act.shape[-1] // 64
                    for h in range(n_heads):
                        node_id = f"{model_type}_{layer_name}_head_{h}"
                        nodes.append(node_id)
                        node_metadata[node_id] = {
                            'layer': layer_name,
                            'head_idx': h,
                            'type': 'attention_head',
                            'model_type': model_type,
                        }
                else:
                    node_id = f"{model_type}_{layer_name}"
                    nodes.append(node_id)
                    node_metadata[node_id] = {
                        'layer': layer_name,
                        'type': 'layer',
                        'model_type': model_type,
                    }
                    
            elif self.config.node_type == NodeType.RESIDUAL_STREAM:
                seq_len = act.shape[1] if act.dim() > 2 else 1
                for pos in range(min(seq_len, 128)):
                    node_id = f"{model_type}_{layer_name}_pos_{pos}"
                    nodes.append(node_id)
                    node_metadata[node_id] = {
                        'layer': layer_name,
                        'position': pos,
                        'type': 'residual_stream',
                        'model_type': model_type,
                    }
        
        if self.config.target_layers is not None:
            filtered_nodes = []
            filtered_metadata = {}
            for node in nodes:
                meta = node_metadata[node]
                layer_name = meta['layer']
                try:
                    layer_idx = int(layer_name.split('_')[-1])
                    if layer_idx in self.config.target_layers:
                        filtered_nodes.append(node)
                        filtered_metadata[node] = meta
                except (ValueError, IndexError):
                    filtered_nodes.append(node)
                    filtered_metadata[node] = meta
            nodes = filtered_nodes
            node_metadata = filtered_metadata
        
        return nodes, node_metadata
    
    def _compute_edges(self,
                      activations: Dict[str, torch.Tensor],
                      nodes: List[str],
                      node_metadata: Dict[str, Dict]) -> Tuple[List[Tuple[str, str, float]], np.ndarray]:
        n_nodes = len(nodes)
        adjacency = np.zeros((n_nodes, n_nodes), dtype=np.float32)
        edges = []
        
        node_activations = {}
        for node in nodes:
            meta = node_metadata[node]
            layer_name = meta['layer']
            act = activations.get(layer_name)
            
            if act is None:
                continue
                
            if self.config.aggregate_over_seq and act.dim() == 3:
                act = act.mean(dim=1)
            elif act.dim() == 3:
                act = act[:, 0, :]
            elif act.dim() == 2:
                pass
            else:
                act = act.flatten(1)
            
            if self.config.node_type == NodeType.NEURON:
                neuron_idx = meta['neuron_idx']
                node_act = act[:, neuron_idx]
            elif self.config.node_type == NodeType.CHANNEL:
                start, end = meta['neuron_range']
                node_act = act[:, start:end].mean(dim=1)
            elif self.config.node_type == NodeType.ATTENTION_HEAD:
                head_idx = meta['head_idx']
                head_dim = 64
                start = head_idx * head_dim
                end = start + head_dim
                node_act = act[:, start:end].mean(dim=1)
            elif self.config.node_type == NodeType.RESIDUAL_STREAM:
                pos = meta['position']
                if act.dim() == 3 and pos < act.shape[1]:
                    node_act = act[:, pos, :].mean(dim=1)
                else:
                    node_act = act.mean(dim=1) if act.dim() > 1 else act
            else:
                node_act = act.mean(dim=1) if act.dim() > 1 else act
            
            node_activations[node] = node_act.numpy()
        
        node_list = list(node_activations.keys())
        n_valid = len(node_list)
        
        if n_valid < 2:
            return edges, adjacency
        
        act_matrix = np.column_stack([node_activations[n] for n in node_list])
        
        if self.config.edge_type in [EdgeType.CORRELATION, EdgeType.COSINE_SIMILARITY]:
            if self.config.edge_type == EdgeType.CORRELATION:
                corr_matrix = np.corrcoef(act_matrix, rowvar=False)
            else:
                norms = np.linalg.norm(act_matrix, axis=0, keepdims=True)
                norms[norms == 0] = 1
                normalized = act_matrix / norms
                corr_matrix = normalized.T @ normalized
            
            np.fill_diagonal(corr_matrix, 0)
            
            if self.config.top_k_edges is not None:
                for i in range(n_valid):
                    row = corr_matrix[i]
                    top_k = min(self.config.top_k_edges, n_valid - 1)
                    if top_k > 0:
                        top_indices = np.argpartition(np.abs(row), -top_k)[-top_k:]
                        mask = np.zeros_like(row, dtype=bool)
                        mask[top_indices] = True
                        if self.config.symmetric_top_k:
                            mask = mask | np.zeros_like(row, dtype=bool)
                            mask[top_indices] = True
                        row[~mask] = 0
            else:
                corr_matrix[np.abs(corr_matrix) < self.config.correlation_threshold] = 0
            
            adjacency[:n_valid, :n_valid] = corr_matrix
            
            for i in range(n_valid):
                for j in range(i+1, n_valid):
                    w = corr_matrix[i, j]
                    if w != 0:
                        edges.append((node_list[i], node_list[j], float(w)))
        
        return edges, adjacency
    
    def _compute_extraction_stats(self,
                                 activations: Dict[str, torch.Tensor],
                                 nodes: List[str],
                                 edges: List[Tuple[str, str, float]]) -> Dict[str, Any]:
        return {
            'n_layers_sampled': len(activations),
            'n_nodes': len(nodes),
            'n_edges': len(edges),
            'edge_density': len(edges) / (len(nodes) * (len(nodes) - 1) / 2) if len(nodes) > 1 else 0,
            'avg_degree': 2 * len(edges) / len(nodes) if len(nodes) > 0 else 0,
            'activation_shapes': {k: list(v.shape) for k, v in activations.items()},
        }


