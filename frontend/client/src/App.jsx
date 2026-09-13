import { useState } from 'react';
import {
  useLatestStructureCheckpoint,
  useStructureCheckpoints,
  useStructureGraph,
  useStructureComparison,
  useContinualLearning,
  useReasoning,
  useReasoningComparison,
  useModelConfig
} from './hooks/useData';
import { TopNav } from './components/TopNav';
import { PanelA_NetworkTopology } from './components/PanelA_NetworkTopology';
import { PanelB_TrainingEvolution } from './components/PanelB_TrainingEvolution';
import { PanelC_ReasoningBenchmark } from './components/PanelC_ReasoningBenchmark';
import { PanelD_ContinualLearning } from './components/PanelD_ContinualLearning';
import { PanelE_StructureBehavior } from './components/PanelE_StructureBehavior';
import { BottomBanner } from './components/BottomBanner';
import { RefreshCw } from 'lucide-react';

export default function App() {
  const [showControl, setShowControl] = useState(false);
  const [activeTab, setActiveTab] = useState('inspect');

  const { data: checkpoint, loading: latestLoading, error: latestError, refetch: refetchLatest } = useLatestStructureCheckpoint();
  const { data: checkpointsData, loading: checkpointsLoading, error: checkpointsError, refetch: refetchCheckpoints } = useStructureCheckpoints();
  const { data: bdhGraph, loading: graphLoading, error: graphError, refetch: refetchBdhGraph } = useStructureGraph('bdh');
  const { data: controlGraph, loading: controlGraphLoading, error: controlGraphError, refetch: refetchControlGraph } = useStructureGraph('transformer');
  const { data: comparison, loading: compLoading, error: compError, refetch: refetchComp } = useStructureComparison();
  const { data: continual, loading: continualLoading, error: continualError, refetch: refetchContinual } = useContinualLearning();
  const { data: reasoning, loading: reasoningLoading, error: reasoningError, refetch: refetchReasoning } = useReasoning();
  const { data: reasoningComp, loading: reasoningCompLoading, error: reasoningCompError, refetch: refetchReasoningComp } = useReasoningComparison();
  const { data: modelConfig, loading: configLoading, error: configError } = useModelConfig();

  const handleRefresh = async () => {
    await Promise.all([
      refetchLatest(),
      refetchCheckpoints(),
      refetchBdhGraph(),
      refetchControlGraph(),
      refetchComp(),
      refetchContinual(),
      refetchReasoning(),
      refetchReasoningComp()
    ]);
  };

  const handleExportData = () => {
    const dataToExport = {
      checkpoint,
      checkpoints: checkpointsData,
      bdhGraph,
      controlGraph,
      comparison,
      continual,
      reasoning,
      reasoningComp,
      modelConfig,
      exportedAt: new Date().toISOString()
    };
    
    const blob = new Blob([JSON.stringify(dataToExport, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `neurolens_metrics_${Date.now()}.json`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  return (
    <div className="min-h-screen bg-neurolens-bg text-neurolens-textPrimary flex flex-col font-sans">
      <TopNav modelConfig={modelConfig} onExport={handleExportData} />

      {/* Main Container */}
      <main className="flex-1 max-w-[1600px] mx-auto w-full px-4 sm:px-6 lg:px-8 py-6 flex flex-col gap-6">
        
        {/* Navigation Tabs & Refresh */}
        <div className="flex items-center justify-between border-b border-neurolens-border pb-2 flex-wrap gap-4">
          <div className="flex gap-2">
            <button
              onClick={() => setActiveTab('inspect')}
              className={`px-4 py-2 font-mono text-small transition-all ${
                activeTab === 'inspect'
                  ? 'border-b-2 border-white text-neurolens-textPrimary font-semibold'
                  : 'text-neurolens-textSecondary hover:text-neurolens-textPrimary'
              }`}
            >
              INSPECT VIEW (A)
            </button>
            <button
              onClick={() => setActiveTab('track')}
              className={`px-4 py-2 font-mono text-small transition-all ${
                activeTab === 'track'
                  ? 'border-b-2 border-white text-neurolens-textPrimary font-semibold'
                  : 'text-neurolens-textSecondary hover:text-neurolens-textPrimary'
              }`}
            >
              TRACK VIEW (B)
            </button>
            <button
              onClick={() => setActiveTab('test')}
              className={`px-4 py-2 font-mono text-small transition-all ${
                activeTab === 'test'
                  ? 'border-b-2 border-white text-neurolens-textPrimary font-semibold'
                  : 'text-neurolens-textSecondary hover:text-neurolens-textPrimary'
              }`}
            >
              TEST VIEW (C, D)
            </button>
            <button
              onClick={() => setActiveTab('connect')}
              className={`px-4 py-2 font-mono text-small transition-all ${
                activeTab === 'connect'
                  ? 'border-b-2 border-white text-neurolens-textPrimary font-semibold'
                  : 'text-neurolens-textSecondary hover:text-neurolens-textPrimary'
              }`}
            >
              CONNECT PANEL (E)
            </button>
          </div>

          <button
            onClick={handleRefresh}
            className="btn-secondary text-tiny py-1.5 px-3 flex items-center gap-1.5"
            title="Reload live results"
          >
            <RefreshCw className="w-3.5 h-3.5" />
            Reload Live Data
          </button>
        </div>

        {/* View Switcheable Main Content */}
        <div className="flex-1 flex flex-col gap-6">
          {activeTab === 'inspect' && (
            <div className="animate-fade-in">
              <PanelA_NetworkTopology
                structureData={checkpoint}
                graphData={showControl ? controlGraph : bdhGraph}
                modelConfig={modelConfig}
                showControl={showControl}
                onToggleControl={() => setShowControl(!showControl)}
              />
            </div>
          )}

          {activeTab === 'track' && (
            <div className="animate-fade-in">
              <PanelB_TrainingEvolution
                structureCheckpoints={checkpointsData}
              />
            </div>
          )}

          {activeTab === 'test' && (
            <div className="grid grid-cols-1 xl:grid-cols-2 gap-6 animate-fade-in">
              <PanelC_ReasoningBenchmark
                reasoningData={reasoning}
                reasoningComparison={reasoningComp}
              />
              <PanelD_ContinualLearning
                continualData={continual}
              />
            </div>
          )}

          {activeTab === 'connect' && (
            <div className="animate-fade-in">
              <PanelE_StructureBehavior
                structureData={checkpoint}
                continualData={continual}
              />
            </div>
          )}
        </div>
      </main>

      <BottomBanner />
    </div>
  );
}
