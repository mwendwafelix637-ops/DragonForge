import torch
import torch.nn as nn
from typing import Dict, Any, Optional, List, Union
from pathlib import Path
import json
import logging
from datetime import datetime
from dataclasses import dataclass, asdict
from omegaconf import DictConfig, OmegaConf

logger = logging.getLogger(__name__)


@dataclass
class CheckpointMetadata:
    timestamp: str
    model_type: str
    model_config: Dict[str, Any]
    training_config: Dict[str, Any]
    epoch: int
    step: int
    loss: float
    metrics: Dict[str, float]
    git_commit: Optional[str] = None
    tags: List[str] = None
    
    def __post_init__(self):
        if self.tags is None:
            self.tags = []


class CheckpointManager:
    def __init__(self, checkpoint_dir: Union[str, Path] = "checkpoints/"):
        self.checkpoint_dir = Path(checkpoint_dir)
        self.checkpoint_dir.mkdir(parents=True, exist_ok=True)
        
        self.models_dir = self.checkpoint_dir / "models"
        self.graphs_dir = self.checkpoint_dir / "graphs"
        self.metrics_dir = self.checkpoint_dir / "metrics"
        self.results_dir = self.checkpoint_dir / "results"
        
        for d in [self.models_dir, self.graphs_dir, self.metrics_dir, self.results_dir]:
            d.mkdir(parents=True, exist_ok=True)
    
    def save_model_checkpoint(self,
                             model: nn.Module,
                             optimizer: Optional[torch.optim.Optimizer],
                             scheduler: Optional[torch.optim.lr_scheduler._LRScheduler],
                             epoch: int,
                             step: int,
                             loss: float,
                             metrics: Dict[str, float],
                             model_type: str,
                             model_config: DictConfig,
                             training_config: DictConfig,
                             name: Optional[str] = None,
                             tags: List[str] = None) -> Path:
        timestamp = datetime.now().isoformat()
        
        if name is None:
            name = f"{model_type}_epoch{epoch}_step{step}_{timestamp.replace(':', '-')}"
        
        checkpoint_path = self.models_dir / f"{name}.pt"
        
        metadata = CheckpointMetadata(
            timestamp=timestamp,
            model_type=model_type,
            model_config=OmegaConf.to_container(model_config, resolve=True),
            training_config=OmegaConf.to_container(training_config, resolve=True),
            epoch=epoch,
            step=step,
            loss=loss,
            metrics=metrics,
            tags=tags or [],
        )
        
        checkpoint = {
            'metadata': asdict(metadata),
            'model_state_dict': model.state_dict(),
            'optimizer_state_dict': optimizer.state_dict() if optimizer else None,
            'scheduler_state_dict': scheduler.state_dict() if scheduler else None,
            'epoch': epoch,
            'step': step,
            'loss': loss,
        }
        
        torch.save(checkpoint, checkpoint_path)
        logger.info(f"Saved checkpoint to {checkpoint_path}")
        
        meta_path = self.models_dir / f"{name}_meta.json"
        with open(meta_path, 'w') as f:
            json.dump(asdict(metadata), f, indent=2, default=str)
        
        return checkpoint_path
    
    def save_graph(self, graph: Any, name: str, model_type: str) -> Path:
        timestamp = datetime.now().isoformat().replace(':', '-')
        filename = f"{model_type}_{name}_{timestamp}.json"
        graph_path = self.graphs_dir / filename
        
        if hasattr(graph, 'save'):
            graph.save(str(graph_path))
        else:
            import networkx as nx
            data = nx.node_link_data(graph)
            with open(graph_path, 'w') as f:
                json.dump(data, f, indent=2, default=str)
        
        logger.info(f"Saved graph to {graph_path}")
        return graph_path
    
    def save_metrics(self, metrics: Any, name: str, model_type: str) -> Path:
        timestamp = datetime.now().isoformat().replace(':', '-')
        filename = f"{model_type}_{name}_{timestamp}.json"
        metrics_path = self.metrics_dir / filename
        
        if hasattr(metrics, 'to_dict'):
            data = metrics.to_dict()
        else:
            data = metrics
        
        with open(metrics_path, 'w') as f:
            json.dump(data, f, indent=2, default=str)
        
        logger.info(f"Saved metrics to {metrics_path}")
        return metrics_path
    
    def save_experiment_results(self,
                               results: Dict[str, Any],
                               experiment_name: str,
                               model_type: str) -> Path:
        timestamp = datetime.now().isoformat().replace(':', '-')
        filename = f"{model_type}_{experiment_name}_{timestamp}.json"
        results_path = self.results_dir / filename
        
        with open(results_path, 'w') as f:
            json.dump(results, f, indent=2, default=str)
        
        logger.info(f"Saved experiment results to {results_path}")
        return results_path


class ExperimentTracker:
    def __init__(self, tracker_dir: Union[str, Path] = "checkpoints/experiments/"):
        self.tracker_dir = Path(tracker_dir)
        self.tracker_dir.mkdir(parents=True, exist_ok=True)
        self.index_file = self.tracker_dir / "experiment_index.json"
        self._load_index()
    
    def _load_index(self):
        if self.index_file.exists():
            with open(self.index_file, 'r') as f:
                self.index = json.load(f)
        else:
            self.index = {'experiments': []}
    
    def _save_index(self):
        with open(self.index_file, 'w') as f:
            json.dump(self.index, f, indent=2, default=str)
    
    def log_experiment(self,
                      experiment_name: str,
                      config: DictConfig,
                      results: Dict[str, Any],
                      model_type: str,
                      tags: List[str] = None) -> str:
        timestamp = datetime.now().isoformat()
        exp_id = f"{experiment_name}_{model_type}_{timestamp.replace(':', '-')}"
        
        exp_record = {
            'id': exp_id,
            'name': experiment_name,
            'model_type': model_type,
            'timestamp': timestamp,
            'config': OmegaConf.to_container(config, resolve=True),
            'results': results,
            'tags': tags or [],
        }
        
        self.index['experiments'].append(exp_record)
        self._save_index()
        
        results_file = self.tracker_dir / f"{exp_id}_results.json"
        with open(results_file, 'w') as f:
            json.dump(exp_record, f, indent=2, default=str)
        
        logger.info(f"Logged experiment: {exp_id}")
        return exp_id
    
def create_checkpoint_manager(config: DictConfig) -> CheckpointManager:
    checkpoint_dir = config.paths.get('checkpoints_dir', 'checkpoints/')
    return CheckpointManager(checkpoint_dir)


def create_experiment_tracker(config: DictConfig) -> ExperimentTracker:
    tracker_dir = config.paths.get('checkpoints_dir', 'checkpoints/') + "experiments/"
    return ExperimentTracker(tracker_dir)
