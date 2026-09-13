import torch
import torch.nn as nn
from torch.utils.data import DataLoader
import numpy as np
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from pathlib import Path
import logging
import json
from datetime import datetime
from omegaconf import DictConfig, OmegaConf

from ..models.bdh_loader import create_bdh_model, BDHLoader
from ..models.transformer_baseline import create_transformer_model, TransformerLoader
from ..instrumentation.graph_extractor import (
    GraphExtractor, GraphConfig, NodeType, EdgeType, 
    InteractionGraph
)
from ..instrumentation.metrics import (
    MetricsComputer, StructuralMetrics, compare_models
)
from ..instrumentation.checkpoint_utils import (
    CheckpointManager, ExperimentTracker, create_checkpoint_manager, create_experiment_tracker
)
from ..experiments.continual_learning import (
    ContinualLearningExperiment, ContinualLearningResults,
    ReplayBuffer, load_split_mnist, load_permuted_mnist, load_split_cifar100
)
from ..experiments.long_context import (
    LongContextExperiment, LongContextResults, evaluate_long_context
)

logger = logging.getLogger(__name__)


@dataclass
class ExperimentConfig:
    bdh_config: DictConfig
    transformer_config: DictConfig
    training_config: DictConfig
    instrumentation_config: DictConfig
    continual_learning_config: DictConfig
    long_context_config: DictConfig
    paths: DictConfig
    logging_config: DictConfig
    
    run_instrumentation: bool = True
    run_continual_learning: bool = True
    run_long_context: bool = True
    compare_models: bool = True
    num_seeds: int = 3
    seed_offset: int = 0


@dataclass
class FullExperimentResults:
    bdh_structural_metrics: Optional[StructuralMetrics] = None
    transformer_structural_metrics: Optional[StructuralMetrics] = None
    structural_comparison: Optional[Dict] = None
    bdh_graph: Optional[InteractionGraph] = None
    transformer_graph: Optional[InteractionGraph] = None
    
    bdh_continual_results: Optional[ContinualLearningResults] = None
    transformer_continual_results: Optional[ContinualLearningResults] = None
    continual_comparison: Optional[Dict] = None
    
    bdh_long_context_results: Optional[LongContextResults] = None
    transformer_long_context_results: Optional[LongContextResults] = None
    long_context_comparison: Optional[Dict] = None
    
    config: Optional[Dict] = None
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    git_commit: Optional[str] = None
    
    def to_dict(self) -> Dict:
        result = {
            'timestamp': self.timestamp,
            'git_commit': self.git_commit,
            'config': self.config,
        }
        
        if self.bdh_structural_metrics:
            result['bdh_structural_metrics'] = self.bdh_structural_metrics.to_dict()
        if self.transformer_structural_metrics:
            result['transformer_structural_metrics'] = self.transformer_structural_metrics.to_dict()
        if self.structural_comparison:
            result['structural_comparison'] = self.structural_comparison
        if self.bdh_graph:
            result['bdh_graph'] = self.bdh_graph.to_dict()
        if self.transformer_graph:
            result['transformer_graph'] = self.transformer_graph.to_dict()
        if self.bdh_continual_results:
            result['bdh_continual_results'] = self.bdh_continual_results.to_dict()
        if self.transformer_continual_results:
            result['transformer_continual_results'] = self.transformer_continual_results.to_dict()
        if self.continual_comparison:
            result['continual_comparison'] = self.continual_comparison
        if self.bdh_long_context_results:
            result['bdh_long_context_results'] = self.bdh_long_context_results.to_dict()
        if self.transformer_long_context_results:
            result['transformer_long_context_results'] = self.transformer_long_context_results.to_dict()
        if self.long_context_comparison:
            result['long_context_comparison'] = self.long_context_comparison
            
        return result
    
    def save(self, path: str):
        with open(path, 'w') as f:
            json.dump(self.to_dict(), f, indent=2, default=str)
        logger.info(f"Saved full experiment results to {path}")


