import React from 'react';
import { ArrowRight, Orbit, Sparkles } from 'lucide-react';
import { ThreeUniverse } from './ThreeUniverse';
import { GraphData, SystemStatus } from '../types';

interface LandingHeroProps {
  onStartResearch: () => void;
  onExploreGraph: () => void;
  onLoadTopic: (topicName: string) => void;
  graphData: GraphData | null;
  status: SystemStatus | null;
  loadingTopic: string | null;
}

export const LandingHero: React.FC<LandingHeroProps> = ({
  onStartResearch,
  onExploreGraph,
  onLoadTopic,
  graphData,
  status,
  loadingTopic,
}) => {
  const topics = [
    {
      id: 'AI',
      title: 'AI & Machine Learning',
      desc: 'Neural networks, transformer models, deep learning foundational theorems.',
      icon: '🧠',
      count: '3 Articles',
    },
    {
      id: 'Science',
      title: 'Physics & Natural Science',
      desc: 'Quantum states, thermodynamics, and biological systems.',
      icon: '🔬',
      count: '3 Articles',
    },
    {
      id: 'Technology',
      title: 'Advanced Technology',
      desc: 'Cloud systems, quantum computing, and cryptography.',
      icon: '⚡',
      count: '3 Articles',
    },
    {
      id: 'Economics',
      title: 'Economics & Markets',
      desc: 'Monetary policy, macro dynamics, inflation, and fiscal structures.',
      icon: '📈',
      count: '3 Articles',
    },
    {
      id: 'History',
      title: 'History & Civilization',
      desc: 'Renaissance, industrial transformations, space exploration epochs.',
      icon: '🏛️',
      count: '3 Articles',
    },
  ];

  return (
    <div className="relative w-full min-h-[calc(100vh-65px)] flex flex-col justify-between overflow-hidden bg-[#121924]">
      {/* 3D Background Canvas */}
      <div className="absolute inset-0 z-0 opacity-85">
        <ThreeUniverse graphData={graphData} interactive={true} />
      </div>

      {/* Hero Content Overlay */}
      <div className="relative z-10 max-w-7xl mx-auto px-6 pt-16 pb-12 flex flex-col items-center text-center">
        {/* Pill Badge */}
        <div className="inline-flex items-center gap-2 px-3.5 py-1.5 rounded-full bg-[#27374D]/85 border border-[#9DB2BF]/40 text-[#DDE6ED] text-xs font-semibold mb-6 shadow-lg shadow-[#526D82]/20 backdrop-blur-md">
          <Sparkles className="w-3.5 h-3.5 text-[#DDE6ED]" />
          <span>SPATIAL VECTOR KNOWLEDGE ENGINE · RAG 2.0</span>
        </div>

        {/* Hero Title */}
        <h1 className="text-4xl sm:text-6xl md:text-7xl font-extrabold tracking-tight text-white font-['Space_Grotesk'] max-w-4xl leading-[1.1] mb-6">
          Turn Knowledge Into{' '}
          <span className="bg-gradient-to-r from-[#DDE6ED] via-[#9DB2BF] to-[#526D82] bg-clip-text text-transparent drop-shadow-sm">
            Answers.
          </span>
        </h1>

        {/* Subtitle */}
        <p className="text-base sm:text-xl text-[#9DB2BF] max-w-2xl font-light leading-relaxed mb-10">
          An intelligent retrieval-augmented research workspace that connects questions to evidence through a 3D semantic universe.
        </p>

        {/* Primary & Secondary Actions */}
        <div className="flex flex-wrap items-center justify-center gap-4 mb-16">
          <button
            onClick={onStartResearch}
            className="flex items-center gap-2.5 px-7 py-3.5 rounded-xl bg-[#DDE6ED] hover:bg-white text-[#121924] font-bold text-sm shadow-xl shadow-[#9DB2BF]/20 hover:shadow-[#DDE6ED]/30 hover:-translate-y-0.5 transition-all duration-300 cursor-pointer"
          >
            <span>Start Researching</span>
            <ArrowRight className="w-4 h-4 text-[#121924]" />
          </button>

          <button
            onClick={onExploreGraph}
            className="flex items-center gap-2.5 px-6 py-3.5 rounded-xl bg-[#27374D]/80 hover:bg-[#526D82] text-[#DDE6ED] hover:text-white border border-[#9DB2BF]/30 font-medium text-sm transition-all duration-300 backdrop-blur-md cursor-pointer"
          >
            <Orbit className="w-4 h-4 text-[#9DB2BF]" />
            <span>Explore Knowledge Graph</span>
          </button>
        </div>

        {/* System Stats Bar */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 w-full max-w-3xl glass-panel p-4 rounded-2xl border border-[#9DB2BF]/25 mb-14 bg-[#27374D]/80">
          <div className="flex flex-col items-center">
            <span className="text-2xl font-bold font-['Space_Grotesk'] text-[#DDE6ED]">
              {status?.documents_loaded || 0}
            </span>
            <span className="text-[11px] text-[#9DB2BF] uppercase tracking-wider mt-0.5">Documents Ingested</span>
          </div>
          <div className="flex flex-col items-center">
            <span className="text-2xl font-bold font-['Space_Grotesk'] text-[#9DB2BF]">
              {status?.total_chunks || 0}
            </span>
            <span className="text-[11px] text-[#9DB2BF] uppercase tracking-wider mt-0.5">Semantic Chunks</span>
          </div>
          <div className="flex flex-col items-center">
            <span className="text-2xl font-bold font-['Space_Grotesk'] text-[#DDE6ED]">384-D</span>
            <span className="text-[11px] text-[#9DB2BF] uppercase tracking-wider mt-0.5">MiniLM Vector Space</span>
          </div>
          <div className="flex flex-col items-center">
            <span className="text-2xl font-bold font-['Space_Grotesk'] text-[#9DB2BF]">6-Stage</span>
            <span className="text-[11px] text-[#9DB2BF] uppercase tracking-wider mt-0.5">Pipeline Grounding</span>
          </div>
        </div>

        {/* Quick Start Topics Section */}
        <div className="w-full max-w-5xl text-left">
          <div className="flex items-center justify-between mb-4">
            <div>
              <h3 className="text-lg font-bold text-white font-['Space_Grotesk'] flex items-center gap-2">
                <span>Quick Start Topic Clusters</span>
              </h3>
              <p className="text-xs text-[#9DB2BF]">
                Click any topic card to instantly ingest verified Wikipedia articles into 3D vector space
              </p>
            </div>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3.5">
            {topics.map((t) => {
              const isLoading = loadingTopic === t.id;
              return (
                <div
                  key={t.id}
                  onClick={() => !loadingTopic && onLoadTopic(t.id)}
                  className={`glass-card p-4 rounded-xl cursor-pointer group relative overflow-hidden transition-all duration-300 bg-[#27374D]/60 hover:bg-[#526D82]/50 border border-[#9DB2BF]/20 hover:border-[#DDE6ED]/50 ${
                    isLoading ? 'border-[#DDE6ED]/60 bg-[#27374D]/90' : ''
                  }`}
                >
                  <div className="flex items-start justify-between mb-2">
                    <span className="text-2xl p-2 rounded-lg bg-[#16202c]/70 border border-[#9DB2BF]/20">
                      {t.icon}
                    </span>
                    <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-[#16202c]/80 text-[#DDE6ED] border border-[#9DB2BF]/25 font-semibold">
                      {t.count}
                    </span>
                  </div>

                  <h4 className="font-bold text-sm text-white group-hover:text-[#DDE6ED] transition-colors">
                    {t.title}
                  </h4>
                  <p className="text-xs text-[#9DB2BF] mt-1 line-clamp-2 leading-relaxed">
                    {t.desc}
                  </p>

                  <div className="mt-3.5 flex items-center justify-between text-[11px] text-[#DDE6ED] font-semibold">
                    <span>{isLoading ? 'Ingesting into Vector Space...' : 'Explore Cluster'}</span>
                    <ArrowRight className={`w-3.5 h-3.5 group-hover:translate-x-1 transition-transform ${isLoading ? 'animate-pulse' : ''}`} />
                  </div>

                  {isLoading && (
                    <div className="absolute inset-0 bg-[#121924]/80 backdrop-blur-sm flex items-center justify-center gap-2">
                      <div className="w-4 h-4 border-2 border-[#DDE6ED] border-t-transparent rounded-full animate-spin" />
                      <span className="text-xs font-semibold text-[#DDE6ED]">Embedding...</span>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      </div>
    </div>
  );
};
