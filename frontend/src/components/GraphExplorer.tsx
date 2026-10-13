import React, { useState } from 'react';
import { Orbit, ExternalLink } from 'lucide-react';
import { ThreeUniverse } from './ThreeUniverse';
import { GraphData, GraphNode } from '../types';

interface GraphExplorerProps {
  graphData: GraphData | null;
  onRefreshGraph: () => void;
}

export const GraphExplorer: React.FC<GraphExplorerProps> = ({
  graphData,
  onRefreshGraph,
}) => {
  const [selectedNode, setSelectedNode] = useState<GraphNode | null>(null);

  return (
    <div className="relative w-full h-[calc(100vh-65px)] overflow-hidden bg-[#121924]">
      {/* 3D WebGL Canvas */}
      <ThreeUniverse
        graphData={graphData}
        selectedNodeId={selectedNode?.id}
        onSelectNode={(node) => setSelectedNode(node)}
        interactive={true}
      />

      {/* Top Left Title HUD */}
      <div className="absolute top-6 left-6 z-20 pointer-events-none">
        <div className="glass-panel p-4 rounded-2xl border border-[#9DB2BF]/30 max-w-sm pointer-events-auto shadow-2xl bg-[#27374D]/85 backdrop-blur-xl">
          <div className="flex items-center gap-2 mb-1">
            <Orbit className="w-5 h-5 text-[#9DB2BF]" />
            <h2 className="font-bold text-base text-white font-['Space_Grotesk']">
              3D Vector Knowledge Graph
            </h2>
          </div>
          <p className="text-xs text-[#9DB2BF] leading-relaxed">
            Visualizing semantic vector space. Document clusters anchor in outer orbit,
            while chunk nodes gravitate toward high cosine similarity.
          </p>

          {/* Stats Bar */}
          <div className="grid grid-cols-3 gap-2 mt-3 pt-3 border-t border-[#9DB2BF]/20 text-center font-mono">
            <div>
              <div className="text-sm font-bold text-[#9DB2BF]">
                {graphData?.stats.documents || 0}
              </div>
              <div className="text-[10px] text-[#526D82] uppercase font-semibold">Documents</div>
            </div>
            <div>
              <div className="text-sm font-bold text-[#526D82] brightness-150">
                {graphData?.stats.chunks || 0}
              </div>
              <div className="text-[10px] text-[#526D82] uppercase font-semibold">Chunks</div>
            </div>
            <div>
              <div className="text-sm font-bold text-[#DDE6ED]">
                {graphData?.stats.retrieved || 0}
              </div>
              <div className="text-[10px] text-[#526D82] uppercase font-semibold">Retrieved</div>
            </div>
          </div>
        </div>
      </div>

      {/* Selected Node Details Drawer */}
      {selectedNode && (
        <div className="absolute bottom-6 right-6 z-20 glass-panel-glow p-5 rounded-2xl border border-[#9DB2BF]/50 max-w-md w-full animate-fade-in shadow-2xl bg-[#27374D]/95 backdrop-blur-2xl">
          <div className="flex items-center justify-between pb-3 border-b border-[#9DB2BF]/20 mb-3">
            <div className="flex items-center gap-2">
              <span
                className="w-3 h-3 rounded-full"
                style={{ backgroundColor: selectedNode.color }}
              />
              <span className="font-bold text-sm text-white font-['Space_Grotesk'] uppercase tracking-wider">
                {selectedNode.type} Details
              </span>
            </div>
            <button
              onClick={() => setSelectedNode(null)}
              className="text-slate-300 hover:text-white text-xs font-mono px-2 py-0.5 rounded bg-[#526D82]/60 hover:bg-[#526D82] cursor-pointer"
            >
              ✕
            </button>
          </div>

          <h3 className="font-bold text-sm text-white mb-2">{selectedNode.name}</h3>

          {selectedNode.doc_title && (
            <div className="text-xs text-[#9DB2BF] mb-1">
              Parent Document: <b className="text-white">{selectedNode.doc_title}</b>
            </div>
          )}

          {selectedNode.section && (
            <div className="text-xs text-[#9DB2BF] mb-2">
              Section: <b className="text-[#DDE6ED]">{selectedNode.section}</b>
            </div>
          )}

          {selectedNode.preview && (
            <div className="bg-[#16202c]/90 p-3 rounded-xl border border-[#9DB2BF]/20 text-xs text-[#DDE6ED] italic mb-3 leading-relaxed max-h-36 overflow-y-auto">
              "{selectedNode.preview}"
            </div>
          )}

          <div className="flex items-center justify-between pt-2 border-t border-[#9DB2BF]/20 text-xs">
            <span className="font-mono text-[10px] text-[#526D82]">ID: {selectedNode.id}</span>
            {selectedNode.url && (
              <a
                href={selectedNode.url}
                target="_blank"
                rel="noreferrer"
                className="text-[#9DB2BF] hover:text-[#DDE6ED] flex items-center gap-1 font-semibold transition-colors"
              >
                <span>Read Full Article</span>
                <ExternalLink className="w-3.5 h-3.5" />
              </a>
            )}
          </div>
        </div>
      )}

      {/* Legend / Color Guide */}
      <div className="absolute bottom-6 left-6 z-20 glass-panel px-4 py-2.5 rounded-xl border border-[#9DB2BF]/20 text-[11px] flex items-center gap-4 text-[#DDE6ED] bg-[#27374D]/85 backdrop-blur-md shadow-xl">
        <div className="flex items-center gap-1.5">
          <span className="w-2.5 h-2.5 rounded-full bg-[#9DB2BF] shadow-[0_0_8px_#9DB2BF]"></span>
          <span>Document Cluster</span>
        </div>
        <div className="flex items-center gap-1.5">
          <span className="w-2.5 h-2.5 rounded-full bg-[#526D82] border border-[#9DB2BF]/40"></span>
          <span>Semantic Chunk</span>
        </div>
        <div className="flex items-center gap-1.5">
          <span className="w-2.5 h-2.5 rounded-full bg-[#DDE6ED] shadow-[0_0_8px_#DDE6ED]"></span>
          <span>Retrieved Evidence</span>
        </div>
        <div className="flex items-center gap-1.5">
          <span className="w-2.5 h-2.5 rounded-full bg-[#DDE6ED] ring-2 ring-[#9DB2BF]"></span>
          <span>Query Vector</span>
        </div>
      </div>
    </div>
  );
};
