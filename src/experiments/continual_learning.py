"""
Continual Learning Experiments

Tests model's ability to learn sequential tasks without catastrophic forgetting.
Compares BDH vs Transformer baseline on forgetting, forward/backward transfer.
"""

import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.utils.data import DataLoader, TensorDataset, Subset
import numpy as np
from typing import Dict, List, Optional, Tuple, Any, Callable
from dataclasses import dataclass, field
from pathlib import Path
import logging
from omegaconf import DictConfig
from collections import defaultdict
import copy

logger = logging.getLogger(__name__)


@dataclass
class Task:
    """Definition of a continual learning task."""
    name: str
    dataset_name: str
    task_id: int
    num_classes: int
    train_data: Any = None
    val_data: Any = None
    test_data: Any = None


@dataclass
class ContinualLearningResults:
    """Results from continual learning experiment."""
    # Per-task accuracies
    task_accuracies: Dict[str, Dict[int, float]] = field(default_factory=dict)  # task -> {eval_task: acc}
    # Forgetting measures
    forgetting: Dict[str, float] = field(default_factory=dict)
    # Forward transfer
    forward_transfer: Dict[str, float] = field(default_factory=dict)
    # Backward transfer
    backward_transfer: Dict[str, float] = field(default_factory=dict)
    # Average metrics
    avg_accuracy: float = 0.0
    avg_forgetting: float = 0.0
    avg_forward_transfer: float = 0.0
    avg_backward_transfer: float = 0.0
    # Per-epoch tracking
    training_curves: Dict[str, List[float]] = field(default_factory=dict)
    
    def to_dict(self) -> Dict:
        return {
            'task_accuracies': self.task_accuracies,
            'forgetting': self.forgetting,
            'forward_transfer': self.forward_transfer,
            'backward_transfer': self.backward_transfer,
            'avg_accuracy': self.avg_accuracy,
            'avg_forgetting': self.avg_forgetting,
            'avg_forward_transfer': self.avg_forward_transfer,
            'avg_backward_transfer': self.avg_backward_transfer,
            'training_curves': self.training_curves,
        }


