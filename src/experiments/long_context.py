import torch
import torch.nn as nn
from torch.utils.data import DataLoader, Dataset
import numpy as np
from collections import defaultdict
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
import logging
from omegaconf import DictConfig
import random

logger = logging.getLogger(__name__)


@dataclass
class LongContextTask:
    name: str
    context_lengths: List[int]
    num_samples: int
    needle_type: str = "random_token"
    num_hops: int = 2
    num_variables: int = 3
    train_data: Any = None
    val_data: Any = None
    test_data: Any = None


@dataclass
class LongContextResults:
    accuracies: Dict[str, Dict[int, float]] = field(default_factory=dict)
    sample_details: Dict[str, List[Dict]] = field(default_factory=dict)
    avg_accuracy: float = 0.0
    accuracy_by_length: Dict[int, float] = field(default_factory=dict)
    length_scaling_exponent: Optional[float] = None
    
    def to_dict(self) -> Dict:
        return {
            'accuracies': self.accuracies,
            'sample_details': self.sample_details,
            'avg_accuracy': self.avg_accuracy,
            'accuracy_by_length': self.accuracy_by_length,
            'length_scaling_exponent': self.length_scaling_exponent,
        }


class LongContextExperiment:
    def __init__(self, config: DictConfig):
        self.config = config
        self.tasks: List[LongContextTask] = []
        self.device = torch.device(config.training.get('device', 'cuda'))
        self.results = LongContextResults()
        self.tokenizer = None
        
    def setup_tokenizer(self, tokenizer):
        self.tokenizer = tokenizer
    
    def setup_tasks(self, tasks_config: List[Dict]) -> List[LongContextTask]:
        self.tasks = []
        for task_cfg in tasks_config:
            task = LongContextTask(
                name=task_cfg['name'],
                context_lengths=task_cfg['context_lengths'],
                num_samples=task_cfg['num_samples'],
                needle_type=task_cfg.get('needle_type', 'random_token'),
                num_hops=task_cfg.get('num_hops', 2),
                num_variables=task_cfg.get('num_variables', 3),
            )
            self.tasks.append(task)
        
        logger.info(f"Setup {len(self.tasks)} long-context tasks")
        return self.tasks
    
    def generate_needle_in_haystack(self, 
                                   context_length: int,
                                   num_samples: int,
                                   needle_type: str = "random_token") -> List[Dict]:
        samples = []
        
        for _ in range(num_samples):
            vocab_size = 50257
            context = torch.randint(0, vocab_size, (context_length - 1,))
            
            if needle_type == "random_token":
                needle = torch.randint(1000, vocab_size - 1000, (1,)).item()
            elif needle_type == "specific_phrase":
                needle = 42
            else:
                needle = torch.randint(1000, vocab_size - 1000, (1,)).item()
            
            insert_pos = random.randint(0, context_length - 2)
            context = torch.cat([
                context[:insert_pos],
                torch.tensor([needle]),
                context[insert_pos:]
            ])
            
            query_token = 50256
            input_ids = torch.cat([context, torch.tensor([query_token])])
            
            samples.append({
                'input_ids': input_ids,
                'labels': torch.tensor([needle]),
                'needle_position': insert_pos,
                'context_length': context_length,
            })
        
        return samples
    
    def generate_multi_hop_qa(self,
                             context_length: int,
                             num_samples: int,
                             num_hops: int = 3) -> List[Dict]:
        samples = []
        
        for _ in range(num_samples):
            entities = torch.randint(10000, 30000, (num_hops + 1,)).tolist()
            
            context_parts = []
            for i in range(num_hops):
                rel_token = 1000 + i
                context_parts.extend([entities[i], rel_token, entities[i+1]])
            
            context = torch.tensor(context_parts)
            if len(context) < context_length - 2:
                padding = torch.randint(1000, 10000, (context_length - 2 - len(context),))
                context = torch.cat([context, padding])
            else:
                context = context[:context_length - 2]
            
            query_token = 50256
            input_ids = torch.cat([context, torch.tensor([entities[0], query_token])])
            
            samples.append({
                'input_ids': input_ids,
                'labels': torch.tensor([entities[-1]]),
                'entities': entities,
                'num_hops': num_hops,
                'context_length': context_length,
            })
        
        return samples
    
    def generate_variable_tracking(self,
                                  context_length: int,
                                  num_samples: int,
                                  num_variables: int = 5) -> List[Dict]:
        samples = []
        
        var_tokens = torch.randint(20000, 25000, (num_variables,)).tolist()
        value_tokens = torch.randint(30000, 40000, (20,)).tolist()
        assign_token = 5000
        query_token = 50256
        
        for _ in range(num_samples):
            num_assignments = min(context_length // 3, 20)
            assignments = []
            var_values = {v: None for v in var_tokens}
            
            for _ in range(num_assignments):
                var = random.choice(var_tokens)
                val = random.choice(value_tokens)
                var_values[var] = val
                assignments.extend([var, assign_token, val])
            
            context = torch.tensor(assignments)
            if len(context) < context_length - 3:
                padding = torch.randint(1000, 10000, (context_length - 3 - len(context),))
                context = torch.cat([context, padding])
            else:
                context = context[:context_length - 3]
            
            queried_var = random.choice(var_tokens)
            true_value = var_values[queried_var]
            if true_value is None:
                true_value = random.choice(value_tokens)
            
            input_ids = torch.cat([context, torch.tensor([queried_var, query_token])])
            
            samples.append({
                'input_ids': input_ids,
                'labels': torch.tensor([true_value]),
                'queried_var': queried_var,
                'var_values': var_values,
                'context_length': context_length,
            })
        
        return samples
    
    def prepare_all_data(self):
        for task in self.tasks:
            logger.info(f"Generating data for task: {task.name}")
            all_samples = []
            
            for ctx_len in task.context_lengths:
                if task.name == "needle_in_haystack":
                    samples = self.generate_needle_in_haystack(
                        ctx_len, task.num_samples, task.needle_type
                    )
                elif task.name == "multi_hop_qa":
                    samples = self.generate_multi_hop_qa(
                        ctx_len, task.num_samples, task.num_hops
                    )
                elif task.name == "variable_tracking":
                    samples = self.generate_variable_tracking(
                        ctx_len, task.num_samples, task.num_variables
                    )
                else:
                    logger.warning(f"Unknown task: {task.name}")
                    continue
                
                all_samples.extend(samples)
            
            random.shuffle(all_samples)
            n = len(all_samples)
            train_end = int(0.7 * n)
            val_end = int(0.85 * n)
            
            task.train_data = all_samples[:train_end]
            task.val_data = all_samples[train_end:val_end]
            task.test_data = all_samples[val_end:]
            
            logger.info(f"  Train: {len(task.train_data)}, Val: {len(task.val_data)}, Test: {len(task.test_data)}")
    
    def run(self, model: nn.Module) -> LongContextResults:
        self.results = LongContextResults()
        model = model.to(self.device)
        model.eval()
        
        all_accuracies = []
        
        for task in self.tasks:
            logger.info(f"\n=== Evaluating Task: {task.name} ===")
            task_accuracies = {}
            task_details = []
            
            for ctx_len in task.context_lengths:
                test_samples = [s for s in task.test_data if s['context_length'] == ctx_len]
                
                if not test_samples:
                    logger.warning(f"  No test samples for context length {ctx_len}")
                    continue
                
                test_loader = self._create_dataloader(test_samples)
                
                correct = 0
                total = 0
                sample_details = []
                
                with torch.no_grad():
                    for batch in test_loader:
                        inputs = batch['input_ids'].to(self.device)
                        labels = batch['labels'].to(self.device)
                        
                        outputs = model(inputs)
                        logits = outputs['logits'] if isinstance(outputs, dict) else outputs
                        
                        preds = logits[:, -1, :].argmax(dim=-1)
                        
                        batch_correct = (preds == labels).sum().item()
                        correct += batch_correct
                        total += labels.size(0)
                        
                        for i in range(labels.size(0)):
                            sample_details.append({
                                'predicted': preds[i].item(),
                                'true': labels[i].item(),
                                'correct': preds[i].item() == labels[i].item(),
                            })
                
                accuracy = correct / max(total, 1)
                task_accuracies[ctx_len] = accuracy
                task_details.extend(sample_details)
                all_accuracies.append(accuracy)
                
                logger.info(f"  Context Length {ctx_len}: Accuracy = {accuracy:.4f} ({correct}/{total})")
            
            self.results.accuracies[task.name] = task_accuracies
            self.results.sample_details[task.name] = task_details
        
        self.results.avg_accuracy = np.mean(all_accuracies) if all_accuracies else 0.0
        
        length_accs = defaultdict(list)
        for accs in self.results.accuracies.values():
            for length, acc in accs.items():
                length_accs[length].append(acc)
        
        for length, accs in length_accs.items():
            self.results.accuracy_by_length[length] = np.mean(accs)
        
        if len(self.results.accuracy_by_length) >= 3:
            lengths = np.array(sorted(self.results.accuracy_by_length.keys()))
            accs = np.array([self.results.accuracy_by_length[l] for l in lengths])
            log_lengths = np.log(lengths)
            log_accs = np.log(np.maximum(accs, 1e-6))
            try:
                coeffs = np.polyfit(log_lengths, log_accs, 1)
                self.results.length_scaling_exponent = float(coeffs[0])
            except (ValueError, np.linalg.LinAlgError):
                self.results.length_scaling_exponent = None

        logger.info("\n=== Long-Context Results ===")
        logger.info(f"Average Accuracy: {self.results.avg_accuracy:.4f}")
        logger.info(f"Length Scaling Exponent: {self.results.length_scaling_exponent}")
        
        return self.results
    
    def _create_dataloader(self, samples: List[Dict], batch_size: int = None) -> DataLoader:
        if batch_size is None:
            batch_size = self.config.long_context.eval_batch_size
        
        class SampleDataset(Dataset):
            def __init__(self, samples):
                self.samples = samples
            
            def __len__(self):
                return len(self.samples)
            
            def __getitem__(self, idx):
                s = self.samples[idx]
                return {
                    'input_ids': s['input_ids'],
                    'labels': s['labels'],
                }
        
        return DataLoader(SampleDataset(samples), batch_size=batch_size, shuffle=False)


class LongContextDataset(Dataset):
    def __init__(self, 
                 task_type: str,
                 context_lengths: List[int],
                 num_samples_per_length: int,
                 **task_kwargs):
        self.task_type = task_type
        self.context_lengths = context_lengths
        self.num_samples_per_length = num_samples_per_length
        self.task_kwargs = task_kwargs
        self.samples = []
        self._generate_all()
    
    def _generate_all(self):
        for ctx_len in self.context_lengths:
            for _ in range(self.num_samples_per_length):
                if self.task_type == "needle_in_haystack":
                    sample = self._gen_needle(ctx_len)
                elif self.task_type == "multi_hop_qa":
                    sample = self._gen_multihop(ctx_len)
                elif self.task_type == "variable_tracking":
                    sample = self._gen_tracking(ctx_len)
                else:
                    raise ValueError(f"Unknown task type: {self.task_type}")
                self.samples.append(sample)
    
    def _gen_needle(self, ctx_len):
        vocab_size = 50257
        context = torch.randint(0, vocab_size, (ctx_len - 1,))
        needle = torch.randint(1000, vocab_size - 1000, (1,)).item()
        insert_pos = random.randint(0, ctx_len - 2)
        context = torch.cat([context[:insert_pos], torch.tensor([needle]), context[insert_pos:]])
        return {
            'input_ids': torch.cat([context, torch.tensor([50256])]),
            'labels': torch.tensor([needle]),
            'context_length': ctx_len,
        }
    
    def _gen_multihop(self, ctx_len):
        num_hops = self.task_kwargs.get('num_hops', 3)
        entities = torch.randint(10000, 30000, (num_hops + 1,)).tolist()
        context_parts = []
        for i in range(num_hops):
            rel_token = 1000 + i
            context_parts.extend([entities[i], rel_token, entities[i+1]])
        context = torch.tensor(context_parts)
        if len(context) < ctx_len - 2:
            padding = torch.randint(1000, 10000, (ctx_len - 2 - len(context),))
            context = torch.cat([context, padding])
        else:
            context = context[:ctx_len - 2]
        return {
            'input_ids': torch.cat([context, torch.tensor([entities[0], 50256])]),
            'labels': torch.tensor([entities[-1]]),
            'context_length': ctx_len,
        }
    
    def _gen_tracking(self, ctx_len):
        num_variables = self.task_kwargs.get('num_variables', 5)
        var_tokens = torch.randint(20000, 25000, (num_variables,)).tolist()
        value_tokens = torch.randint(30000, 40000, (20,)).tolist()
        assign_token = 5000
        num_assignments = min(ctx_len // 3, 20)
        assignments = []
        var_values = {v: None for v in var_tokens}
        for _ in range(num_assignments):
            var = random.choice(var_tokens)
            val = random.choice(value_tokens)
            var_values[var] = val
            assignments.extend([var, assign_token, val])
        context = torch.tensor(assignments)
        if len(context) < ctx_len - 3:
            padding = torch.randint(1000, 10000, (ctx_len - 3 - len(context),))
            context = torch.cat([context, padding])
        else:
            context = context[:ctx_len - 3]
        queried_var = random.choice(var_tokens)
        true_value = var_values[queried_var] or random.choice(value_tokens)
        return {
            'input_ids': torch.cat([context, torch.tensor([queried_var, 50256])]),
            'labels': torch.tensor([true_value]),
            'context_length': ctx_len,
        }
    
    def __len__(self):
        return len(self.samples)
    
    def __getitem__(self, idx):
        s = self.samples[idx]
        return {
            'input_ids': s['input_ids'],
            'labels': s['labels'],
        }


def evaluate_long_context(model: nn.Module,
                         tokenizer,
                         task_configs: List[Dict],
                         config: DictConfig) -> LongContextResults:
    experiment = LongContextExperiment(config)
    experiment.setup_tokenizer(tokenizer)
    experiment.setup_tasks(task_configs)
    experiment.prepare_all_data()
    return experiment.run(model)
