import React from 'react';
import { Sparkles, Orbit, BookOpen, Settings as SettingsIcon, Database, Cpu } from 'lucide-react';
import { SystemStatus } from '../types';

interface NavbarProps {
  activeTab: 'overview' | 'workspace' | 'graph';
  setActiveTab: (tab: 'overview' | 'workspace' | 'graph') => void;
  status: SystemStatus | null;
  onOpenSettings: () => void;
}

export const Navbar: React.FC<NavbarProps> = ({
  activeTab,
  setActiveTab,
  status,
  onOpenSettings,
}) => {
  return (
    <header className="sticky top-0 z-40 w-full glass-panel border-b border-[#9DB2BF]/20 px-6 py-3.5 backdrop-blur-xl bg-[#27374D]/80">
      <div className="max-w-7xl mx-auto flex items-center justify-between">
        {/* Brand */}
        <div
          onClick={() => setActiveTab('overview')}
          className="flex items-center gap-3 cursor-pointer group"
        >
          <div className="w-10 h-10 rounded-xl bg-gradient-to-tr from-[#27374D] via-[#526D82] to-[#DDE6ED] flex items-center justify-center p-0.5 shadow-lg shadow-[#526D82]/20 group-hover:shadow-[#DDE6ED]/30 transition-all duration-300">
            <div className="w-full h-full bg-[#121924] rounded-[10px] flex items-center justify-center">
              <Orbit className="w-5 h-5 text-[#9DB2BF] group-hover:text-[#DDE6ED] group-hover:rotate-180 transition-all duration-700" />
            </div>
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className="font-bold text-base tracking-tight text-white font-['Space_Grotesk']">
                COGNITIVE RAG
              </span>
              <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-[#526D82]/30 text-[#DDE6ED] border border-[#9DB2BF]/30 font-semibold">
                3D UNIVERSE
              </span>
            </div>
            <div className="text-[11px] text-[#9DB2BF] flex items-center gap-1.5">
              <span>Retrieval-Augmented Intelligence</span>
            </div>
          </div>
        </div>

        {/* Navigation Tabs */}
        <nav className="hidden md:flex items-center gap-1 bg-[#27374D]/70 p-1 rounded-xl border border-[#9DB2BF]/20">
          <button
            onClick={() => setActiveTab('overview')}
            className={`flex items-center gap-2 px-4 py-1.5 rounded-lg text-xs font-medium transition-all cursor-pointer ${
              activeTab === 'overview'
                ? 'bg-[#526D82]/60 text-white border border-[#9DB2BF]/40 shadow-sm font-semibold'
                : 'text-[#9DB2BF] hover:text-[#DDE6ED] hover:bg-white/5'
            }`}
          >
            <Sparkles className="w-3.5 h-3.5 text-[#DDE6ED]" />
            <span>Overview</span>
          </button>

          <button
            onClick={() => setActiveTab('workspace')}
            className={`flex items-center gap-2 px-4 py-1.5 rounded-lg text-xs font-medium transition-all cursor-pointer ${
              activeTab === 'workspace'
                ? 'bg-[#526D82]/60 text-white border border-[#9DB2BF]/40 shadow-sm font-semibold'
                : 'text-[#9DB2BF] hover:text-[#DDE6ED] hover:bg-white/5'
            }`}
          >
            <BookOpen className="w-3.5 h-3.5" />
            <span>Research Workspace</span>
          </button>

          <button
            onClick={() => setActiveTab('graph')}
            className={`flex items-center gap-2 px-4 py-1.5 rounded-lg text-xs font-medium transition-all cursor-pointer ${
              activeTab === 'graph'
                ? 'bg-[#526D82]/60 text-white border border-[#9DB2BF]/40 shadow-sm font-semibold'
                : 'text-[#9DB2BF] hover:text-[#DDE6ED] hover:bg-white/5'
            }`}
          >
            <Orbit className="w-3.5 h-3.5" />
            <span>Knowledge Graph</span>
          </button>
        </nav>

        {/* Right Status & Settings */}
        <div className="flex items-center gap-3">
          {/* Status Badge */}
          <div className="hidden sm:flex items-center gap-2.5 px-3 py-1.5 rounded-xl bg-[#27374D]/90 border border-[#9DB2BF]/20 text-xs">
            <span
              className={`w-2 h-2 rounded-full ${
                status?.has_api_key ? 'bg-emerald-400 shadow-[0_0_8px_#10b981]' : 'bg-[#DDE6ED] shadow-[0_0_8px_#DDE6ED]'
              }`}
            />
            <div className="flex items-center gap-1.5 text-[#DDE6ED] text-[11px]">
              <Cpu className="w-3 h-3 text-[#9DB2BF]" />
              <span>{status?.device?.toUpperCase() || 'CPU'}</span>
              <span className="text-[#526D82]">·</span>
              <Database className="w-3 h-3 text-[#DDE6ED]" />
              <span>{status?.documents_loaded || 0} Docs ({status?.total_chunks || 0} Chunks)</span>
            </div>
          </div>

          {/* Settings Button */}
          <button
            onClick={onOpenSettings}
            className="p-2 rounded-xl bg-[#27374D]/80 hover:bg-[#526D82] text-[#9DB2BF] hover:text-[#DDE6ED] border border-[#9DB2BF]/20 hover:border-[#DDE6ED]/40 transition-all cursor-pointer shadow-sm active:scale-95"
            title="Open RAG Configuration"
          >
            <SettingsIcon className="w-4 h-4" />
          </button>
        </div>
      </div>
    </header>
  );
};
