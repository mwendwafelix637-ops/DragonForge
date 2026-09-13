import torch

from bdh.bdh import BDH, BDHConfig
from src.instrumentation.activation_capture import (
    capture_activations,
    activation_statistics,
)


def make_random_input(config, seq_len=32):
    return torch.randint(
        0,
        config.vocab_size,
        (1, seq_len),
    )


def make_repeated_input(config, seq_len=32):
    token = torch.tensor([[42]])
    return token.repeat(1, seq_len)


def make_structured_input(config, seq_len=32):
    tokens = torch.arange(seq_len) % config.vocab_size
    return tokens.unsqueeze(0)


def run_probe(model, name, input_ids):
    activations = capture_activations(
        model,
        input_ids,
    )

    stats = activation_statistics(activations)

    print(f"\n{'=' * 60}")
    print(f"PROBE: {name}")
    print(f"{'=' * 60}")

    for layer_name in sorted(stats.keys()):
        s = stats[layer_name]

        print(
            f"{layer_name}: "
            f"sparsity={s['sparsity']:.4%}, "
            f"mean={s['mean_activation']:.6f}, "
            f"max={s['max_activation']:.6f}"
        )


def main():
    config = BDHConfig()
    model = BDH(config)

    probes = [
        (
            "random",
            make_random_input(config),
        ),
        (
            "repeated",
            make_repeated_input(config),
        ),
        (
            "structured",
            make_structured_input(config),
        ),
    ]

    for name, input_ids in probes:
        run_probe(
            model,
            name,
            input_ids,
        )


if __name__ == "__main__":
    main()