class ContinualLearningExperiment:
    """
    Runs continual learning experiments on BDH and Transformer models.
    
    Implements:
    - Sequential task learning
    - Catastrophic forgetting measurement
    - Forward/backward transfer
    - Optional replay buffer
    """
    
    def __init__(self, config: DictConfig):
        self.config = config
        self.tasks: List[Task] = []
        self.device = torch.device(config.training.get('device', 'cuda'))
        self.results = ContinualLearningResults()
        
    def setup_tasks(self, tasks_config: List[Dict], 
                   dataset_loader: Callable[[str, int], Tuple[Any, Any, Any]]) -> List[Task]:
        """
        Setup tasks from config.
        
        Args:
            tasks_config: List of task configurations
            dataset_loader: Function(dataset_name, task_id) -> (train, val, test)
        """
        self.tasks = []
        for task_cfg in tasks_config:
            train_data, val_data, test_data = dataset_loader(
                task_cfg['dataset'], task_cfg['task_id']
            )
            task = Task(
                name=task_cfg['name'],
                dataset_name=task_cfg['dataset'],
                task_id=task_cfg['task_id'],
                num_classes=task_cfg['num_classes'],
                train_data=train_data,
                val_data=val_data,
                test_data=test_data,
            )
            self.tasks.append(task)
        
        logger.info(f"Setup {len(self.tasks)} continual learning tasks")
        return self.tasks
    
    def run(self, 
           model: nn.Module,
           optimizer_fn: Callable[[nn.Module], torch.optim.Optimizer],
           criterion: Callable = None,
           replay_buffer: Optional[Any] = None) -> ContinualLearningResults:
        """
        Run continual learning experiment.
        
        Args:
            model: Model to train (will be modified in-place)
            optimizer_fn: Function(model) -> optimizer
            criterion: Loss function (default: CrossEntropyLoss)
            replay_buffer: Optional replay buffer for experience replay
            
        Returns:
            ContinualLearningResults
        """
        if criterion is None:
            criterion = nn.CrossEntropyLoss()
        
        self.results = ContinualLearningResults()
        model = model.to(self.device)
        
        # Track accuracy matrix: task_accuracies[train_task][eval_task] = accuracy
        accuracy_matrix = defaultdict(dict)
        
        for task_idx, task in enumerate(self.tasks):
            logger.info(f"\n=== Training Task {task_idx+1}/{len(self.tasks)}: {task.name} ===")
            
            # Create optimizer for this task
            optimizer = optimizer_fn(model)
            
            # Prepare data loaders
            train_loader = DataLoader(
                task.train_data, 
                batch_size=self.config.training.batch_size, 
                shuffle=True,
                num_workers=self.config.training.get('num_workers', 4)
            )
            val_loader = DataLoader(
                task.val_data, 
                batch_size=self.config.training.batch_size * 2, 
                shuffle=False
            )
            
            # Add replay data if available
            if replay_buffer is not None and replay_buffer.size > 0:
                replay_data = replay_buffer.get_batch(self.config.training.batch_size)
                if replay_data is not None:
                    replay_loader = DataLoader(replay_data, batch_size=self.config.training.batch_size, shuffle=True)
                    # Combine with current task data
                    train_loader = self._combine_loaders(train_loader, replay_loader)
            
            # Training loop
            task_curves = []
            epochs_per_task = self.config.continual_learning.epochs_per_task
            
            for epoch in range(epochs_per_task):
                # Train
                train_loss = self._train_epoch(model, train_loader, optimizer, criterion, task)
                
                # Validate on current task
                val_acc = self._evaluate(model, val_loader, task)
                task_curves.append(val_acc)
                
                logger.info(f"  Epoch {epoch+1}/{epochs_per_task}: Loss={train_loss:.4f}, Val Acc={val_acc:.4f}")
            
            self.results.training_curves[task.name] = task_curves
            
            # Evaluate on all tasks so far
            for eval_idx, eval_task in enumerate(self.tasks[:task_idx+1]):
                test_loader = DataLoader(
                    eval_task.test_data, 
                    batch_size=self.config.training.batch_size * 2, 
                    shuffle=False
                )
                acc = self._evaluate(model, test_loader, eval_task)
                accuracy_matrix[task.name][eval_task.name] = acc
                logger.info(f"  Test Acc on {eval_task.name}: {acc:.4f}")
            
            # Update replay buffer
            if replay_buffer is not None:
                replay_buffer.add_task_data(task)
        
        # Compute final metrics
        self._compute_metrics(accuracy_matrix)
        
        return self.results
    
    def _train_epoch(self, model, train_loader, optimizer, criterion, task) -> float:
        """Train for one epoch."""
        model.train()
        total_loss = 0.0
        num_batches = 0
        
        for batch in train_loader:
            if isinstance(batch, dict):
                inputs = batch['input_ids'].to(self.device)
                labels = batch['labels'].to(self.device)
                attention_mask = batch.get('attention_mask', None)
                if attention_mask is not None:
                    attention_mask = attention_mask.to(self.device)
            elif isinstance(batch, (tuple, list)):
                inputs = batch[0].to(self.device)
                labels = batch[1].to(self.device)
                attention_mask = batch[2].to(self.device) if len(batch) > 2 else None
            else:
                raise ValueError(f"Unexpected batch format: {type(batch)}")
            
            optimizer.zero_grad()
            
            # Forward pass
            outputs = model(inputs, attention_mask=attention_mask)
            logits = outputs['logits'] if isinstance(outputs, dict) else outputs
            
            # For classification, use last token or pooled output
            if logits.dim() == 3:  # [batch, seq, vocab]
                # Use last token for classification
                logits = logits[:, -1, :task.num_classes]
            
            loss = criterion(logits, labels)
            loss.backward()
            
            # Gradient clipping
            torch.nn.utils.clip_grad_norm_(model.parameters(), self.config.training.gradient_clip)
            
            optimizer.step()
            
            total_loss += loss.item()
            num_batches += 1
        
        return total_loss / max(num_batches, 1)
    
    def _evaluate(self, model, data_loader, task) -> float:
        """Evaluate model on a task."""
        model.eval()
        correct = 0
        total = 0
        
        with torch.no_grad():
            for batch in data_loader:
                if isinstance(batch, dict):
                    inputs = batch['input_ids'].to(self.device)
                    labels = batch['labels'].to(self.device)
                    attention_mask = batch.get('attention_mask', None)
                    if attention_mask is not None:
                        attention_mask = attention_mask.to(self.device)
                elif isinstance(batch, (tuple, list)):
                    inputs = batch[0].to(self.device)
                    labels = batch[1].to(self.device)
                    attention_mask = batch[2].to(self.device) if len(batch) > 2 else None
                else:
                    raise ValueError(f"Unexpected batch format: {type(batch)}")
                
                outputs = model(inputs, attention_mask=attention_mask)
                logits = outputs['logits'] if isinstance(outputs, dict) else outputs
                
                if logits.dim() == 3:
                    logits = logits[:, -1, :task.num_classes]
                
                preds = logits.argmax(dim=-1)
                correct += (preds == labels).sum().item()
                total += labels.size(0)
        
        return correct / max(total, 1)
    
    def _combine_loaders(self, loader1, loader2):
        """Combine two data loaders."""
        # Simple approach: alternate batches
        class CombinedLoader:
            def __init__(self, l1, l2):
                self.l1 = l1
                self.l2 = l2
                self.iter1 = iter(l1)
                self.iter2 = iter(l2)
                self.use_l1 = True
            
            def __iter__(self):
                return self
            
            def __next__(self):
                try:
                    if self.use_l1:
                        return next(self.iter1)
                    else:
                        return next(self.iter2)
                except StopIteration:
                    # Switch to other loader
                    self.use_l1 = not self.use_l1
                    if self.use_l1:
                        self.iter1 = iter(self.l1)
                        return next(self.iter1)
                    else:
                        self.iter2 = iter(self.l2)
                        return next(self.iter2)
        
        return CombinedLoader(loader1, loader2)
    
    def _compute_metrics(self, accuracy_matrix: Dict[str, Dict[str, float]]):
        """Compute forgetting, forward/backward transfer from accuracy matrix."""
        task_names = list(accuracy_matrix.keys())
        
        if not task_names:
            return
        
        # Forgetting: for each task, difference between max accuracy and final accuracy
        for task_name in task_names:
            if task_name in accuracy_matrix:
                task_accs = accuracy_matrix[task_name]
                if task_accs:
                    max_acc = max(task_accs.values())
                    final_acc = task_accs.get(task_names[-1], 0)
                    self.results.forgetting[task_name] = max_acc - final_acc
        
        # Average forgetting
        if self.results.forgetting:
            self.results.avg_forgetting = np.mean(list(self.results.forgetting.values()))
        
        # Forward transfer: accuracy on new task after learning previous tasks vs random init
        # (Simplified: just use accuracy on each task when first trained)
        for i, task_name in enumerate(task_names):
            if i == 0:
                self.results.forward_transfer[task_name] = 0.0  # No previous tasks
            else:
                # Accuracy on this task after learning previous tasks
                first_train_acc = accuracy_matrix[task_name].get(task_name, 0)
                self.results.forward_transfer[task_name] = first_train_acc
        
        if self.results.forward_transfer:
            self.results.avg_forward_transfer = np.mean(list(self.results.forward_transfer.values()))
        
        # Backward transfer: change in accuracy on previous tasks after learning new task
        for i, task_name in enumerate(task_names):
            if i < len(task_names) - 1:
                # Accuracy before and after learning subsequent tasks
                acc_before = accuracy_matrix[task_name].get(task_name, 0)
                acc_after = accuracy_matrix[task_names[-1]].get(task_name, 0)
                self.results.backward_transfer[task_name] = acc_after - acc_before
            else:
                self.results.backward_transfer[task_name] = 0.0
        
        if self.results.backward_transfer:
            self.results.avg_backward_transfer = np.mean(list(self.results.backward_transfer.values()))
        
        # Overall average accuracy (on final model, all tasks)
        final_task = task_names[-1]
        final_accs = [accuracy_matrix[final_task].get(t, 0) for t in task_names]
        self.results.avg_accuracy = np.mean(final_accs) if final_accs else 0.0
        
        # Store full accuracy matrix
        self.results.task_accuracies = {k: dict(v) for k, v in accuracy_matrix.items()}
        
        logger.info(f"\n=== Continual Learning Results ===")
        logger.info(f"Average Accuracy: {self.results.avg_accuracy:.4f}")
        logger.info(f"Average Forgetting: {self.results.avg_forgetting:.4f}")
        logger.info(f"Average Forward Transfer: {self.results.avg_forward_transfer:.4f}")
        logger.info(f"Average Backward Transfer: {self.results.avg_backward_transfer:.4f}")


