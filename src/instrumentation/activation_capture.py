from __future__ import annotations

from typing import Dict, Iterable, Optional

import torch

from bdh.bdh import BDH


def capture_activations(
    model: BDH,
    input_ids: torch.Tensor,
    layers: Optional[Iterable[int]] = None,
) -> Dict[str, torch.Tensor]:
    if input_ids.ndim != 2:
        raise ValueError(
            f"input_ids must have shape [B, T], got {tuple(input_ids.shape)}"
        )

    if not torch.is_floating_point(input_ids) and input_ids.dtype != torch.long:
        input_ids = input_ids.long()

    requested_layers = None if layers is None else set(layers)

    model.capture_activations = True

    if hasattr(model, "activation_cache"):
        model.activation_cache.clear()

    was_training = model.training
    model.eval()

    with torch.no_grad():
        model(input_ids)

    if was_training:
        model.train()

    cache = getattr(model, "activation_cache", None)

    if cache is None:
        raise RuntimeError(
            "BDH did not expose activation_cache. "
            "Make sure the activation capture mechanism is enabled "
            "in the local BDH implementation."
        )

    result = {}

    for name, activation in cache.items():
        if not name.startswith("layer_"):
            continue

        layer_idx = int(name.split("_")[1])

        if requested_layers is not None and layer_idx not in requested_layers:
            continue

        result[name] = activation.detach().cpu()

    if not result:
        raise RuntimeError(
            "No BDH layer activations were captured."
        )

    return result


def activation_statistics(
    activations: Dict[str, torch.Tensor],
) -> Dict[str, Dict[str, float]]:
    statistics = {}

    for layer_name, activation in activations.items():
        total = activation.numel()
        zero_count = (activation == 0).sum().item()
        active_count = total - zero_count

        statistics[layer_name] = {
            "total_activations": int(total),
            "zero_activations": int(zero_count),
            "active_activations": int(active_count),
            "sparsity": zero_count / total if total else 0.0,
            "activity": active_count / total if total else 0.0,
            "mean_activation": activation.float().mean().item(),
            "max_activation": activation.float().max().item(),
        }

    return statistics
