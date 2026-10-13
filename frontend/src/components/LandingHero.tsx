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
    <div className="relative w-full min-h-[calc(100vh-65px)] flex flex-col justify-center overflow-hidden bg-[#121924]">
      {/* 3D Background Canvas (non-interactive, no controls) */}
      <div className="absolute inset-0 z-0 opacity-85">
        <ThreeUniverse graphData={graphData} interactive={false} />
      </div>

      {/* Hero Content Overlay */}
      <div className="relative z-10 max-w-7xl mx-auto px-6 py-16 flex flex-col items-center text-center">
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
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 w-full max-w-3xl glass-panel p-4 rounded-2xl border border-[#9DB2BF]/25 bg-[#27374D]/80">
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
      </div>
    </div>
  );
};
