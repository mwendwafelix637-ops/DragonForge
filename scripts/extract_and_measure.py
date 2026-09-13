import numpy as np
import torch
from torch.utils.data import DataLoader
import argparse
import logging
from pathlib import Path
from omegaconf import OmegaConf
import json

from src.models.bdh_loader import create_bdh_model
from src.models.transformer_baseline import create_transformer_model
from src.instrumentation.graph_extractor import (
    GraphExtractor, GraphConfig, NodeType, EdgeType
)
from src.instrumentation.metrics import MetricsComputer
from src.instrumentation.checkpoint_utils import create_checkpoint_manager
from src.experiments.long_context import LongContextDataset

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def load_model(model_type: str, config, checkpoint_path: str, device: torch.device):
    if model_type == "bdh":
        model = create_bdh_model(config.model.bdh, checkpoint_path)
    elif model_type == "transformer":
        model = create_transformer_model(config.model.transformer, checkpoint_path)
    else:
        raise ValueError(f"Unknown model type: {model_type}")
    
    model = model.to(device)
    model.eval()
    logger.info(f"Loaded {model_type} model: {sum(p.numel() for p in model.parameters()):,} parameters")
    return model


def create_instrumentation_dataloader(config, batch_size: int = 4):
    dataset = LongContextDataset(
        task_type="needle_in_haystack",
        context_lengths=[config.instrumentation.graph_extraction.sample_seq_len],
        num_samples_per_length=config.instrumentation.graph_extraction.sample_batches * 4,
    )
    
    return DataLoader(dataset, batch_size=batch_size, shuffle=True, num_workers=4)


def extract_and_measure(model, dataloader, device, model_type: str, graph_config: GraphConfig):
    logger.info(f"Extracting interaction graph for {model_type}...")
    
    extractor = GraphExtractor(graph_config)
    graph = extractor.extract_from_model(model, dataloader, device, model_type)
    
    logger.info(f"Graph extracted: {len(graph.nodes)} nodes, {len(graph.edges)} edges")
    
    activations = get_activations(model, dataloader, device)
    
    weights = dict(model.named_parameters())
    
    logger.info("Computing structural metrics...")
    metrics_config = {
        'compute_modularity': True,
        'compute_degree_distribution': True,
        'compute_clustering': True,
        'compute_path_length': True,
        'compute_rich_club': True,
        'modularity_resolution': 1.0,
        'community_algorithm': 'louvain',
    }
    
    metrics_computer = MetricsComputer(metrics_config)
    metrics = metrics_computer.compute_all(
        graph.to_networkx(),
        adjacency_matrix=graph.adjacency_matrix,
        activations=activations,
        model_weights=weights,
    )
    
    return graph, metrics


def get_activations(model, dataloader, device, max_batches: int = 10):
    model.eval()
    activations = {}
    
    with torch.no_grad():
        for batch_idx, batch in enumerate(dataloader):
            if batch_idx >= max_batches:
                break
            
            if isinstance(batch, dict):
                inputs = batch['input_ids'].to(device)
                attention_mask = batch.get('attention_mask', None)
            else:
                inputs = batch[0].to(device)
                attention_mask = batch[1].to(device) if len(batch) > 1 else None
            
            outputs = model(inputs, attention_mask=attention_mask, return_activations=True)
            
            if 'activations' in outputs:
                for key, act in outputs['activations'].items():
                    if key not in activations:
                        activations[key] = act.cpu().numpy()
                    else:
                        activations[key] = np.concatenate([activations[key], act.cpu().numpy()], axis=0)
    
    return activations


def save_results(graph, metrics, model_type: str, output_dir: Path, checkpoint_manager):
    output_dir.mkdir(parents=True, exist_ok=True)
    
    graph_path = output_dir / f"{model_type}_interaction_graph.json"
    graph.save(str(graph_path))
    logger.info(f"Saved graph to {graph_path}")
    
    metrics_path = output_dir / f"{model_type}_structural_metrics.json"
    with open(metrics_path, 'w') as f:
        json.dump(metrics.to_dict(), f, indent=2, default=str)
    logger.info(f"Saved metrics to {metrics_path}")
    
    checkpoint_manager.save_graph(graph, "instrumentation", model_type)
    checkpoint_manager.save_metrics(metrics, "instrumentation", model_type)


def print_metrics_summary(metrics, model_type: str):
    print(f"\n{'='*50}")
    print(f"{model_type.upper()} Structural Metrics Summary")
    print(f"{'='*50}")
    print(f"Graph Sparsity:          {metrics.sparsity:.4f}")
    print(f"Activation Sparsity:     {metrics.activation_sparsity:.4f}")
    print(f"Weight Sparsity:         {metrics.weight_sparsity:.4f}")
    print(f"Modularity:              {metrics.modularity:.4f}")
    print(f"Number of Communities:   {metrics.n_communities}")
    print(f"Avg Degree:              {metrics.avg_degree:.2f}")
    print(f"Max Degree:              {metrics.max_degree}")
    print(f"Degree Assortativity:    {metrics.degree_assortativity:.4f}")
    print(f"Power Law Exponent:      {metrics.power_law_exponent}")
    print(f"Avg Clustering:          {metrics.avg_clustering:.4f}")
    print(f"Global Clustering:       {metrics.global_clustering:.4f}")
    print(f"Avg Path Length:         {metrics.avg_path_length}")
    print(f"Diameter:                {metrics.diameter}")
    print(f"Small-world Sigma:       {metrics.small_world_sigma}")
    print(f"Algebraic Connectivity:  {metrics.algebraic_connectivity}")
    print(f"Spectral Gap:            {metrics.spectral_gap}")
    print(f"{'='*50}\n")


