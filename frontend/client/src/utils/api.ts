import type {
  StructureCheckpoint,
  StructureMetrics,
  InteractionGraph,
  ContinualLearningResult,
  ReasoningResult,
  ModelConfig,
} from '../types';

const API_BASE = '/api';

async function fetchJson<T>(endpoint: string): Promise<T> {
  const response = await fetch(`${API_BASE}${endpoint}`);
  if (!response.ok) {
    throw new Error(`API error: ${response.status} ${response.statusText}`);
  }
  return response.json();
}

export const api = {
  health: () => fetchJson<{ status: string; timestamp: string }>('/health'),
  
  structure: {
    all: () => fetchJson<{ checkpoints: StructureCheckpoint[]; count: number }>('/structure'),
    latest: () => fetchJson<StructureCheckpoint>('/structure/latest'),
    comparison: () => fetchJson<{ bdh: StructureMetrics | null; transformer: StructureMetrics | null }>('/structure/comparison'),
    graph: (model: 'bdh' | 'transformer') => fetchJson<InteractionGraph>(`/structure/graph?model=${model}`),
  },
  
  continual: {
    all: () => fetchJson<ContinualLearningResult>('/continual'),
  },
  
  reasoning: {
    all: () => fetchJson<ReasoningResult>('/reasoning'),
    comparison: () => fetchJson<{ tasks: Array<{ name: string; bdh: { mean: number; std: number }; transformer: { mean: number; std: number }; seeds: number[]; tag: string }> }>('/reasoning/comparison'),
  },
  
  config: {
    model: () => fetchJson<ModelConfig>('/config/model'),
  },
};
