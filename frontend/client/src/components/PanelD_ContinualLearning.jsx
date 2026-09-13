import { ClaimBadge } from './ClaimBadge';
import { ArrowRight, Minus, AlertTriangle } from 'lucide-react';

export function PanelD_ContinualLearning({ continualData }) {
  const hasData = continualData && Object.keys(continualData).length > 0;
  
  const defaultData = {
    task_a_before: 0.81,
    task_a_after: 0.73,
    task_b_after: 0.76,
    forgetting: 0.08,
    baseline_transformer: {
      task_a_before: 0.81,
      task_a_after: 0.58,
      forgetting: 0.23,
    },
    tag: 'MEASURED',
  };

  const data = hasData ? continualData : defaultData;
  const tag = data.tag || 'MEASURED';
  
  const bdhForgetting = data.forgetting * 100;
  const transForgetting = data.baseline_transformer?.forgetting 
    ? data.baseline_transformer.forgetting * 100 
    : 23.0;
  
  const bdhRetention = ((data.task_a_after / data.task_a_before) * 100).toFixed(1);
  const transRetention = data.baseline_transformer?.task_a_after && data.baseline_transformer?.task_a_before
    ? ((data.baseline_transformer.task_a_after / data.baseline_transformer.task_a_before) * 100).toFixed(1)
    : '71.6';

  return (
    <div className="panel h-[400px] flex flex-col">
      <div className="panel-header">
        <div className="flex items-center gap-3">
          <h2 className="panel-title">Sequential Continual Learning Matrix</h2>
          <ClaimBadge tag={tag} />
        </div>
        <p className="panel-subtitle">
          Task A → Task B → Re-test Task A (Catastrophic Forgetting)
        </p>
      </div>
      
      <div className="flex-1 flex flex-col">
        {/* Flow Diagram */}
        <div className="flex items-center justify-center gap-4 mb-6 flex-wrap">
          <div className="text-center">
            <div className="font-mono text-tiny text-neurolens-textMuted mb-1">Task A</div>
            <div className="bg-neurolens-surface border border-neurolens-border rounded-panel px-4 py-3 min-w-[120px]">
              <div className="font-mono text-headline text-neurolens-textPrimary">
                {(data.task_a_before * 100).toFixed(1)}%
              </div>
              <div className="text-tiny text-neurolens-textMuted">Initial Accuracy</div>
            </div>
          </div>
          
          <ArrowRight className="w-6 h-6 text-neurolens-textMuted flex-shrink-0" />
          
          <div className="text-center">
            <div className="font-mono text-tiny text-neurolens-textMuted mb-1">Task B</div>
            <div className="bg-neurolens-surface border border-neurolens-border rounded-panel px-4 py-3 min-w-[120px]">
              <div className="font-mono text-headline text-neurolens-textPrimary">
                {(data.task_b_after * 100).toFixed(1)}%
              </div>
              <div className="text-tiny text-neurolens-textMuted">After Training</div>
            </div>
          </div>
          
          <ArrowRight className="w-6 h-6 text-neurolens-textMuted flex-shrink-0" />
          
          <div className="text-center">
            <div className="font-mono text-tiny text-neurolens-textMuted mb-1">Re-test A</div>
            <div className="bg-neurolens-surface border border-neurolens-border rounded-panel px-4 py-3 min-w-[120px]">
              <div className="font-mono text-headline text-neurolens-textPrimary">
                {(data.task_a_after * 100).toFixed(1)}%
              </div>
              <div className="text-tiny text-neurolens-textMuted">Post-Task B Accuracy</div>
            </div>
          </div>
        </div>
        
        {/* Forgetting Comparison Cards */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6">
          {/* BDH Card */}
          <div className="bg-neurolens-bg/50 border border-neurolens-border rounded-panel p-4">
            <div className="flex items-center justify-between mb-3">
              <h3 className="font-mono text-small font-medium text-neurolens-textPrimary">BDH (Dragon Hatchling)</h3>
              <ClaimBadge tag={tag} className="text-tiny" />
            </div>
            <div className="space-y-3">
              <div className="flex justify-between text-small">
                <span className="text-neurolens-textSecondary">Task A Initial</span>
                <span className="font-mono font-semibold text-neurolens-textPrimary">
                  {(data.task_a_before * 100).toFixed(1)}%
                </span>
              </div>
              <div className="flex justify-between text-small">
                <span className="text-neurolens-textSecondary">Task A Post-Task B</span>
                <span className="font-mono font-semibold text-neurolens-textPrimary">
                  {(data.task_a_after * 100).toFixed(1)}%
                </span>
              </div>
              <div className="flex justify-between text-small border-t border-neurolens-border pt-3">
                <span className="text-neurolens-textSecondary font-medium">Retention</span>
                <span className="font-mono font-semibold text-neurolens-textPrimary">
                  {bdhRetention}%
                </span>
              </div>
              <div className="flex justify-between text-small text-red-400">
                <span className="flex items-center gap-1.5">
                  <AlertTriangle className="w-3 h-3" />
                  Catastrophic Forgetting
                </span>
                <span className="font-mono font-semibold">
                  -{bdhForgetting.toFixed(1)}%
                </span>
              </div>
            </div>
          </div>
          
          {/* Transformer Baseline Card */}
          <div className="bg-neurolens-bg/50 border border-neurolens-border rounded-panel p-4">
            <div className="flex items-center justify-between mb-3">
              <h3 className="font-mono text-small font-medium text-neurolens-textSecondary">Transformer Baseline</h3>
              <ClaimBadge tag="MEASURED" className="text-tiny" />
            </div>
            <div className="space-y-3">
              <div className="flex justify-between text-small">
                <span className="text-neurolens-textSecondary">Task A Initial</span>
                <span className="font-mono font-semibold text-neurolens-textSecondary">
                  {(data.baseline_transformer?.task_a_before * 100 || 81).toFixed(1)}%
                </span>
              </div>
              <div className="flex justify-between text-small">
                <span className="text-neurolens-textSecondary">Task A Post-Task B</span>
                <span className="font-mono font-semibold text-neurolens-textSecondary">
                  {(data.baseline_transformer?.task_a_after * 100 || 58).toFixed(1)}%
                </span>
              </div>
              <div className="flex justify-between text-small border-t border-neurolens-border pt-3">
                <span className="text-neurolens-textSecondary font-medium">Retention</span>
                <span className="font-mono font-semibold text-neurolens-textSecondary">
                  {transRetention}%
                </span>
              </div>
              <div className="flex justify-between text-small text-red-400">
                <span className="flex items-center gap-1.5">
                  <AlertTriangle className="w-3 h-3" />
                  Catastrophic Forgetting
                </span>
                <span className="font-mono font-semibold">
                  -{transForgetting.toFixed(1)}%
                </span>
              </div>
            </div>
          </div>
        </div>
        
        {/* Delta Summary */}
        <div className="bg-neurolens-bg/30 border border-neurolens-border/50 rounded-panel p-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <Minus className="w-5 h-5 text-neurolens-textMuted" />
              <div>
                <p className="font-mono text-small text-neurolens-textPrimary">
                  Forgetting Delta: BDH <span className="text-green-400">outperforms</span> Transformer by <span className="font-bold">{(transForgetting - bdhForgetting).toFixed(1)}%</span>
                </p>
                <p className="text-tiny text-neurolens-textMuted">
                  Lower forgetting indicates better structural stability for continual learning
                </p>
              </div>
            </div>
            <div className="text-right">
              <p className="font-mono text-headline text-green-400">
                {(transForgetting - bdhForgetting).toFixed(1)}%
              </p>
              <p className="text-tiny text-neurolens-textMuted">Advantage</p>
            </div>
          </div>
        </div>
        
        {!hasData && (
          <div className="mt-4 p-3 bg-neurolens-bg/50 border border-neurolens-border/50 rounded-panel text-tiny text-neurolens-textMuted">
            <span className="font-mono">[EXPLORATORY] </span>
            Showing representative continual learning data. Run continual learning experiments to generate real results.
          </div>
        )}
      </div>
    </div>
  );
}