class ReplayBuffer:
    """Experience replay buffer for continual learning."""
    
    def __init__(self, buffer_size: int = 1000, strategy: str = "random"):
        self.buffer_size = buffer_size
        self.strategy = strategy
        self.buffer = []
        self.task_indices = []
    
    @property
    def size(self) -> int:
        return len(self.buffer)
    
    def add_task_data(self, task: Task, samples_per_class: int = None):
        """Add task data to buffer."""
        if samples_per_class is None:
            samples_per_class = max(1, self.buffer_size // (task.num_classes * len(self.task_indices) + task.num_classes))
        
        # For simplicity, add random samples from task
        # In practice, use herding or reservoir sampling
        indices = torch.randperm(len(task.train_data))[:samples_per_class * task.num_classes]
        for idx in indices:
            if len(self.buffer) < self.buffer_size:
                self.buffer.append(task.train_data[idx])
                self.task_indices.append(task.task_id)
            else:
                # Replace random element
                replace_idx = torch.randint(0, self.buffer_size, (1,)).item()
                self.buffer[replace_idx] = task.train_data[idx]
                self.task_indices[replace_idx] = task.task_id
    
    def get_batch(self, batch_size: int):
        """Get random batch from buffer."""
        if len(self.buffer) == 0:
            return None
        
        indices = torch.randperm(len(self.buffer))[:min(batch_size, len(self.buffer))]
        return [self.buffer[i] for i in indices]


def create_continual_learning_experiment(config: DictConfig) -> ContinualLearningExperiment:
    """Factory function."""
    return ContinualLearningExperiment(config)


# Dataset loaders for common continual learning benchmarks
def load_split_mnist(task_id: int, num_tasks: int = 5) -> Tuple[Any, Any, Any]:
    """Load Split MNIST task (2 classes per task)."""
    from torchvision import datasets, transforms
    
    transform = transforms.Compose([
        transforms.ToTensor(),
        transforms.Normalize((0.1307,), (0.3081,))
    ])
    
    train_dataset = datasets.MNIST('data/', train=True, download=True, transform=transform)
    test_dataset = datasets.MNIST('data/', train=False, download=True, transform=transform)
    
    # Split classes
    classes_per_task = 10 // num_tasks
    start_class = task_id * classes_per_task
    end_class = start_class + classes_per_task
    target_classes = list(range(start_class, end_class))
    
    # Filter datasets
    train_indices = [i for i, (_, label) in enumerate(train_dataset) if label in target_classes]
    test_indices = [i for i, (_, label) in enumerate(test_dataset) if label in target_classes]
    
    # Remap labels to 0...classes_per_task-1
    class_map = {c: i for i, c in enumerate(target_classes)}
    
    class RemappedDataset(torch.utils.data.Dataset):
        def __init__(self, base_dataset, indices, class_map):
            self.base_dataset = base_dataset
            self.indices = indices
            self.class_map = class_map
        
        def __len__(self):
            return len(self.indices)
        
        def __getitem__(self, idx):
            img, label = self.base_dataset[self.indices[idx]]
            return img, self.class_map[label]
    
    train_data = RemappedDataset(train_dataset, train_indices, class_map)
    test_data = RemappedDataset(test_dataset, test_indices, class_map)
    
    # Split train into train/val
    val_size = len(train_data) // 5
    train_size = len(train_data) - val_size
    train_subset, val_subset = torch.utils.data.random_split(train_data, [train_size, val_size])
    
    return train_subset, val_subset, test_data


def load_permuted_mnist(task_id: int, num_tasks: int = 5) -> Tuple[Any, Any, Any]:
    """Load Permuted MNIST task (same classes, permuted pixels)."""
    from torchvision import datasets, transforms
    
    # Task permutations are fixed across seeds on purpose: the tasks are the
    # experiment's constant, and only initialisation and batch order should
    # vary. A local generator is used so this does not reset the global RNG
    # state that seeding.set_all_seeds() established for the run.
    permutation = np.random.default_rng(task_id * 42).permutation(784)
    
    transform = transforms.Compose([
        transforms.ToTensor(),
        transforms.Lambda(lambda x: x.view(-1)[permutation].view(1, 28, 28)),
        transforms.Normalize((0.1307,), (0.3081,))
    ])
    
    train_dataset = datasets.MNIST('data/', train=True, download=True, transform=transform)
    test_dataset = datasets.MNIST('data/', train=False, download=True, transform=transform)
    
    val_size = len(train_dataset) // 5
    train_size = len(train_dataset) - val_size
    train_subset, val_subset = torch.utils.data.random_split(train_dataset, [train_size, val_size])
    
    return train_subset, val_subset, test_dataset


def load_split_cifar100(task_id: int, num_tasks: int = 10) -> Tuple[Any, Any, Any]:
    """Load Split CIFAR-100 task."""
    from torchvision import datasets, transforms
    
    transform_train = transforms.Compose([
        transforms.RandomCrop(32, padding=4),
        transforms.RandomHorizontalFlip(),
        transforms.ToTensor(),
        transforms.Normalize((0.5071, 0.4867, 0.4408), (0.2675, 0.2565, 0.2761))
    ])
    
    transform_test = transforms.Compose([
        transforms.ToTensor(),
        transforms.Normalize((0.5071, 0.4867, 0.4408), (0.2675, 0.2565, 0.2761))
    ])
    
    train_dataset = datasets.CIFAR100('data/', train=True, download=True, transform=transform_train)
    test_dataset = datasets.CIFAR100('data/', train=False, download=True, transform=transform_test)
    
    classes_per_task = 100 // num_tasks
    start_class = task_id * classes_per_task
    end_class = start_class + classes_per_task
    target_classes = list(range(start_class, end_class))
    
    train_indices = [i for i, (_, label) in enumerate(train_dataset) if label in target_classes]
    test_indices = [i for i, (_, label) in enumerate(test_dataset) if label in target_classes]
    
    class_map = {c: i for i, c in enumerate(target_classes)}
    
    class RemappedDataset(torch.utils.data.Dataset):
        def __init__(self, base_dataset, indices, class_map):
            self.base_dataset = base_dataset
            self.indices = indices
            self.class_map = class_map
        
        def __len__(self):
            return len(self.indices)
        
        def __getitem__(self, idx):
            img, label = self.base_dataset[self.indices[idx]]
            return img, self.class_map[label]
    
    train_data = RemappedDataset(train_dataset, train_indices, class_map)
    test_data = RemappedDataset(test_dataset, test_indices, class_map)
    
    val_size = len(train_data) // 5
    train_size = len(train_data) - val_size
    train_subset, val_subset = torch.utils.data.random_split(train_data, [train_size, val_size])
    
    return train_subset, val_subset, test_data