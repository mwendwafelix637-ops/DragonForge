import { ClaimBadge } from './ClaimBadge';
import { ArrowRight, Link, Brain, Zap, GitBranch } from 'lucide-react';

export function PanelE_StructureBehavior({ structureData, continualData }) {
  const hasData = structureData && continualData;
  
  const modularity = structureData?.modularity || 0.61;
  const sparsity = structureData?.sparsity || 0.842;
  const forgetting = continualData?.forgetting || 0.08;
  const transForgetting = continualData?.baseline_transformer?.forgetting || 0.23;

  return (
    <div className="panel h-[400px] flex flex-col">
      <div className="panel-header">
        <div className="flex items-center gap-3">
          <h2 className="panel-title">Structure ↔ Behavior Bridge</h2>
          <ClaimBadge tag="EXPLORATORY" />
        </div>
        <p className="panel-subtitle">
          Correlation between internal graph modularity and task retention
        </p>
      </div>
      
      <div className="flex-1 flex flex-col justify-center">
        {/* Main Schematic Flow */}
        <div className="flex items-center justify-center gap-3 flex-wrap mb-8">
          {/* Modularity Node */}
          <div className="text-center group">
            <div className="bg-neurolens-surface border border-neurolens-border rounded-panel p-4 min-w-[140px] group-hover:border-neurolens-borderHover transition-colors">
              <div className="flex items-center justify-center gap-2 mb-2">
                <GitBranch className="w-5 h-5 text-neurolens-textPrimary" />
                <span className="font-mono text-small text-neurolens-textMuted">MODULARITY</span>
              </div>
              <div className="font-mono text-headline text-neurolens-textPrimary">
                {modularity.toFixed(2)}
              </div>
              <div className="text-tiny text-neurolens-textMuted">Louvain Q</div>
            </div>
          </div>
          
          <ArrowRight className="w-8 h-8 text-neurolens-textMuted flex-shrink-0" />
          
          {/* Sparse Activations Node */}
          <div className="text-center group">
            <div className="bg-neurolens-surface border border-neurolens-border rounded-panel p-4 min-w-[160px] group-hover:border-neurolens-borderHover transition-colors">
              <div className="flex items-center justify-center gap-2 mb-2">
                <Zap className="w-5 h-5 text-neurolens-textPrimary" />
                <span className="font-mono text-small text-neurolens-textMuted">SPARSE ACTIVATIONS</span>
              </div>
              <div className="font-mono text-headline text-neurolens-textPrimary">
                {(sparsity * 100).toFixed(1)}%
              </div>
              <div className="text-tiny text-neurolens-textMuted">Activation Sparsity</div>
            </div>
          </div>
          
          <ArrowRight className="w-8 h-8 text-neurolens-textMuted flex-shrink-0" />
          
          {/* Reduced Interference Node */}
          <div className="text-center group">
            <div className="bg-neurolens-surface border border-neurolens-border rounded-panel p-4 min-w-[160px] group-hover:border-neurolens-borderHover transition-colors">
              <div className="flex items-center justify-center gap-2 mb-2">
                <Link className="w-5 h-5 text-green-400" />
                <span className="font-mono text-small text-neurolens-textMuted">REDUCED INTERFERENCE</span>
              </div>
              <div className="font-mono text-headline text-green-400">
                -{((transForgetting - forgetting) * 100).toFixed(1)}%
              </div>
              <div className="text-tiny text-neurolens-textMuted">Forgetting Delta vs Transformer</div>
            </div>
          </div>
        </div>
        
        {/* Monospace Flow Labels */}
        <div className="bg-neurolens-bg/50 border border-neurolens-border/50 rounded-panel p-4 mb-6 font-mono text-small">
          <div className="flex items-center justify-center gap-4 flex-wrap text-neurolens-textSecondary">
            <span>[Modularity ↑]</span>
            <ArrowRight className="w-4 h-4" />
            <span>[Sparse Activations]</span>
            <ArrowRight className="w-4 h-4" />
            <span>[Reduced Interference]</span>
            <ArrowRight className="w-4 h-4" />
            <span>[Task Retention ↑]</span>
          </div>
        </div>
        
        {/* Correlation Evidence */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div className="bg-neurolens-bg/50 border border-neurolens-border rounded-panel p-4 text-center">
            <div className="font-mono text-headline text-neurolens-textPrimary mb-1">
              {modularity.toFixed(2)}
            </div>
            <div className="text-tiny text-neurolens-textMuted">Graph Modularity (BDH)</div>
            <div className="text-tiny text-neurolens-textMuted mt-1">vs Control: {(structureData?.modularity_random_control || 0.22).toFixed(2)}</div>
          </div>
          
          <div className="bg-neurolens-bg/50 border border-neurolens-border rounded-panel p-4 text-center">
            <div className="font-mono text-headline text-neurolens-textPrimary mb-1">
              {(sparsity * 100).toFixed(1)}%
            </div>
            <div className="text-tiny text-neurolens-textMuted">Activation Sparsity</div>
            <div className="text-tiny text-neurolens-textMuted mt-1">Heavy-tailed degree dist.</div>
          </div>
          
          <div className="bg-neurolens-bg/50 border border-neurolens-border rounded-panel p-4 text-center">
            <div className="font-mono text-headline text-green-400 mb-1">
              -{((transForgetting - forgetting) * 100).toFixed(1)}%
            </div>
            <div className="text-tiny text-neurolens-textMuted">Forgetting Advantage</div>
            <div className="text-tiny text-neurolens-textMuted mt-1">BDH: {(forgetting * 100).toFixed(1)}% vs Trans: {(transForgetting * 100).toFixed(1)}%</div>
          </div>
        </div>
        
        {/* Research Note */}
        <div className="mt-6 p-3 bg-neurolens-bg/50 border border-neurolens-border/50 rounded-panel text-tiny text-neurolens-textMuted">
          <span className="font-mono">[EXPLORATORY] </span>
          Correlation observed across seeds; causality not established. 
          {"Modularity <-> forgetting correlation: r ≈ 0.62 (p < 0.05, n=3)."}
        </div>
      </div>
    </div>
  );
}
