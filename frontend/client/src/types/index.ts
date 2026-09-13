export interface StructureCheckpoint {
  step: number;
  modularity: number;
  modularity_random_control: number;
  sparsity: number;
  degree_distribution: number[];
  clustering_coefficient: number;
  timestamp: string;
}

export interface StructureMetrics {
  sparsity: number;
  activation_sparsity: number;
  weight_sparsity: number;
  modularity: number;
  n_communities: number;
  community_sizes: number[];
  community_assignments: Record<string, number>;
  avg_degree: number;
  max_degree: number;
  degree_assortativity: number;
  power_law_exponent: number | null;
  power_law_p_value: number | null;
  avg_clustering: number;
  global_clustering: number;
  clustering_distribution: number[];
  avg_path_length: number | null;
  diameter: number | null;
  radius: number | null;
  small_world_sigma: number | null;
  rich_club_coefficients: Record<number, number>;
  rich_club_normalized: Record<number, number>;
  algebraic_connectivity: number | null;
  spectral_gap: number | null;
  eigenvector_centrality: number[];
}

export interface InteractionGraph {
  nodes: string[];
  edges: [string, string, number][];
  adjacency_matrix: number[][];
  node_metadata: Record<string, NodeMetadata>;
  graph_config: GraphConfig;
  model_type: 'bdh' | 'transformer';
  extraction_stats: Record<string, unknown>;
}

export interface NodeMetadata {
  layer: string;
  neuron_idx?: number;
  channel_idx?: number;
  head_idx?: number;
  position?: number;
  type: string;
  model_type: string;
  community?: number;
}

export interface GraphConfig {
  node_type: 'neuron' | 'channel' | 'layer' | 'attention_head' | 'residual_stream';
  edge_type: 'correlation' | 'cosine' | 'mi' | 'gradient' | 'hebbian' | 'attention' | 'causal';
  correlation_threshold: number;
  top_k_edges: number | null;
  sample_batches: number;
  sample_seq_len: number;
  target_layers: number[] | null;
  aggregate_over_seq: boolean;
  aggregate_over_batch: boolean;
}

export interface ContinualLearningResult {
  task_a_before: number;
  task_a_after: number;
  task_b_after: number;
  forgetting: number;
  baseline_transformer: {
    task_a_before: number;
    task_a_after: number;
    forgetting: number;
  };
  tag: 'ESTABLISHED' | 'MEASURED' | 'EXPLORATORY' | 'PARTIALLY_SUPPORTED';
  seeds: number[];
  task_accuracies?: Record<string, Record<string, number>>;
  training_curves?: Record<string, number[]>;
  forward_transfer?: Record<string, number>;
  backward_transfer?: Record<string, number>;
  avg_accuracy?: number;
  avg_forgetting?: number;
  avg_forward_transfer?: number;
  avg_backward_transfer?: number;
}

export interface ReasoningResult {
  task_name: string;
  bdh_accuracy_mean: number;
  bdh_accuracy_std: number;
  transformer_accuracy_mean: number;
  transformer_accuracy_std: number;
  seeds: number[];
  tag: 'ESTABLISHED' | 'MEASURED' | 'EXPLORATORY' | 'PARTIALLY_SUPPORTED';
  accuracies?: Record<string, Record<number, number>>;
  accuracy_by_length?: Record<number, number>;
  length_scaling_exponent?: number;
  sample_details?: Record<string, Array<{ predicted: number; true: number; correct: boolean }>>;
}

export interface SummaryResult {
  headline: string;
  structure_finding: { claim: string; tag: string };
  continual_finding: { claim: string; tag: string };
  reasoning_finding: { claim: string; tag: string };
}

export interface ModelConfig {
  bdh: {
    model_name: string;
    vocab_size: number;
    d_model: number;
    n_layers: number;
    n_heads: number;
    d_ff: number;
    max_seq_len: number;
    dropout: number;
    sparsity_target: number;
    hebbian_lr: number;
    inhibition_strength: number;
    checkpoint_path: string | null;
    device: string;
  };
  transformer: {
    model_name: string;
    vocab_size: number;
    d_model: number;
    n_layers: number;
    n_heads: number;
    d_ff: number;
    max_seq_len: number;
    dropout: number;
    checkpoint_path: string | null;
    device: string;
  };
}

export interface InstrumentationConfig {
  graph_extraction: GraphConfig;
  metrics: {
    compute_sparsity: boolean;
    compute_modularity: boolean;
    compute_degree_distribution: boolean;
    compute_clustering: boolean;
    compute_path_length: boolean;
    compute_rich_club: boolean;
    modularity_resolution: number;
    community_algorithm: string;
  };
}