class ExperimentRunner:
    def __init__(self, config: ExperimentConfig):
        self.config = config
        self.device = torch.device(config.training_config.get('device', 'cuda'))
        self.results = FullExperimentResults()
        self.results.config = OmegaConf.to_container(
            OmegaConf.create({
                'bdh': config.bdh_config,
                'transformer': config.transformer_config,
                'training': config.training_config,
                'instrumentation': config.instrumentation_config,
                'continual_learning': config.continual_learning_config,
                'long_context': config.long_context_config,
                'paths': config.paths,
                'logging': config.logging_config,
            }), resolve=True
        )
        
        self.checkpoint_manager = create_checkpoint_manager(
            OmegaConf.create({'paths': config.paths})
        )
        self.experiment_tracker = create_experiment_tracker(
            OmegaConf.create({'paths': config.paths})
        )
        
        self._setup_logging()
    
    def _setup_logging(self):
        log_level = self.config.logging_config.get('level', 'INFO')
        log_dir = Path(self.config.logging_config.get('log_dir', 'logs/'))
        log_dir.mkdir(parents=True, exist_ok=True)
        
        logging.basicConfig(
            level=getattr(logging, log_level),
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_dir / f"experiment_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"),
                logging.StreamHandler()
            ]
        )
    
    def run_all(self) -> FullExperimentResults:
        logger.info("=" * 60)
        logger.info("Starting NeuroLens Experiment Pipeline")
        logger.info("=" * 60)
        
        logger.info("\n[1/5] Loading models...")
        bdh_model = self._load_bdh_model()
        transformer_model = self._load_transformer_model()
        
        logger.info("\n[2/5] Preparing dataloaders...")
        dataloader = self._create_instrumentation_dataloader()
        
        if self.config.run_instrumentation:
            logger.info("\n[3/5] Running structural instrumentation...")
            self._run_instrumentation(bdh_model, transformer_model, dataloader)
        
        if self.config.run_continual_learning:
            logger.info("\n[4/5] Running continual learning experiments...")
            self._run_continual_learning(bdh_model, transformer_model)
        
        if self.config.run_long_context:
            logger.info("\n[5/5] Running long-context reasoning experiments...")
            self._run_long_context(bdh_model, transformer_model)
        
        if self.config.compare_models:
            logger.info("\n[+] Comparing models...")
            self._compare_models()
        
        self._save_results()
        
        logger.info("\n" + "=" * 60)
        logger.info("NeuroLens Experiment Pipeline Complete!")
        logger.info("=" * 60)
        
        return self.results
    
    def _load_bdh_model(self) -> nn.Module:
        checkpoint_path = self.config.bdh_config.get('checkpoint_path')
        model = create_bdh_model(self.config.bdh_config, checkpoint_path)
        model = model.to(self.device)
        logger.info(f"Loaded BDH model: {sum(p.numel() for p in model.parameters()):,} parameters")
        return model
    
    def _load_transformer_model(self) -> nn.Module:
        checkpoint_path = self.config.transformer_config.get('checkpoint_path')
        model = create_transformer_model(self.config.transformer_config, checkpoint_path)
        model = model.to(self.device)
        logger.info(f"Loaded Transformer model: {sum(p.numel() for p in model.parameters()):,} parameters")
        return model
    
    def _create_instrumentation_dataloader(self) -> DataLoader:
        from ..experiments.long_context import LongContextDataset
        
        dataset = LongContextDataset(
            task_type="needle_in_haystack",
            context_lengths=[self.config.instrumentation_config.graph_extraction.sample_seq_len],
            num_samples_per_length=self.config.instrumentation_config.graph_extraction.sample_batches * 4,
        )
        
        return DataLoader(
            dataset,
            batch_size=4,
            shuffle=True,
            num_workers=self.config.training_config.get('num_workers', 4)
        )
    
    def _run_instrumentation(self, 
                            bdh_model: nn.Module,
                            transformer_model: nn.Module,
                            dataloader: DataLoader):
        graph_config = GraphConfig(
            node_type=NodeType(self.config.instrumentation_config.graph_extraction.node_type),
            edge_type=EdgeType(self.config.instrumentation_config.graph_extraction.edge_type),
            correlation_threshold=self.config.instrumentation_config.graph_extraction.correlation_threshold,
            top_k_edges=self.config.instrumentation_config.graph_extraction.top_k_edges,
            sample_batches=self.config.instrumentation_config.graph_extraction.sample_batches,
            sample_seq_len=self.config.instrumentation_config.graph_extraction.sample_seq_len,
            target_layers=self.config.instrumentation_config.graph_extraction.target_layers,
        )
        
        logger.info("Extracting BDH interaction graph...")
        bdh_extractor = GraphExtractor(graph_config)
        self.results.bdh_graph = bdh_extractor.extract_from_model(
            bdh_model, dataloader, self.device, model_type="bdh"
        )
        
        logger.info("Extracting Transformer interaction graph...")
        transformer_extractor = GraphExtractor(graph_config)
        self.results.transformer_graph = transformer_extractor.extract_from_model(
            transformer_model, dataloader, self.device, model_type="transformer"
        )
        
        logger.info("Computing structural metrics...")
        metrics_config = {
            'compute_modularity': self.config.instrumentation_config.metrics.compute_modularity,
            'compute_degree_distribution': self.config.instrumentation_config.metrics.compute_degree_distribution,
            'compute_clustering': self.config.instrumentation_config.metrics.compute_clustering,
            'compute_path_length': self.config.instrumentation_config.metrics.compute_path_length,
            'compute_rich_club': self.config.instrumentation_config.metrics.compute_rich_club,
            'modularity_resolution': self.config.instrumentation_config.metrics.modularity_resolution,
            'community_algorithm': self.config.instrumentation_config.metrics.community_algorithm,
        }
        
        metrics_computer = MetricsComputer(metrics_config)
        
        bdh_activations = self._get_activations_for_metrics(bdh_model, dataloader)
        transformer_activations = self._get_activations_for_metrics(transformer_model, dataloader)
        
        bdh_weights = dict(bdh_model.named_parameters())
        transformer_weights = dict(transformer_model.named_parameters())
        
        self.results.bdh_structural_metrics = metrics_computer.compute_all(
            self.results.bdh_graph.to_networkx(),
            adjacency_matrix=self.results.bdh_graph.adjacency_matrix,
            activations=bdh_activations,
            model_weights=bdh_weights,
        )
        
        self.results.transformer_structural_metrics = metrics_computer.compute_all(
            self.results.transformer_graph.to_networkx(),
            adjacency_matrix=self.results.transformer_graph.adjacency_matrix,
            activations=transformer_activations,
            model_weights=transformer_weights,
        )
        
        self.results.structural_comparison = compare_models(
            self.results.bdh_structural_metrics,
            self.results.transformer_structural_metrics
        )
        
        self.checkpoint_manager.save_graph(
            self.results.bdh_graph, "instrumentation", "bdh"
        )
        self.checkpoint_manager.save_graph(
            self.results.transformer_graph, "instrumentation", "transformer"
        )
        self.checkpoint_manager.save_metrics(
            self.results.bdh_structural_metrics, "instrumentation", "bdh"
        )
        self.checkpoint_manager.save_metrics(
            self.results.transformer_structural_metrics, "instrumentation", "transformer"
        )
        
        self._log_structural_results()
    
    def _get_activations_for_metrics(self, model: nn.Module, dataloader: DataLoader) -> Dict[str, np.ndarray]:
        model.eval()
        activations = {}
        
        with torch.no_grad():
            for batch_idx, batch in enumerate(dataloader):
                if batch_idx >= 10:
                    break
                    
                if isinstance(batch, dict):
                    inputs = batch['input_ids'].to(self.device)
                    attention_mask = batch.get('attention_mask', None)
                else:
                    inputs = batch[0].to(self.device)
                    attention_mask = batch[1].to(self.device) if len(batch) > 1 else None
                
                outputs = model(inputs, attention_mask=attention_mask, return_activations=True)
                
                if 'activations' in outputs:
                    for key, act in outputs['activations'].items():
                        if key not in activations:
                            activations[key] = act.cpu().numpy()
                        else:
                            activations[key] = np.concatenate([activations[key], act.cpu().numpy()], axis=0)
        
        return activations
    
    def _run_continual_learning(self, 
                               bdh_model: nn.Module,
                               transformer_model: nn.Module):
        tasks_config = self.config.continual_learning_config.tasks
        
        def dataset_loader(dataset_name: str, task_id: int):
            if dataset_name == "split_mnist":
                return load_split_mnist(task_id)
            elif dataset_name == "permuted_mnist":
                return load_permuted_mnist(task_id)
            elif dataset_name == "split_cifar100":
                return load_split_cifar100(task_id)
            else:
                raise ValueError(f"Unknown dataset: {dataset_name}")
        
        def optimizer_fn(model):
            return torch.optim.AdamW(
                model.parameters(),
                lr=self.config.training_config.learning_rate,
                weight_decay=self.config.training_config.weight_decay
            )
        
        logger.info("Running continual learning on BDH...")
        bdh_model_cl = self._load_bdh_model()
        cl_exp = ContinualLearningExperiment(self.config.continual_learning_config)
        cl_exp.setup_tasks(tasks_config, dataset_loader)
        
        replay_buffer = None
        if self.config.continual_learning_config.replay.enabled:
            replay_buffer = ReplayBuffer(
                buffer_size=self.config.continual_learning_config.replay.buffer_size,
                strategy=self.config.continual_learning_config.replay.strategy
            )
        
        self.results.bdh_continual_results = cl_exp.run(
            bdh_model_cl, optimizer_fn, replay_buffer=replay_buffer
        )
        
        self.checkpoint_manager.save_experiment_results(
            self.results.bdh_continual_results.to_dict(), 
            "continual_learning", "bdh"
        )
        
        logger.info("Running continual learning on Transformer...")
        transformer_model_cl = self._load_transformer_model()
        cl_exp = ContinualLearningExperiment(self.config.continual_learning_config)
        cl_exp.setup_tasks(tasks_config, dataset_loader)
        
        replay_buffer = None
        if self.config.continual_learning_config.replay.enabled:
            replay_buffer = ReplayBuffer(
                buffer_size=self.config.continual_learning_config.replay.buffer_size,
                strategy=self.config.continual_learning_config.replay.strategy
            )
        
        self.results.transformer_continual_results = cl_exp.run(
            transformer_model_cl, optimizer_fn, replay_buffer=replay_buffer
        )
        
        self.checkpoint_manager.save_experiment_results(
            self.results.transformer_continual_results.to_dict(),
            "continual_learning", "transformer"
        )
        
        self.results.continual_comparison = self._compare_continual_results(
            self.results.bdh_continual_results,
            self.results.transformer_continual_results
        )
        
        self._log_continual_results()
    
    def _run_long_context(self,
                         bdh_model: nn.Module,
                         transformer_model: nn.Module):
        tasks_config = self.config.long_context_config.tasks
        
        try:
            from transformers import GPT2TokenizerFast
            tokenizer = GPT2TokenizerFast.from_pretrained('gpt2')
            tokenizer.pad_token = tokenizer.eos_token
        except ImportError:
            logger.warning("transformers not installed, using basic tokenizer")
            tokenizer = None
        
        logger.info("Running long-context evaluation on BDH...")
        self.results.bdh_long_context_results = evaluate_long_context(
            bdh_model, tokenizer, tasks_config, self.config.long_context_config
        )
        
        self.checkpoint_manager.save_experiment_results(
            self.results.bdh_long_context_results.to_dict(),
            "long_context", "bdh"
        )
        
        logger.info("Running long-context evaluation on Transformer...")
        self.results.transformer_long_context_results = evaluate_long_context(
            transformer_model, tokenizer, tasks_config, self.config.long_context_config
        )
        
        self.checkpoint_manager.save_experiment_results(
            self.results.transformer_long_context_results.to_dict(),
            "long_context", "transformer"
        )
        
        self.results.long_context_comparison = self._compare_long_context_results(
            self.results.bdh_long_context_results,
            self.results.transformer_long_context_results
        )
        
        self._log_long_context_results()
    
    def _compare_continual_results(self,
                                  bdh_results: ContinualLearningResults,
                                  transformer_results: ContinualLearningResults) -> Dict:
        return {
            'avg_accuracy': {
                'bdh': bdh_results.avg_accuracy,
                'transformer': transformer_results.avg_accuracy,
                'difference': bdh_results.avg_accuracy - transformer_results.avg_accuracy,
            },
            'avg_forgetting': {
                'bdh': bdh_results.avg_forgetting,
                'transformer': transformer_results.avg_forgetting,
                'difference': bdh_results.avg_forgetting - transformer_results.avg_forgetting,
            },
            'avg_forward_transfer': {
                'bdh': bdh_results.avg_forward_transfer,
                'transformer': transformer_results.avg_forward_transfer,
                'difference': bdh_results.avg_forward_transfer - transformer_results.avg_forward_transfer,
            },
            'avg_backward_transfer': {
                'bdh': bdh_results.avg_backward_transfer,
                'transformer': transformer_results.avg_backward_transfer,
                'difference': bdh_results.avg_backward_transfer - transformer_results.avg_backward_transfer,
            },
            'task_accuracies_comparison': {
                'bdh': bdh_results.task_accuracies,
                'transformer': transformer_results.task_accuracies,
            }
        }
    
    def _compare_long_context_results(self,
                                     bdh_results: LongContextResults,
                                     transformer_results: LongContextResults) -> Dict:
        return {
            'avg_accuracy': {
                'bdh': bdh_results.avg_accuracy,
                'transformer': transformer_results.avg_accuracy,
                'difference': bdh_results.avg_accuracy - transformer_results.avg_accuracy,
            },
            'accuracy_by_length': {
                'bdh': bdh_results.accuracy_by_length,
                'transformer': transformer_results.accuracy_by_length,
            },
            'length_scaling_exponent': {
                'bdh': bdh_results.length_scaling_exponent,
                'transformer': transformer_results.length_scaling_exponent,
            },
            'per_task_comparison': {
                task: {
                    'bdh': bdh_results.accuracies.get(task, {}),
                    'transformer': transformer_results.accuracies.get(task, {}),
                }
                for task in set(bdh_results.accuracies.keys()) | set(transformer_results.accuracies.keys())
            }
        }
    
    def _compare_models(self):
        logger.info("\n=== OVERALL MODEL COMPARISON ===")
        
        if self.results.structural_comparison:
            logger.info("\n--- Structural Metrics ---")
            for key, val in self.results.structural_comparison.items():
                if isinstance(val, dict) and 'difference' in val:
                    diff = val['difference']
                    logger.info(f"  {key}: BDH={val['bdh']:.4f}, Transformer={val['transformer']:.4f}, Diff={diff:+.4f}")
        
        if self.results.continual_comparison:
            logger.info("\n--- Continual Learning ---")
            for key, val in self.results.continual_comparison.items():
                if isinstance(val, dict) and 'difference' in val:
                    diff = val['difference']
                    logger.info(f"  {key}: BDH={val['bdh']:.4f}, Transformer={val['transformer']:.4f}, Diff={diff:+.4f}")
        
        if self.results.long_context_comparison:
            logger.info("\n--- Long-Context Reasoning ---")
            for key, val in self.results.long_context_comparison.items():
                if isinstance(val, dict) and 'difference' in val:
                    diff = val['difference']
                    logger.info(f"  {key}: BDH={val['bdh']:.4f}, Transformer={val['transformer']:.4f}, Diff={diff:+.4f}")
    
    def _log_structural_results(self):
        if self.results.bdh_structural_metrics:
            m = self.results.bdh_structural_metrics
            logger.info("\nBDH Structural Metrics:")
            logger.info(f"  Graph Sparsity: {m.sparsity:.4f}")
            logger.info(f"  Activation Sparsity: {m.activation_sparsity:.4f}")
            logger.info(f"  Weight Sparsity: {m.weight_sparsity:.4f}")
            logger.info(f"  Modularity: {m.modularity:.4f} ({m.n_communities} communities)")
            logger.info(f"  Avg Degree: {m.avg_degree:.2f}")
            logger.info(f"  Avg Clustering: {m.avg_clustering:.4f}")
            logger.info(f"  Small-world Sigma: {m.small_world_sigma}")
        
        if self.results.transformer_structural_metrics:
            m = self.results.transformer_structural_metrics
            logger.info("\nTransformer Structural Metrics:")
            logger.info(f"  Graph Sparsity: {m.sparsity:.4f}")
            logger.info(f"  Activation Sparsity: {m.activation_sparsity:.4f}")
            logger.info(f"  Weight Sparsity: {m.weight_sparsity:.4f}")
            logger.info(f"  Modularity: {m.modularity:.4f} ({m.n_communities} communities)")
            logger.info(f"  Avg Degree: {m.avg_degree:.2f}")
            logger.info(f"  Avg Clustering: {m.avg_clustering:.4f}")
            logger.info(f"  Small-world Sigma: {m.small_world_sigma}")
    
    def _log_continual_results(self):
        if self.results.bdh_continual_results:
            r = self.results.bdh_continual_results
            logger.info(f"\nBDH Continual Learning:")
            logger.info(f"  Avg Accuracy: {r.avg_accuracy:.4f}")
            logger.info(f"  Avg Forgetting: {r.avg_forgetting:.4f}")
            logger.info(f"  Avg Forward Transfer: {r.avg_forward_transfer:.4f}")
            logger.info(f"  Avg Backward Transfer: {r.avg_backward_transfer:.4f}")
        
        if self.results.transformer_continual_results:
            r = self.results.transformer_continual_results
            logger.info(f"\nTransformer Continual Learning:")
            logger.info(f"  Avg Accuracy: {r.avg_accuracy:.4f}")
            logger.info(f"  Avg Forgetting: {r.avg_forgetting:.4f}")
            logger.info(f"  Avg Forward Transfer: {r.avg_forward_transfer:.4f}")
            logger.info(f"  Avg Backward Transfer: {r.avg_backward_transfer:.4f}")
    
    def _log_long_context_results(self):
        if self.results.bdh_long_context_results:
            r = self.results.bdh_long_context_results
            logger.info(f"\nBDH Long-Context:")
            logger.info(f"  Avg Accuracy: {r.avg_accuracy:.4f}")
            logger.info(f"  Length Scaling Exponent: {r.length_scaling_exponent}")
            for task, accs in r.accuracies.items():
                logger.info(f"  {task}: {accs}")
        
        if self.results.transformer_long_context_results:
            r = self.results.transformer_long_context_results
            logger.info(f"\nTransformer Long-Context:")
            logger.info(f"  Avg Accuracy: {r.avg_accuracy:.4f}")
            logger.info(f"  Length Scaling Exponent: {r.length_scaling_exponent}")
            for task, accs in r.accuracies.items():
                logger.info(f"  {task}: {accs}")
    
    def _save_results(self):
        results_dir = Path(self.config.paths.results_dir)
        results_dir.mkdir(parents=True, exist_ok=True)
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        results_path = results_dir / f"full_experiment_results_{timestamp}.json"
        
        self.results.save(str(results_path))
        
        self.experiment_tracker.log_experiment(
            experiment_name="full_pipeline",
            config=OmegaConf.create(self.results.config),
            results=self.results.to_dict(),
            model_type="comparison",
            tags=["bdh", "transformer", "instrumentation", "continual_learning", "long_context"]
        )


def create_experiment_runner(config: DictConfig) -> ExperimentRunner:
    exp_config = ExperimentConfig(
        bdh_config=config.model.bdh,
        transformer_config=config.model.transformer,
        training_config=config.training,
        instrumentation_config=config.instrumentation,
        continual_learning_config=config.continual_learning,
        long_context_config=config.long_context,
        paths=config.paths,
        logging_config=config.logging,
    )
    return ExperimentRunner(exp_config)


def run_full_pipeline(config: DictConfig) -> FullExperimentResults:
    runner = create_experiment_runner(config)
    return runner.run_all()


if __name__ == "__main__":
    import sys
    from omegaconf import OmegaConf
    
    config_path = sys.argv[1] if len(sys.argv) > 1 else "configs/default.yaml"
    config = OmegaConf.load(config_path)
    
    results = run_full_pipeline(config)
    
    print("\nExperiment completed successfully!")
    print(f"Results saved to {config.paths.results_dir}")
