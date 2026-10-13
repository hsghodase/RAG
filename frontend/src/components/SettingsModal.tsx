import React, { useState, useEffect } from 'react';
import { SlidersHorizontal, Key, Check, AlertCircle, Cpu, Layers, Activity, RefreshCw } from 'lucide-react';
import { AppConfig, ConnectionTestResult } from '../types';
import { api } from '../services/api';

interface SettingsModalProps {
  isOpen: boolean;
  onClose: () => void;
  config: AppConfig | null;
  onSave: (updated: Partial<AppConfig> & { gemini_api_key?: string }) => Promise<void>;
}

export const SettingsModal: React.FC<SettingsModalProps> = ({
  isOpen,
  onClose,
  config,
  onSave,
}) => {
  const [apiKey, setApiKey] = useState('');
  const [model, setModel] = useState('gemini-3.5-flash');
  const [temperature, setTemperature] = useState(0.3);
  const [topK, setTopK] = useState(5);
  const [threshold, setThreshold] = useState(0.20);
  const [chunkSize, setChunkSize] = useState(500);
  const [chunkOverlap, setChunkOverlap] = useState(75);
  const [tokenBudget, setTokenBudget] = useState(3000);
  
  const [isSaving, setIsSaving] = useState(false);
  const [saveSuccess, setSaveSuccess] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  // Connectivity Test State
  const [isTestingConn, setIsTestingConn] = useState(false);
  const [connResult, setConnResult] = useState<ConnectionTestResult | null>(null);

  useEffect(() => {
    if (config) {
      setModel(config.llm_model || 'gemini-3.5-flash');
      setTemperature(config.temperature ?? 0.3);
      setTopK(config.top_k ?? 5);
      setThreshold(config.similarity_threshold ?? 0.20);
      setChunkSize(config.chunk_size ?? 500);
      setChunkOverlap(config.chunk_overlap ?? 75);
      setTokenBudget(config.context_token_budget ?? 3000);
    }
  }, [config, isOpen]);

  if (!isOpen) return null;

  const handleTestConnection = async () => {
    setIsTestingConn(true);
    setConnResult(null);
    try {
      // If user typed a new key without saving, temporarily update config
      if (apiKey.trim()) {
        await api.updateConfig({ gemini_api_key: apiKey.trim(), llm_model: model });
      }
      const res = await api.testConnection();
      setConnResult(res);
    } catch (err: any) {
      setConnResult({
        success: false,
        message: err.message || 'Connection test failed',
        info: { status: 'error' }
      });
    } finally {
      setIsTestingConn(false);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsSaving(true);
    setErrorMsg(null);
    setSaveSuccess(false);

    try {
      const payload: Partial<AppConfig> & { gemini_api_key?: string } = {
        llm_model: model,
        temperature,
        top_k: topK,
        similarity_threshold: threshold,
        chunk_size: chunkSize,
        chunk_overlap: chunkOverlap,
        context_token_budget: tokenBudget,
      };
      if (apiKey.trim()) {
        payload.gemini_api_key = apiKey.trim();
      }

      await onSave(payload);
      setSaveSuccess(true);
      setTimeout(() => {
        setSaveSuccess(false);
        onClose();
      }, 1200);
    } catch (err: any) {
      setErrorMsg(err.message || 'Failed to update settings');
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 bg-black/80 backdrop-blur-md flex items-center justify-center p-4 animate-fade-in">
      <div className="glass-panel-glow w-full max-w-xl rounded-2xl border border-[#9DB2BF]/40 p-6 flex flex-col shadow-2xl bg-[#27374D]/95 backdrop-blur-2xl max-h-[90vh] overflow-y-auto">
        <div className="flex items-center justify-between pb-4 border-b border-[#9DB2BF]/20 mb-5">
          <div className="flex items-center gap-2">
            <SlidersHorizontal className="w-5 h-5 text-[#38bdf8]" />
            <h3 className="font-bold text-base text-white font-['Space_Grotesk']">
              Engine & Retrieval Settings
            </h3>
          </div>
          <button
            onClick={onClose}
            className="text-[#9DB2BF] hover:text-white text-xs font-mono px-2.5 py-1 rounded bg-[#1e293b] cursor-pointer"
          >
            ✕
          </button>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          {/* Gemini API Key */}
          <div className="bg-[#121924]/60 p-3.5 rounded-xl border border-[#9DB2BF]/20 space-y-2">
            <div className="flex items-center justify-between">
              <label className="text-xs font-semibold text-[#DDE6ED] flex items-center gap-1.5">
                <Key className="w-3.5 h-3.5 text-[#38bdf8]" />
                <span>Google Gemini API Key:</span>
              </label>
              <button
                type="button"
                onClick={handleTestConnection}
                disabled={isTestingConn}
                className="text-xs px-2.5 py-1 rounded-md bg-[#0284c7]/20 hover:bg-[#0284c7]/40 text-[#38bdf8] border border-[#0284c7]/40 font-medium transition-all flex items-center gap-1.5 cursor-pointer disabled:opacity-50"
              >
                {isTestingConn ? <RefreshCw className="w-3 h-3 animate-spin" /> : <Activity className="w-3 h-3" />}
                <span>Test Connection</span>
              </button>
            </div>
            <input
              type="password"
              placeholder={config?.api_key_masked ? `Masked: ${config.api_key_masked}` : 'AIzaSy...'}
              value={apiKey}
              onChange={(e) => setApiKey(e.target.value)}
              className="w-full bg-[#16202c] border border-[#9DB2BF]/30 rounded-lg px-3 py-2 text-xs text-white placeholder-slate-400 focus:outline-none focus:border-[#38bdf8]"
            />
            {connResult && (
              <div className={`text-xs p-2 rounded-lg border flex items-center justify-between ${
                connResult.success
                  ? 'bg-emerald-950/60 border-emerald-500/40 text-emerald-300'
                  : 'bg-rose-950/60 border-rose-500/40 text-rose-300'
              }`}>
                <span>{connResult.message}</span>
                {connResult.info?.latency_ms && (
                  <span className="font-mono text-[10px] bg-emerald-900/60 px-2 py-0.5 rounded font-bold">
                    {connResult.info.latency_ms} ms
                  </span>
                )}
              </div>
            )}
          </div>

          {/* Model Selection */}
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="text-xs font-semibold text-[#DDE6ED] block mb-1.5">
                LLM Synthesis Model:
              </label>
              <select
                value={model}
                onChange={(e) => setModel(e.target.value)}
                className="w-full bg-[#16202c] border border-[#9DB2BF]/30 rounded-lg px-3 py-2 text-xs text-white focus:outline-none focus:border-[#38bdf8] cursor-pointer"
              >
                <option value="gemini-3.5-flash">gemini-3.5-flash (Fast & Recommended)</option>
                <option value="gemini-3.1-flash-lite">gemini-3.1-flash-lite (High Reliability)</option>
                <option value="gemini-3.8-flash">gemini-3.8-flash (Extended Capabilities)</option>
              </select>
            </div>
            <div>
              <label className="text-xs font-semibold text-[#DDE6ED] block mb-1.5">
                Temperature: <span className="text-[#38bdf8] font-mono">{temperature}</span>
              </label>
              <input
                type="range"
                min="0.0"
                max="1.0"
                step="0.05"
                value={temperature}
                onChange={(e) => setTemperature(parseFloat(e.target.value))}
                className="w-full h-2 bg-[#16202c] rounded-lg appearance-none cursor-pointer accent-[#38bdf8] mt-2.5"
              />
            </div>
          </div>

          {/* Retrieval Parameters */}
          <div className="bg-[#121924]/60 p-3.5 rounded-xl border border-[#9DB2BF]/20 space-y-3">
            <div className="text-xs font-semibold text-white flex items-center gap-1.5">
              <Layers className="w-3.5 h-3.5 text-[#38bdf8]" />
              <span>Retrieval & Chunking Configuration</span>
            </div>
            <div className="grid grid-cols-3 gap-3">
              <div>
                <label className="text-[11px] text-[#9DB2BF] block mb-1">Top-K Passages:</label>
                <input
                  type="number"
                  min="1"
                  max="20"
                  value={topK}
                  onChange={(e) => setTopK(parseInt(e.target.value) || 5)}
                  className="w-full bg-[#16202c] border border-[#9DB2BF]/30 rounded-lg px-2.5 py-1.5 text-xs text-white focus:outline-none focus:border-[#38bdf8]"
                />
              </div>
              <div>
                <label className="text-[11px] text-[#9DB2BF] block mb-1">Similarity Threshold:</label>
                <input
                  type="number"
                  min="0.0"
                  max="1.0"
                  step="0.05"
                  value={threshold}
                  onChange={(e) => setThreshold(parseFloat(e.target.value) || 0.2)}
                  className="w-full bg-[#16202c] border border-[#9DB2BF]/30 rounded-lg px-2.5 py-1.5 text-xs text-white focus:outline-none focus:border-[#38bdf8]"
                />
              </div>
              <div>
                <label className="text-[11px] text-[#9DB2BF] block mb-1">Token Budget:</label>
                <input
                  type="number"
                  min="500"
                  max="8000"
                  step="500"
                  value={tokenBudget}
                  onChange={(e) => setTokenBudget(parseInt(e.target.value) || 3000)}
                  className="w-full bg-[#16202c] border border-[#9DB2BF]/30 rounded-lg px-2.5 py-1.5 text-xs text-white focus:outline-none focus:border-[#38bdf8]"
                />
              </div>
            </div>
            <div className="grid grid-cols-2 gap-3 pt-1">
              <div>
                <label className="text-[11px] text-[#9DB2BF] block mb-1">Chunk Size (Tokens):</label>
                <input
                  type="number"
                  min="128"
                  max="2048"
                  step="64"
                  value={chunkSize}
                  onChange={(e) => setChunkSize(parseInt(e.target.value) || 500)}
                  className="w-full bg-[#16202c] border border-[#9DB2BF]/30 rounded-lg px-2.5 py-1.5 text-xs text-white focus:outline-none focus:border-[#38bdf8]"
                />
              </div>
              <div>
                <label className="text-[11px] text-[#9DB2BF] block mb-1">Chunk Overlap (Tokens):</label>
                <input
                  type="number"
                  min="0"
                  max="256"
                  step="16"
                  value={chunkOverlap}
                  onChange={(e) => setChunkOverlap(parseInt(e.target.value) || 75)}
                  className="w-full bg-[#16202c] border border-[#9DB2BF]/30 rounded-lg px-2.5 py-1.5 text-xs text-white focus:outline-none focus:border-[#38bdf8]"
                />
              </div>
            </div>
          </div>

          {/* Embedding & Hardware Diagnostics */}
          <div className="p-3 bg-[#121924]/80 rounded-xl border border-[#9DB2BF]/20 flex items-center justify-between text-xs">
            <div className="flex items-center gap-2">
              <Cpu className="w-4 h-4 text-[#38bdf8]" />
              <div>
                <div className="font-semibold text-white">Embedding Space</div>
                <div className="text-[#9DB2BF] text-[11px] font-mono">
                  {config?.embedding_model || 'sentence-transformers/paraphrase-MiniLM-L3-v2'}
                </div>
              </div>
            </div>
            <span className="text-[10px] font-mono font-bold px-2 py-0.5 rounded bg-emerald-950 text-emerald-400 border border-emerald-500/30 uppercase">
              {config?.device || 'CPU'} ACTIVE
            </span>
          </div>

          {errorMsg && (
            <div className="p-2.5 bg-rose-950/80 border border-rose-500/40 rounded-lg text-rose-300 text-xs flex items-center gap-2">
              <AlertCircle className="w-4 h-4 shrink-0" />
              <span>{errorMsg}</span>
            </div>
          )}

          {saveSuccess && (
            <div className="p-2.5 bg-emerald-950/80 border border-emerald-500/40 rounded-lg text-emerald-300 text-xs flex items-center gap-2">
              <Check className="w-4 h-4 shrink-0" />
              <span>Settings applied successfully!</span>
            </div>
          )}

          {/* Actions */}
          <div className="flex items-center justify-end gap-2 pt-2 border-t border-[#9DB2BF]/20">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 rounded-lg bg-[#1e293b] hover:bg-[#334155] text-slate-300 text-xs font-medium cursor-pointer transition-all"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={isSaving}
              className="px-5 py-2 rounded-lg bg-[#38bdf8] hover:bg-sky-300 text-[#090d16] text-xs font-bold transition-all shadow-md flex items-center gap-1.5 cursor-pointer disabled:opacity-50"
            >
              {isSaving ? <RefreshCw className="w-3.5 h-3.5 animate-spin" /> : <Check className="w-3.5 h-3.5" />}
              <span>Save & Apply Settings</span>
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};