def main():
    parser = argparse.ArgumentParser(description="Extract and measure structural properties")
    parser.add_argument("--config", type=str, default="configs/default.yaml", help="Config file path")
    parser.add_argument("--bdh-checkpoint", type=str, help="Path to BDH checkpoint")
    parser.add_argument("--transformer-checkpoint", type=str, help="Path to Transformer checkpoint")
    parser.add_argument("--model-type", type=str, choices=["bdh", "transformer", "both"], default="both")
    parser.add_argument("--device", type=str, default="cuda", help="Device (cuda/cpu)")
    parser.add_argument("--output-dir", type=str, default="results/structure/", help="Output directory")
    parser.add_argument("--node-type", type=str, default="neuron", choices=["neuron", "channel", "layer", "attention_head", "residual_stream"])
    parser.add_argument("--edge-type", type=str, default="correlation", choices=["correlation", "cosine", "mi", "gradient", "hebbian", "attention", "causal"])
    parser.add_argument("--correlation-threshold", type=float, default=0.3)
    parser.add_argument("--top-k-edges", type=int, default=None)
    parser.add_argument("--sample-batches", type=int, default=100)
    parser.add_argument("--sample-seq-len", type=int, default=512)
    args = parser.parse_args()
    
    config = OmegaConf.load(args.config)
    
    config.training.device = args.device
    config.model.bdh.device = args.device
    config.model.transformer.device = args.device
    config.instrumentation.graph_extraction.node_type = args.node_type
    config.instrumentation.graph_extraction.edge_type = args.edge_type
    config.instrumentation.graph_extraction.correlation_threshold = args.correlation_threshold
    config.instrumentation.graph_extraction.top_k_edges = args.top_k_edges
    config.instrumentation.graph_extraction.sample_batches = args.sample_batches
    config.instrumentation.graph_extraction.sample_seq_len = args.sample_seq_len
    
    device = torch.device(args.device)
    logger.info(f"Running on {device}")
    
    graph_config = GraphConfig(
        node_type=NodeType(args.node_type),
        edge_type=EdgeType(args.edge_type),
        correlation_threshold=args.correlation_threshold,
        top_k_edges=args.top_k_edges,
        sample_batches=args.sample_batches,
        sample_seq_len=args.sample_seq_len,
        target_layers=None,
    )
    
    dataloader = create_instrumentation_dataloader(config)
    
    checkpoint_manager = create_checkpoint_manager(config)
    
    output_dir = Path(args.output_dir)
    
    if args.model_type in ["bdh", "both"]:
        if args.bdh_checkpoint:
            bdh_model = load_model("bdh", config, args.bdh_checkpoint, device)
        else:
            logger.info("No BDH checkpoint provided, using random initialization")
            bdh_model = create_bdh_model(config.model.bdh).to(device)
        
        bdh_graph, bdh_metrics = extract_and_measure(
            bdh_model, dataloader, device, "bdh", graph_config
        )
        
        save_results(bdh_graph, bdh_metrics, "bdh", output_dir, checkpoint_manager)
        print_metrics_summary(bdh_metrics, "bdh")
    
    if args.model_type in ["transformer", "both"]:
        if args.transformer_checkpoint:
            trans_model = load_model("transformer", config, args.transformer_checkpoint, device)
        else:
            logger.info("No Transformer checkpoint provided, using random initialization")
            trans_model = create_transformer_model(config.model.transformer).to(device)
        
        trans_graph, trans_metrics = extract_and_measure(
            trans_model, dataloader, device, "transformer", graph_config
        )
        
        save_results(trans_graph, trans_metrics, "transformer", output_dir, checkpoint_manager)
        print_metrics_summary(trans_metrics, "transformer")
    
    if args.model_type == "both" and 'bdh_metrics' in locals() and 'trans_metrics' in locals():
        print("\n" + "="*50)
        print("COMPARISON: BDH vs Transformer")
        print("="*50)
        
        comparison = {
            'sparsity': bdh_metrics.sparsity - trans_metrics.sparsity,
            'activation_sparsity': bdh_metrics.activation_sparsity - trans_metrics.activation_sparsity,
            'weight_sparsity': bdh_metrics.weight_sparsity - trans_metrics.weight_sparsity,
            'modularity': bdh_metrics.modularity - trans_metrics.modularity,
            'avg_clustering': bdh_metrics.avg_clustering - trans_metrics.avg_clustering,
            'avg_degree': bdh_metrics.avg_degree - trans_metrics.avg_degree,
        }
        
        for metric, diff in comparison.items():
            direction = "higher" if diff > 0 else "lower"
            print(f"  {metric}: BDH is {direction} by {abs(diff):.4f}")
        
        print("="*50)
    
    logger.info("Extraction and measurement complete!")


if __name__ == "__main__":
    main()
