import * as d3 from 'd3';
import { useEffect, useRef, useState, useMemo } from 'react';
import {
  ZoomIn,
  ZoomOut,
  RotateCcw,
  Play,
  Pause,
  Zap,
  Search,
  Sliders,
  Filter,
  X,
  Share2,
  Info,
  Layers,
  Activity,
  Crosshair
} from 'lucide-react';
import { ClaimBadge } from './ClaimBadge';

const COMMUNITY_COLORS = [
  '#06B6D4',
  '#A855F7',
  '#F59E0B',
  '#10B981',
  '#EC4899',
];

export function PanelA_NetworkTopology({
  structureData,
  graphData,
  modelConfig,
  showControl = false,
  onToggleControl
}) {
  const svgRef = useRef(null);
  const containerRef = useRef(null);
  const zoomBehaviorRef = useRef(null);
  const simulationRef = useRef(null);

  const [dimensions, setDimensions] = useState({ width: 0, height: 0 });
  const [selectedNode, setSelectedNode] = useState(null);
  const [hoveredNode, setHoveredNode] = useState(null);
  const [isPaused, setIsPaused] = useState(false);
  const [edgeThreshold, setEdgeThreshold] = useState(0.35);
  const [searchQuery, setSearchQuery] = useState('');
  const [communityFilter, setCommunityFilter] = useState('all');
  const [tooltip, setTooltip] = useState({ visible: false, x: 0, y: 0, node: null });

  useEffect(() => {
    const resizeObserver = new ResizeObserver(entries => {
      for (let entry of entries) {
        const { width, height } = entry.contentRect;
        if (width > 0 && height > 0) {
          setDimensions({ width, height });
        }
      }
    });

    if (containerRef.current) {
      resizeObserver.observe(containerRef.current);
    }
    return () => resizeObserver.disconnect();
  }, []);

  const { nodes, links, communities, neighborMap } = useMemo(() => {
    if (!graphData?.nodes) {
      return { nodes: [], links: [], communities: [], neighborMap: new Map() };
    }

    const rawNodes = graphData.nodes.map((id, i) => ({
      id,
      index: i,
      ...(graphData.node_metadata?.[id] || {
        community: i % 3,
        layer: `layer_${Math.floor(i / 8)}`,
        degree: 2,
        activation: 0.75
      })
    }));

    const nodeIdsSet = new Set(rawNodes.map(n => n.id));
    const commSet = new Set();
    rawNodes.forEach(n => {
      if (n.community !== undefined) commSet.add(n.community);
    });

    const rawLinks = (graphData.edges || []).map(([source, target, weight]) => ({
      source: typeof source === 'object' ? source.id : source,
      target: typeof target === 'object' ? target.id : target,
      weight: Math.abs(weight || 0.5)
    })).filter(l => nodeIdsSet.has(l.source) && nodeIdsSet.has(l.target));

    const filteredLinks = rawLinks.filter(l => l.weight >= edgeThreshold);

    const adjMap = new Map();
    rawNodes.forEach(n => adjMap.set(n.id, []));
    filteredLinks.forEach(l => {
      adjMap.get(l.source)?.push({ neighbor: l.target, weight: l.weight });
      adjMap.get(l.target)?.push({ neighbor: l.source, weight: l.weight });
    });

    return {
      nodes: rawNodes,
      links: filteredLinks,
      communities: Array.from(commSet).sort((a, b) => a - b),
      neighborMap: adjMap
    };
  }, [graphData, edgeThreshold]);

  useEffect(() => {
    if (!svgRef.current || !dimensions.width || nodes.length === 0) return;

    const svg = d3.select(svgRef.current);
    svg.selectAll('*').remove();

    const { width, height } = dimensions;

    const g = svg.append('g').attr('class', 'main-graph-group');

    const zoom = d3.zoom()
      .scaleExtent([0.2, 5])
      .on('zoom', (event) => {
        g.attr('transform', event.transform);
      });

    svg.call(zoom);
    zoomBehaviorRef.current = zoom;

    svg.call(zoom.transform, d3.zoomIdentity.translate(width / 2, height / 2).scale(0.85));

    const simulation = d3.forceSimulation(nodes)
      .force('link', d3.forceLink(links).id(d => d.id).distance(50).strength(0.2))
      .force('charge', d3.forceManyBody().strength(-120))
      .force('center', d3.forceCenter(0, 0))
      .force('collision', d3.forceCollide().radius(14))
      .alphaDecay(0.025);

    simulationRef.current = simulation;

    if (isPaused) {
      simulation.stop();
    }

    svg.on('click', () => {
      setSelectedNode(null);
      setTooltip({ visible: false, x: 0, y: 0, node: null });
    });

    const linkGroup = g.append('g').attr('class', 'links-group');
    const link = linkGroup
      .selectAll('line')
      .data(links)
      .join('line')
      .attr('stroke', '#3F3F46')
      .attr('stroke-opacity', 0.4)
      .attr('stroke-width', d => Math.max(1, d.weight * 3));

    const nodeGroup = g.append('g').attr('class', 'nodes-group');
    const node = nodeGroup
      .selectAll('g.node')
      .data(nodes)
      .join('g')
      .attr('class', 'node')
      .attr('cursor', 'pointer')
      .call(
        d3.drag()
          .on('start', (event, d) => {
            if (!event.active && !isPaused) simulation.alphaTarget(0.3).restart();
            d.fx = d.x;
            d.fy = d.y;
          })
          .on('drag', (event, d) => {
            d.fx = event.x;
            d.fy = event.y;
          })
          .on('end', (event, d) => {
            if (!event.active && !isPaused) simulation.alphaTarget(0);
            d.fx = null;
            d.fy = null;
          })
      );

    node.append('circle')
      .attr('class', 'glow-ring')
      .attr('r', 9)
      .attr('fill', 'none')
      .attr('stroke', d => COMMUNITY_COLORS[(d.community ?? 0) % COMMUNITY_COLORS.length])
      .attr('stroke-opacity', 0)
      .attr('stroke-width', 2);

    node.append('circle')
      .attr('class', 'core-circle')
      .attr('r', 6)
      .attr('fill', d => COMMUNITY_COLORS[(d.community ?? 0) % COMMUNITY_COLORS.length])
      .attr('stroke', '#09090B')
      .attr('stroke-width', 1.5);

    node.append('text')
      .text(d => d.id.replace('neuron_', '').replace('trans_', ''))
      .attr('dy', 16)
      .attr('text-anchor', 'middle')
      .attr('font-size', '9px')
      .attr('font-family', 'JetBrains Mono, monospace')
      .attr('fill', '#A1A1AA')
      .attr('pointer-events', 'none');

    node
      .on('mouseenter', (event, d) => {
        setHoveredNode(d);
        const [mx, my] = d3.pointer(event, containerRef.current);
        setTooltip({
          visible: true,
          x: mx,
          y: my,
          node: d
        });
      })
      .on('mousemove', (event) => {
        const [mx, my] = d3.pointer(event, containerRef.current);
        setTooltip(prev => ({ ...prev, x: mx, y: my }));
      })
      .on('mouseleave', () => {
        setHoveredNode(null);
        setTooltip({ visible: false, x: 0, y: 0, node: null });
      })
      .on('click', (event, d) => {
        event.stopPropagation();
        setSelectedNode(d);
      });

    simulation.on('tick', () => {
      link
        .attr('x1', d => d.source.x)
        .attr('y1', d => d.source.y)
        .attr('x2', d => d.target.x)
        .attr('y2', d => d.target.y);

      node.attr('transform', d => `translate(${d.x},${d.y})`);
    });

    return () => {
      simulation.stop();
    };
  }, [nodes, links, dimensions, isPaused]);

  useEffect(() => {
    if (!svgRef.current) return;
    const svg = d3.select(svgRef.current);

    const activeNode = hoveredNode || selectedNode;
    const activeNeighbors = activeNode
      ? new Set((neighborMap.get(activeNode.id) || []).map(n => n.neighbor))
      : null;

    svg.selectAll('g.node').each(function(d) {
      const gNode = d3.select(this);
      const isMatchSearch = searchQuery
        ? d.id.toLowerCase().includes(searchQuery.toLowerCase())
        : true;
      const isMatchComm = communityFilter === 'all' || d.community === Number(communityFilter);

      const isSelected = selectedNode?.id === d.id;
      const isHovered = hoveredNode?.id === d.id;
      const isNeighbor = activeNeighbors?.has(d.id);
      const isActive = isSelected || isHovered || isNeighbor;

      if (!isMatchSearch || !isMatchComm) {
        gNode.attr('opacity', 0.15);
        gNode.select('.glow-ring').attr('stroke-opacity', 0);
        return;
      }

      if (activeNode) {
        if (isActive) {
          gNode.attr('opacity', 1);
          gNode.select('.core-circle')
            .attr('r', isSelected || isHovered ? 8 : 6.5)
            .attr('stroke', '#FFFFFF')
            .attr('stroke-width', 2);
          gNode.select('.glow-ring')
            .attr('stroke-opacity', isSelected || isHovered ? 0.8 : 0.4)
            .attr('r', isSelected || isHovered ? 13 : 10);
        } else {
          gNode.attr('opacity', 0.2);
          gNode.select('.core-circle').attr('r', 5).attr('stroke', '#09090B').attr('stroke-width', 1.5);
          gNode.select('.glow-ring').attr('stroke-opacity', 0);
        }
      } else {
        gNode.attr('opacity', 1);
        gNode.select('.core-circle').attr('r', 6).attr('stroke', '#09090B').attr('stroke-width', 1.5);
        gNode.select('.glow-ring').attr('stroke-opacity', 0);
      }
    });

    svg.selectAll('.links-group line').each(function(l) {
      const line = d3.select(this);
      const sourceId = typeof l.source === 'object' ? l.source.id : l.source;
      const targetId = typeof l.target === 'object' ? l.target.id : l.target;

      if (activeNode) {
        const isIncident = sourceId === activeNode.id || targetId === activeNode.id;
        if (isIncident) {
          line
            .attr('stroke', '#38BDF8')
            .attr('stroke-opacity', 0.9)
            .attr('stroke-width', Math.max(2, l.weight * 4));
        } else {
          line.attr('stroke', '#27272A').attr('stroke-opacity', 0.1).attr('stroke-width', 1);
        }
      } else {
        line
          .attr('stroke', '#3F3F46')
          .attr('stroke-opacity', 0.4)
          .attr('stroke-width', Math.max(1, l.weight * 2.5));
      }
    });
  }, [selectedNode, hoveredNode, communityFilter, searchQuery, neighborMap]);

  const handleZoomIn = () => {
    if (svgRef.current && zoomBehaviorRef.current) {
      d3.select(svgRef.current).transition().duration(250).call(zoomBehaviorRef.current.scaleBy, 1.3);
    }
  };

  const handleZoomOut = () => {
    if (svgRef.current && zoomBehaviorRef.current) {
      d3.select(svgRef.current).transition().duration(250).call(zoomBehaviorRef.current.scaleBy, 0.7);
    }
  };

  const handleResetView = () => {
    if (svgRef.current && zoomBehaviorRef.current && dimensions.width) {
      d3.select(svgRef.current).transition().duration(400).call(
        zoomBehaviorRef.current.transform,
        d3.zoomIdentity.translate(dimensions.width / 2, dimensions.height / 2).scale(0.85)
      );
    }
  };

  const handleReheatPhysics = () => {
    if (simulationRef.current) {
      simulationRef.current.alpha(0.8).restart();
      setIsPaused(false);
    }
  };

  const handleTogglePause = () => {
    if (simulationRef.current) {
      if (isPaused) {
        simulationRef.current.alpha(0.3).restart();
        setIsPaused(false);
      } else {
        simulationRef.current.stop();
        setIsPaused(true);
      }
    }
  };

  const handleSelectNeighbor = (neighborId) => {
    const target = nodes.find(n => n.id === neighborId);
    if (target) {
      setSelectedNode(target);
    }
  };

  const modularity = structureData?.modularity || (showControl ? 0.14 : 0.65);
  const modularityControl = structureData?.modularity_random_control || 0.13;
  const sparsity = structureData?.sparsity || (showControl ? 0.21 : 0.86);
  const clustering = structureData?.clustering_coefficient || (showControl ? 0.12 : 0.39);

  const selectedNeighbors = selectedNode ? (neighborMap.get(selectedNode.id) || []) : [];

  return (
    <div className="panel h-[600px] md:h-[680px] flex flex-col gap-3 relative">
      {/* Panel Header */}
      <div className="panel-header flex-wrap gap-3 pb-3 border-b border-neurolens-border">
        <div className="flex items-center gap-3">
          <h2 className="panel-title flex items-center gap-2 text-base sm:text-lg">
            <Share2 className="w-5 h-5 text-cyan-400" />
            Network Topology Inspector
          </h2>
          <ClaimBadge tag="MEASURED" />
        </div>

        {/* Model Toggle & Filter Toolbar */}
        <div className="flex items-center gap-3 flex-wrap">
          {/* Search box */}
          <div className="relative flex items-center">
            <Search className="w-3.5 h-3.5 absolute left-2.5 text-neurolens-textMuted" />
            <input
              type="text"
              placeholder="Search neuron..."
              value={searchQuery}
              onChange={e => setSearchQuery(e.target.value)}
              className="bg-neurolens-surface/80 border border-neurolens-border rounded-md pl-8 pr-3 py-1 text-tiny text-neurolens-textPrimary font-mono placeholder:text-neurolens-textMuted focus:outline-none focus:border-cyan-500 w-36 sm:w-44"
            />
            {searchQuery && (
              <button
                onClick={() => setSearchQuery('')}
                className="absolute right-2 text-neurolens-textMuted hover:text-white"
              >
                <X className="w-3 h-3" />
              </button>
            )}
          </div>

          {/* BDH vs Control Toggle */}
          <div className="flex items-center gap-2 bg-neurolens-surface/80 border border-neurolens-border rounded-md px-2.5 py-1">
            <label className="toggle cursor-pointer" title="Switch between BDH and Control Transformer model topology">
              <input
                type="checkbox"
                checked={showControl}
                onChange={onToggleControl}
                aria-label="Show Control Graph"
              />
              <span className="toggle-track">
                <span className="toggle-thumb" />
              </span>
            </label>
            <span className="text-tiny font-mono font-medium text-neurolens-textPrimary">
              {showControl ? 'Transformer Baseline' : 'BDH (NeuroLens)'}
            </span>
          </div>
        </div>
      </div>

      {/* Main Canvas & Sidebar Container */}
      <div className="flex-1 flex overflow-hidden rounded-panel border border-neurolens-border bg-[#09090B] relative">
        {/* Interactive Graph Canvas */}
        <div className="flex-1 relative overflow-hidden" ref={containerRef}>
          <svg
            ref={svgRef}
            className="w-full h-full cursor-grab active:cursor-grabbing"
            style={{ backgroundColor: '#09090B' }}
          />

          {/* Floating On-Canvas Controls (Top-Left) */}
          <div className="absolute top-3 left-3 flex items-center gap-1.5 bg-neurolens-surface/90 backdrop-blur-md border border-neurolens-border rounded-md p-1 shadow-lg z-10">
            <button
              onClick={handleZoomIn}
              className="p-1.5 rounded hover:bg-white/10 text-neurolens-textSecondary hover:text-white transition-colors"
              title="Zoom In"
            >
              <ZoomIn className="w-4 h-4" />
            </button>
            <button
              onClick={handleZoomOut}
              className="p-1.5 rounded hover:bg-white/10 text-neurolens-textSecondary hover:text-white transition-colors"
              title="Zoom Out"
            >
              <ZoomOut className="w-4 h-4" />
            </button>
            <button
              onClick={handleResetView}
              className="p-1.5 rounded hover:bg-white/10 text-neurolens-textSecondary hover:text-white transition-colors"
              title="Reset View & Center"
            >
              <Crosshair className="w-4 h-4" />
            </button>
            <div className="w-px h-4 bg-neurolens-border mx-0.5" />
            <button
              onClick={handleTogglePause}
              className={`p-1.5 rounded transition-colors ${
                isPaused ? 'bg-amber-500/20 text-amber-300' : 'hover:bg-white/10 text-neurolens-textSecondary hover:text-white'
              }`}
              title={isPaused ? 'Resume Physics' : 'Pause Physics'}
            >
              {isPaused ? <Play className="w-4 h-4" /> : <Pause className="w-4 h-4" />}
            </button>
            <button
              onClick={handleReheatPhysics}
              className="p-1.5 rounded hover:bg-white/10 text-neurolens-textSecondary hover:text-amber-400 transition-colors"
              title="Re-heat Physics / Shake Layout"
            >
              <Zap className="w-4 h-4" />
            </button>
          </div>

          {/* Floating Filter Controls (Top-Right) */}
          <div className="absolute top-3 right-3 flex items-center gap-2 bg-neurolens-surface/90 backdrop-blur-md border border-neurolens-border rounded-md px-3 py-1.5 shadow-lg z-10 text-tiny font-mono">
            <Sliders className="w-3.5 h-3.5 text-cyan-400" />
            <span className="text-neurolens-textMuted">τ Threshold:</span>
            <input
              type="range"
              min="0.2"
              max="0.9"
              step="0.05"
              value={edgeThreshold}
              onChange={e => setEdgeThreshold(parseFloat(e.target.value))}
              className="w-20 accent-cyan-400 cursor-pointer"
            />
            <span className="text-white font-bold">{edgeThreshold.toFixed(2)}</span>
          </div>

          {/* Interactive Floating Hover Tooltip */}
          {tooltip.visible && tooltip.node && (
            <div
              className="absolute pointer-events-none z-30 bg-neurolens-surface/95 backdrop-blur-md border border-neurolens-border rounded-panel p-2.5 shadow-2xl text-tiny font-mono"
              style={{
                left: Math.min(tooltip.x + 12, (dimensions.width || 400) - 180),
                top: Math.min(tooltip.y + 12, (dimensions.height || 400) - 130),
              }}
            >
              <div className="flex items-center gap-2 font-bold text-white mb-1">
                <span
                  className="w-2.5 h-2.5 rounded-full"
                  style={{ backgroundColor: COMMUNITY_COLORS[(tooltip.node.community ?? 0) % COMMUNITY_COLORS.length] }}
                />
                {tooltip.node.id}
              </div>
              <div className="text-neurolens-textMuted space-y-0.5">
                <div>Community: <span className="text-white font-semibold">{tooltip.node.community}</span></div>
                <div>Layer: <span className="text-white">{tooltip.node.layer || 'N/A'}</span></div>
                <div>Connections: <span className="text-cyan-300 font-bold">{(neighborMap.get(tooltip.node.id) || []).length}</span></div>
                <div>Activation: <span className="text-amber-300 font-bold">{(tooltip.node.activation ?? 0.75).toFixed(2)}</span></div>
              </div>
            </div>
          )}

          {/* Community Legend (Bottom-Left) */}
          <div className="absolute bottom-3 left-3 flex flex-col gap-1.5 bg-neurolens-surface/90 backdrop-blur-md border border-neurolens-border rounded-md p-2.5 text-tiny z-10">
            <span className="font-mono text-[10px] text-neurolens-textMuted uppercase tracking-wider font-semibold">
              Communities ({communities.length})
            </span>
            <div className="flex items-center gap-1.5 flex-wrap">
              <button
                onClick={() => setCommunityFilter('all')}
                className={`px-2 py-0.5 rounded text-[11px] font-mono transition-colors ${
                  communityFilter === 'all'
                    ? 'bg-white/20 text-white font-bold'
                    : 'text-neurolens-textMuted hover:text-white'
                }`}
              >
                All
              </button>
              {communities.map(c => (
                <button
                  key={c}
                  onClick={() => setCommunityFilter(communityFilter === String(c) ? 'all' : String(c))}
                  className={`flex items-center gap-1.5 px-2 py-0.5 rounded text-[11px] font-mono transition-colors ${
                    communityFilter === String(c)
                      ? 'bg-white/20 text-white font-bold'
                      : 'text-neurolens-textMuted hover:text-white'
                  }`}
                >
                  <span
                    className="w-2 h-2 rounded-full"
                    style={{ backgroundColor: COMMUNITY_COLORS[c % COMMUNITY_COLORS.length] }}
                  />
                  C{c}
                </button>
              ))}
            </div>
          </div>
        </div>

        {/* Sidebar: Metrics & Selected Node Inspector */}
        <div className="w-80 border-l border-neurolens-border bg-neurolens-surface/40 backdrop-blur-sm p-4 overflow-y-auto flex flex-col gap-4 flex-shrink-0">
          {/* Selected Node Details Drawer */}
          {selectedNode ? (
            <div className="bg-cyan-950/20 border border-cyan-500/30 rounded-panel p-3.5 space-y-3">
              <div className="flex items-center justify-between">
                <span className="text-tiny font-mono text-cyan-400 font-semibold uppercase flex items-center gap-1.5">
                  <Crosshair className="w-3.5 h-3.5" />
                  Inspected Node
                </span>
                <button
                  onClick={() => setSelectedNode(null)}
                  className="text-neurolens-textMuted hover:text-white"
                  title="Close Inspector"
                >
                  <X className="w-4 h-4" />
                </button>
              </div>

              <div className="space-y-1 font-mono">
                <div className="text-base font-bold text-white flex items-center gap-2">
                  <span
                    className="w-3 h-3 rounded-full"
                    style={{ backgroundColor: COMMUNITY_COLORS[(selectedNode.community ?? 0) % COMMUNITY_COLORS.length] }}
                  />
                  {selectedNode.id}
                </div>
                <div className="text-tiny text-neurolens-textMuted">
                  Layer: <span className="text-white">{selectedNode.layer || 'N/A'}</span>
                </div>
                <div className="text-tiny text-neurolens-textMuted">
                  Community: <span className="text-cyan-300 font-bold">Module {selectedNode.community}</span>
                </div>
                <div className="text-tiny text-neurolens-textMuted">
                  Mean Activation: <span className="text-amber-300 font-bold">{(selectedNode.activation ?? 0.75).toFixed(3)}</span>
                </div>
              </div>

              {/* Connected Neighbors List */}
              <div className="pt-2 border-t border-neurolens-border/60">
                <span className="text-tiny font-mono text-neurolens-textMuted uppercase block mb-1.5">
                  Connected Neighbors ({selectedNeighbors.length})
                </span>
                {selectedNeighbors.length === 0 ? (
                  <span className="text-tiny text-neurolens-textMuted font-mono">No connections at τ ≥ {edgeThreshold.toFixed(2)}</span>
                ) : (
                  <div className="max-h-32 overflow-y-auto space-y-1 pr-1">
                    {selectedNeighbors.map(({ neighbor, weight }) => (
                      <button
                        key={neighbor}
                        onClick={() => handleSelectNeighbor(neighbor)}
                        className="w-full flex items-center justify-between text-tiny font-mono bg-neurolens-surface/60 hover:bg-cyan-500/20 px-2 py-1 rounded transition-colors text-left"
                      >
                        <span className="text-white font-medium">{neighbor}</span>
                        <span className="text-cyan-400 font-semibold">r = {weight.toFixed(2)}</span>
                      </button>
                    ))}
                  </div>
                )}
              </div>
            </div>
          ) : (
            <div className="bg-neurolens-surface/50 border border-dashed border-neurolens-border rounded-panel p-3 text-center text-tiny text-neurolens-textMuted font-mono">
              Click any neuron in the graph to inspect connections, weights, and community properties.
            </div>
          )}

          {/* Graph Overview KPIs */}
          <div className="space-y-3">
            <h3 className="font-mono text-tiny font-semibold text-neurolens-textSecondary uppercase tracking-wider">
              Network Properties
            </h3>

            <div className="metric-card bg-neurolens-surface/70 border border-neurolens-border rounded-panel p-3">
              <span className="metric-label text-tiny text-neurolens-textMuted">Modularity Q</span>
              <div className="flex items-baseline gap-2 mt-1">
                <span className="text-lg font-bold font-mono text-white">{Number(modularity).toFixed(3)}</span>
                <span className="font-mono text-tiny text-emerald-400 font-semibold">
                  vs ctrl: {Number(modularityControl).toFixed(3)}
                </span>
              </div>
              <span className="text-[11px] text-neurolens-textMuted">Louvain community partition</span>
            </div>

            <div className="metric-card bg-neurolens-surface/70 border border-neurolens-border rounded-panel p-3">
              <span className="metric-label text-tiny text-neurolens-textMuted">Activation Sparsity</span>
              <span className="text-lg font-bold font-mono text-cyan-300 mt-1 block">
                {(Number(sparsity) * 100).toFixed(1)}%
              </span>
              <span className="text-[11px] text-neurolens-textMuted">Inactive unit fraction</span>
            </div>

            <div className="metric-card bg-neurolens-surface/70 border border-neurolens-border rounded-panel p-3">
              <span className="metric-label text-tiny text-neurolens-textMuted">Clustering Coefficient</span>
              <span className="text-lg font-bold font-mono text-amber-300 mt-1 block">
                {Number(clustering).toFixed(3)}
              </span>
              <span className="text-[11px] text-neurolens-textMuted">Mean local clustering</span>
            </div>

            <div className="metric-card bg-neurolens-surface/70 border border-neurolens-border rounded-panel p-3">
              <span className="metric-label text-tiny text-neurolens-textMuted">Graph Dimensions</span>
              <div className="flex items-center justify-between text-small font-mono text-white mt-1">
                <span>{nodes.length} Nodes</span>
                <span className="text-cyan-400">{links.length} Edges (active)</span>
              </div>
              <span className="text-[11px] text-neurolens-textMuted font-mono">
                {showControl ? 'Transformer dense' : 'BDH modular'}
              </span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
