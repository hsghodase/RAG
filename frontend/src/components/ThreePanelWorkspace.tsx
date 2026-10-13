import React, { useState, useEffect, useRef } from 'react';
import {
  Search, Plus, BookOpen, ExternalLink, Sparkles,
  Copy, Check, RefreshCw, Trash2,
  AlertCircle, FileText, CheckCircle2, History, X, RotateCcw,
  CheckSquare, Square, Filter, ChevronDown, ChevronUp, Clock, Info, ShieldCheck, MoreVertical
} from 'lucide-react';
import {
  DocumentMeta, ArticleHistoryItem, RetrievedEvidence, PipelineStage,
  ChatMessage, BackgroundTask
} from '../types';

interface ThreePanelWorkspaceProps {
  documents: DocumentMeta[];
  articleHistory?: ArticleHistoryItem[];
  chatHistory: ChatMessage[];
  currentEvidences: RetrievedEvidence[];
  currentStages: PipelineStage[] | null;
  isQuerying: boolean;
  onSendQuery: (query: string, articleFilter?: string[]) => void;
  onLoadCustomArticles: (articles: string[]) => Promise<void>;
  onReloadArticles: (articles: string[], mode: string) => Promise<void>;
  onRemoveArticle?: (title: string, deleteFromHistory?: boolean) => Promise<void>;
  onClearChat: () => void;
  onClearCache: () => void;
  selectedEvidenceId: string | null;
  setSelectedEvidenceId: (id: string | null) => void;
  onOpenSettings: () => void;
  activeTask?: BackgroundTask | null;
}

export const ThreePanelWorkspace: React.FC<ThreePanelWorkspaceProps> = ({
  documents,
  articleHistory = [],
  chatHistory,
  currentEvidences,
  currentStages,
  isQuerying,
  onSendQuery,
  onLoadCustomArticles,
  onReloadArticles,
  onRemoveArticle,
  onClearChat,
  selectedEvidenceId,
  setSelectedEvidenceId,
  onOpenSettings,
  activeTask
}) => {
  const [knowledgeTab, setKnowledgeTab] = useState<'active' | 'history'>('active');
  const [articleSearchQuery, setArticleSearchQuery] = useState('');
  const [selectedArticles, setSelectedArticles] = useState<Set<string>>(new Set());
  const [showAdvancedMenu, setShowAdvancedMenu] = useState(false);
  const [reactivatingTitle, setReactivatingTitle] = useState<string | null>(null);
  
  const [inputQuery, setInputQuery] = useState('');
  const [isIngesting, setIsIngesting] = useState(false);
  const [actionLoadingTitle, setActionLoadingTitle] = useState<string | null>(null);
  const [ingestSuccess, setIngestSuccess] = useState<string | null>(null);
  const [ingestError, setIngestError] = useState<string | null>(null);
  const [copiedMsgId, setCopiedMsgId] = useState<string | null>(null);
  const [inspectModalEvidence, setInspectModalEvidence] = useState<RetrievedEvidence | null>(null);
  const [expandedCards, setExpandedCards] = useState<Set<string>>(new Set());

  const searchInputRef = useRef<HTMLInputElement>(null);
  const chatBottomRef = useRef<HTMLDivElement>(null);

  // Auto-scroll chat on updates
  useEffect(() => {
    chatBottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [chatHistory, isQuerying]);

  // Filtered articles list based on search query
  const filteredDocuments = documents.filter((doc) =>
    doc.title.toLowerCase().includes(articleSearchQuery.toLowerCase())
  );

  // Filter history to only show inactive articles (not currently active)
  const activeSet = new Set(documents.map((d) => d.title.toLowerCase().trim()));
  const filteredHistory = articleHistory
    .filter((item) => !activeSet.has(item.title.toLowerCase().trim()))
    .filter((item) =>
      item.title.toLowerCase().includes(articleSearchQuery.toLowerCase())
    );

  // Toggle selection for a single article
  const toggleArticleSelect = (title: string) => {
    const next = new Set(selectedArticles);
    if (next.has(title)) {
      next.delete(title);
    } else {
      next.add(title);
    }
    setSelectedArticles(next);
  };

  // Bulk selection actions
  const selectAllArticles = () => {
    const all = new Set(documents.map((d) => d.title));
    setSelectedArticles(all);
  };

  const deselectAllArticles = () => {
    setSelectedArticles(new Set());
  };

  const selectActiveArticles = () => {
    const active = new Set(documents.filter((d) => d.is_active !== false).map((d) => d.title));
    setSelectedArticles(active);
  };

  const selectFailedArticles = () => {
    const failed = new Set(
      documents.filter((d) => d.status === 'failed' || d.status === 'stale').map((d) => d.title)
    );
    setSelectedArticles(failed);
  };

  // Safe reload execution
  const handleTriggerReload = async (mode: string) => {
    let targets: string[] = [];
    if (mode === 'reload_all') {
      if (!window.confirm('Reload all articles in the knowledge base? This will re-verify all documents.')) {
        return;
      }
      targets = documents.map((d) => d.title);
    } else if (selectedArticles.size > 0) {
      targets = Array.from(selectedArticles);
    } else {
      targets = documents.map((d) => d.title);
    }

    if (targets.length === 0) return;

    try {
      await onReloadArticles(targets, mode);
      setIngestSuccess(`Operation '${mode.replace('_', ' ')}' initiated for ${targets.length} article(s).`);
      setTimeout(() => setIngestSuccess(null), 4000);
    } catch (err: any) {
      setIngestError(err.message || 'Operation failed');
    }
  };

  const handleSubmitQuery = (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    if (!inputQuery.trim() || isQuerying) return;
    const activeFilter = selectedArticles.size > 0 ? Array.from(selectedArticles) : undefined;
    onSendQuery(inputQuery.trim(), activeFilter);
    setInputQuery('');
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmitQuery();
    }
  };

  const handleExamplePrompt = (prompt: string) => {
    setInputQuery(prompt);
  };

  const handleIngest = async (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    if (!articleSearchQuery.trim() || isIngesting) return;
    setIsIngesting(true);
    setIngestError(null);
    setIngestSuccess(null);
    try {
      const parsed = articleSearchQuery.split(',').map((s) => s.trim()).filter(Boolean);
      await onLoadCustomArticles(parsed);
      setArticleSearchQuery('');
      setIngestSuccess(`Added ${parsed.length} article(s)!`);
      setTimeout(() => setIngestSuccess(null), 3500);
    } catch (err: any) {
      setIngestError(err.message || 'Failed to ingest articles');
    } finally {
      setIsIngesting(false);
    }
  };

  const handleReactivate = async (title: string) => {
    setReactivatingTitle(title);
    setIngestError(null);
    setIngestSuccess(null);
    try {
      await onLoadCustomArticles([title]);
      setIngestSuccess(`'${title}' re-activated!`);
      setTimeout(() => setIngestSuccess(null), 3500);
    } catch (err: any) {
      setIngestError(err.message || `Failed to re-activate '${title}'`);
    } finally {
      setReactivatingTitle(null);
    }
  };

  const handleCopyText = (text: string, msgId: string) => {
    navigator.clipboard.writeText(text);
    setCopiedMsgId(msgId);
    setTimeout(() => setCopiedMsgId(null), 2000);
  };

  const toggleCardExpand = (refId: string) => {
    const next = new Set(expandedCards);
    if (next.has(refId)) {
      next.delete(refId);
    } else {
      next.add(refId);
    }
    setExpandedCards(next);
  };

  // Convert raw text into clickable citations like [REF-1]
  const renderFormattedAnswer = (content: string) => {
    const parts = content.split(/(\[REF-\d+\])/g);
    return parts.map((part, i) => {
      const match = part.match(/\[(REF-\d+)\]/);
      if (match) {
        const refId = match[1];
        const isSelected = selectedEvidenceId === refId;
        return (
          <button
            key={i}
            onClick={() => setSelectedEvidenceId(refId)}
            className={`inline-flex items-center px-1.5 py-0.5 mx-1 rounded text-xs font-mono font-bold transition-all cursor-pointer ${
              isSelected
                ? 'bg-[#38bdf8] text-[#090d16] ring-2 ring-[#38bdf8]'
                : 'bg-[#0369a1]/30 text-[#38bdf8] hover:bg-[#38bdf8]/20 hover:text-white border border-[#38bdf8]/40'
            }`}
            title={`Inspect ${refId} Evidence`}
          >
            {part}
          </button>
        );
      }
      return <span key={i}>{part}</span>;
    });
  };

  return (
    <div className="w-full h-[calc(100vh-65px)] flex overflow-hidden bg-[#0a0f1d] text-slate-100">
      {/* =========================================================================
          LEFT PANEL: Knowledge Base & Selective Reloading Management
          ========================================================================= */}
      <aside className="w-84 h-full border-r border-[#1e293b] flex flex-col shrink-0 bg-[#0f172a]/90 backdrop-blur-xl">
        {/* Top Header with Tab Switcher */}
        <div className="p-3 border-b border-[#1e293b] bg-[#090d16]/80 flex flex-col gap-2">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <BookOpen className="w-4 h-4 text-[#38bdf8]" />
              <h2 className="font-bold text-sm text-white font-['Space_Grotesk']">Knowledge Base</h2>
            </div>
            <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-[#1e293b] text-[#38bdf8] border border-[#38bdf8]/30 font-semibold">
              {documents.length} Active Articles
            </span>
          </div>

          {/* Unified Search + Add Article Bar */}
          <form onSubmit={handleIngest} className="relative flex gap-1.5">
            <div className="relative flex-1">
              <Search className="w-3.5 h-3.5 text-slate-400 absolute left-2.5 top-2.5" />
              <input
                type="text"
                placeholder="Search or add articles..."
                value={articleSearchQuery}
                onChange={(e) => setArticleSearchQuery(e.target.value)}
                className="w-full bg-[#1e293b]/70 border border-slate-700/60 rounded-lg pl-8 pr-3 py-1.5 text-xs text-white placeholder-slate-400 focus:outline-none focus:border-[#38bdf8]"
              />
            </div>
            <button
              type="submit"
              disabled={isIngesting || !articleSearchQuery.trim()}
              className="px-2.5 py-1.5 rounded-lg bg-[#38bdf8] hover:bg-sky-300 disabled:opacity-40 text-[#090d16] font-bold text-xs transition-all shrink-0 flex items-center gap-1 cursor-pointer shadow-md"
              title="Add Wikipedia article(s). Multiple can be separated by commas."
            >
              {isIngesting ? <RefreshCw className="w-3.5 h-3.5 animate-spin" /> : <Plus className="w-3.5 h-3.5" />}
              <span>Add</span>
            </button>
          </form>
          {ingestSuccess && (
            <div className="text-[11px] text-emerald-400 flex items-center gap-1 font-medium">
              <CheckCircle2 className="w-3 h-3 shrink-0" />
              <span className="line-clamp-1">{ingestSuccess}</span>
            </div>
          )}
          {ingestError && (
            <div className="text-[11px] text-rose-400 flex items-center gap-1 font-medium">
              <AlertCircle className="w-3 h-3 shrink-0" />
              <span className="line-clamp-1">{ingestError}</span>
            </div>
          )}

          {/* Sub-tabs: Active vs History */}
          <div className="flex items-center gap-1 bg-[#1e293b]/50 p-1 rounded-lg border border-slate-800">
            <button
              onClick={() => setKnowledgeTab('active')}
              className={`flex-1 py-1 px-2 rounded text-xs font-medium transition-all flex items-center justify-center gap-1.5 cursor-pointer ${
                knowledgeTab === 'active'
                  ? 'bg-[#38bdf8]/20 text-[#38bdf8] border border-[#38bdf8]/40 font-semibold'
                  : 'text-slate-400 hover:text-white'
              }`}
            >
              <BookOpen className="w-3 h-3" />
              <span>Active ({documents.length})</span>
            </button>
            <button
              onClick={() => setKnowledgeTab('history')}
              className={`flex-1 py-1 px-2 rounded text-xs font-medium transition-all flex items-center justify-center gap-1.5 cursor-pointer ${
                knowledgeTab === 'history'
                  ? 'bg-[#38bdf8]/20 text-[#38bdf8] border border-[#38bdf8]/40 font-semibold'
                  : 'text-slate-400 hover:text-white'
              }`}
            >
              <History className="w-3 h-3" />
              <span>History ({filteredHistory.length})</span>
            </button>
          </div>
        </div>

        {/* Simplified Action Bar */}
        {knowledgeTab === 'active' && documents.length > 0 && (
          <div className="px-3 py-2 border-b border-[#1e293b] bg-[#111927] flex items-center justify-between text-xs">
            {/* Selection toggle */}
            <button
              onClick={selectedArticles.size === documents.length ? deselectAllArticles : selectAllArticles}
              className="flex items-center gap-1.5 text-slate-300 hover:text-white cursor-pointer transition-colors"
              title={selectedArticles.size === documents.length ? 'Deselect All' : 'Select All'}
            >
              {selectedArticles.size === documents.length ? (
                <CheckSquare className="w-3.5 h-3.5 text-[#38bdf8]" />
              ) : selectedArticles.size > 0 ? (
                <CheckSquare className="w-3.5 h-3.5 text-sky-400/70" />
              ) : (
                <Square className="w-3.5 h-3.5 text-slate-500" />
              )}
              <span className="text-[11px] font-medium">
                {selectedArticles.size > 0 ? `${selectedArticles.size} of ${documents.length} selected` : 'Select all'}
              </span>
            </button>

            {/* Actions: Primary Reload Button + More Options Menu */}
            <div className="flex items-center gap-1.5">
              <button
                onClick={() => handleTriggerReload('reload_selected')}
                className="px-2.5 py-1 rounded-md bg-[#0284c7]/20 hover:bg-[#0284c7]/30 text-[#38bdf8] border border-[#0284c7]/40 text-[11px] font-semibold flex items-center gap-1 transition-all cursor-pointer"
                title="Reload selected articles (or all if none selected)"
              >
                <RefreshCw className="w-3 h-3" />
                <span>{selectedArticles.size > 0 ? `Reload (${selectedArticles.size})` : 'Reload'}</span>
              </button>

              {/* More Actions Dropdown */}
              <div className="relative">
                <button
                  type="button"
                  onClick={() => setShowAdvancedMenu(!showAdvancedMenu)}
                  className="p-1 rounded-md bg-slate-800 hover:bg-slate-700 text-slate-300 hover:text-white border border-slate-700 text-xs transition-all cursor-pointer"
                  title="Advanced options"
                >
                  <MoreVertical className="w-3.5 h-3.5" />
                </button>
                {showAdvancedMenu && (
                  <div className="absolute right-0 top-full mt-1 w-44 bg-[#1e293b] border border-slate-700 rounded-lg shadow-xl p-1 z-30 text-[11px] flex flex-col gap-0.5">
                    <button
                      onClick={() => { setShowAdvancedMenu(false); handleTriggerReload('refresh_wikipedia'); }}
                      className="w-full text-left px-2 py-1.5 rounded hover:bg-slate-700/80 text-slate-200 flex items-center gap-2 cursor-pointer"
                    >
                      <ExternalLink className="w-3 h-3 text-teal-400" />
                      <span>Check Wiki updates</span>
                    </button>
                    <button
                      onClick={() => { setShowAdvancedMenu(false); handleTriggerReload('reprocess_content'); }}
                      className="w-full text-left px-2 py-1.5 rounded hover:bg-slate-700/80 text-slate-200 flex items-center gap-2 cursor-pointer"
                    >
                      <RotateCcw className="w-3 h-3 text-indigo-400" />
                      <span>Reprocess (Offline)</span>
                    </button>
                    <button
                      onClick={() => { setShowAdvancedMenu(false); handleTriggerReload('reload_all'); }}
                      className="w-full text-left px-2 py-1.5 rounded hover:bg-slate-700/80 text-slate-200 flex items-center gap-2 cursor-pointer"
                    >
                      <RefreshCw className="w-3 h-3 text-sky-400" />
                      <span>Reload all articles</span>
                    </button>
                  </div>
                )}
              </div>
            </div>
          </div>
        )}

        {/* Active Background Task Progress Banner */}
        {activeTask && activeTask.status === 'running' && (
          <div className="p-3 bg-sky-950/60 border-b border-sky-500/30 text-xs space-y-1.5">
            <div className="flex items-center justify-between text-sky-300 font-semibold">
              <span className="flex items-center gap-1.5">
                <RefreshCw className="w-3 h-3 animate-spin text-sky-400" />
                {activeTask.stage}...
              </span>
              <span className="font-mono text-[11px]">{Math.round(activeTask.progress * 100)}%</span>
            </div>
            {/* Progress bar */}
            <div className="w-full bg-slate-800 h-1.5 rounded-full overflow-hidden">
              <div
                className="bg-sky-400 h-full transition-all duration-300"
                style={{ width: `${Math.round(activeTask.progress * 100)}%` }}
              />
            </div>
            <div className="text-[10px] text-slate-300 flex items-center justify-between">
              <span className="truncate max-w-[180px]">{activeTask.current_item || activeTask.name}</span>
              <span className="font-mono">{activeTask.elapsed_seconds}s</span>
            </div>
          </div>
        )}

        {/* Article Records List */}
        <div className="flex-1 overflow-y-auto p-2 space-y-1.5">
          {knowledgeTab === 'active' ? (
            filteredDocuments.length === 0 ? (
              <div className="text-center py-8 text-xs text-slate-400">
                {articleSearchQuery ? 'No matching articles found.' : 'No articles loaded yet.'}
              </div>
            ) : (
              filteredDocuments.map((doc) => {
                const isSelected = selectedArticles.has(doc.title);
                const isFailed = doc.status === 'failed' || doc.status === 'stale';
                return (
                  <div
                    key={doc.title}
                    className={`p-2.5 rounded-xl border transition-all text-xs flex flex-col gap-1.5 ${
                      isSelected
                        ? 'bg-sky-950/40 border-sky-500/50 shadow-sm'
                        : 'bg-[#1e293b]/50 border-slate-800 hover:border-slate-700'
                    }`}
                  >
                    <div className="flex items-center justify-between gap-1.5">
                      <div className="flex items-center gap-2 truncate">
                        <button
                          onClick={() => toggleArticleSelect(doc.title)}
                          className="text-slate-400 hover:text-white cursor-pointer"
                        >
                          {isSelected ? (
                            <CheckSquare className="w-4 h-4 text-[#38bdf8]" />
                          ) : (
                            <Square className="w-4 h-4 text-slate-500" />
                          )}
                        </button>
                        <a
                          href={doc.url}
                          target="_blank"
                          rel="noreferrer"
                          className="font-semibold text-slate-100 hover:text-[#38bdf8] flex items-center gap-1 truncate"
                        >
                          <span className="truncate">{doc.title}</span>
                          <ExternalLink className="w-2.5 h-2.5 shrink-0 opacity-60" />
                        </a>
                      </div>

                      <div className="flex items-center gap-1 shrink-0">
                        {/* Status Badge */}
                        <span
                          className={`text-[9px] font-mono px-1.5 py-0.5 rounded font-bold uppercase ${
                            isFailed
                              ? 'bg-amber-950 text-amber-400 border border-amber-600/30'
                              : 'bg-emerald-950 text-emerald-400 border border-emerald-600/30'
                          }`}
                        >
                          {doc.status || 'Indexed'}
                        </span>
                        {/* Individual reload */}
                        <button
                          onClick={() => onReloadArticles([doc.title], 'reload_selected')}
                          className="p-1 rounded text-slate-400 hover:text-[#38bdf8] hover:bg-slate-800 cursor-pointer"
                          title="Reload this article"
                        >
                          <RefreshCw className="w-3 h-3" />
                        </button>
                        {/* Remove */}
                        {onRemoveArticle && (
                          <button
                            onClick={() => onRemoveArticle(doc.title, false)}
                            className="p-1 rounded text-slate-400 hover:text-rose-400 hover:bg-slate-800 cursor-pointer"
                            title="Unload from active index"
                          >
                            <Trash2 className="w-3 h-3" />
                          </button>
                        )}
                      </div>
                    </div>

                    {/* Metadata Footer */}
                    <div className="flex items-center justify-between text-[10px] text-slate-400 font-mono">
                      <span>{doc.chunks_count} chunks · {doc.token_count || Math.round(doc.char_count / 4)} tokens</span>
                      <span>{doc.char_count.toLocaleString()} chars</span>
                    </div>
                  </div>
                );
              })
            )
          ) : (
            filteredHistory.length === 0 ? (
              <div className="text-center py-8 text-xs text-slate-400">No inactive history records.</div>
            ) : (
              filteredHistory.map((item) => {
                const isReactivating = reactivatingTitle === item.title;
                return (
                  <div
                    key={item.title}
                    className="p-2.5 rounded-xl border border-slate-800 bg-[#1e293b]/40 text-xs flex flex-col gap-1"
                  >
                    <div className="flex items-center justify-between">
                      <span className="font-semibold text-slate-200 truncate">{item.title}</span>
                      <button
                        onClick={() => handleReactivate(item.title)}
                        disabled={isReactivating}
                        className={`px-2 py-0.5 rounded border text-[10px] font-bold cursor-pointer flex items-center gap-1 transition-all ${
                          isReactivating
                            ? 'bg-sky-950/50 text-sky-400/60 border-sky-500/20'
                            : 'bg-sky-950 text-sky-400 hover:bg-sky-900 border-sky-500/30 hover:text-sky-300'
                        }`}
                      >
                        {isReactivating && <RefreshCw className="w-2.5 h-2.5 animate-spin" />}
                        <span>{isReactivating ? 'Activating...' : 'Re-activate'}</span>
                      </button>
                    </div>
                    <div className="text-[10px] text-slate-400 flex items-center justify-between font-mono">
                      <span>{item.chunks_count} chunks</span>
                      <span>{item.char_count.toLocaleString()} chars</span>
                    </div>
                  </div>
                );
              })
            )
          )}
        </div>
      </aside>

      {/* =========================================================================
          CENTER PANEL: Research Chat Workspace
          ========================================================================= */}
      <main className="flex-1 h-full flex flex-col bg-[#0a0f1d] border-r border-[#1e293b] relative">
        {/* Chat Header */}
        <div className="px-5 py-3 border-b border-[#1e293b] bg-[#0f172a]/80 backdrop-blur-md flex items-center justify-between shrink-0">
          <div className="flex items-center gap-3">
            <Sparkles className="w-4 h-4 text-[#38bdf8]" />
            <div>
              <h2 className="font-bold text-sm text-white font-['Space_Grotesk']">
                Research Reasoning Chat
              </h2>
              <div className="text-[11px] text-slate-400 flex items-center gap-2">
                <span>
                  Target Scope:{' '}
                  <b className="text-sky-300">
                    {selectedArticles.size > 0
                      ? `${selectedArticles.size} selected article(s)`
                      : `All active articles (${documents.length})`}
                  </b>
                </span>
              </div>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={onClearChat}
              className="text-xs px-2.5 py-1 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 hover:text-white transition-all cursor-pointer font-medium"
            >
              Clear Chat
            </button>
          </div>
        </div>

        {/* Pipeline Stage Indicator Ribbon if present */}
        {currentStages && currentStages.length > 0 && (
          <div className="px-5 py-2 bg-[#0c1322] border-b border-sky-500/20 flex items-center gap-2 overflow-x-auto text-[11px] shrink-0">
            {currentStages.map((stg, idx) => (
              <React.Fragment key={stg.stage}>
                <div className="flex items-center gap-1.5 shrink-0 px-2 py-0.5 rounded bg-[#1e293b] text-sky-300 border border-sky-500/30 font-medium">
                  <span className="font-bold font-mono">{idx + 1}.</span>
                  <span>{stg.title}</span>
                  <span className="font-mono text-[9px] text-slate-400">({stg.time_ms}ms)</span>
                </div>
                {idx < currentStages.length - 1 && <span className="text-slate-600">→</span>}
              </React.Fragment>
            ))}
          </div>
        )}

        {/* Conversation Turns Viewport */}
        <div className="flex-1 overflow-y-auto p-5 space-y-5">
          {chatHistory.length === 0 ? (
            /* Welcoming Empty State */
            <div className="h-full flex flex-col items-center justify-center text-center p-6 max-w-xl mx-auto space-y-6">
              <div className="w-14 h-14 rounded-2xl bg-sky-950/80 border border-sky-500/30 flex items-center justify-center text-sky-400 shadow-xl">
                <Sparkles className="w-7 h-7" />
              </div>
              <div className="space-y-2">
                <h3 className="text-lg font-bold text-white font-['Space_Grotesk']">
                  Welcome to Cognitive RAG Workspace
                </h3>
                <p className="text-xs text-slate-400 leading-relaxed">
                  Your knowledge base contains <b>{documents.length} loaded Wikipedia articles</b> and{' '}
                  <b>{documents.reduce((acc, d) => acc + d.chunks_count, 0)} semantic vector chunks</b>.
                  Ask any question to receive factually grounded answers with verified citations and vector evidence.
                </p>
              </div>

              {/* Example Questions */}
              <div className="w-full space-y-2 text-left">
                <div className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider">
                  Suggested Research Questions:
                </div>
                <div className="grid grid-cols-1 gap-2">
                  {[
                    'Who was Histiaeus and what was his historical role?',
                    'What are the core concepts and teachings of Sadhguru?',
                    'Explain the origins and historical aspects of spirituality.',
                    'Compare and synthesize the key findings across all loaded topics.'
                  ].map((q) => (
                    <button
                      key={q}
                      onClick={() => handleExamplePrompt(q)}
                      className="p-2.5 rounded-xl bg-[#1e293b]/60 hover:bg-[#1e293b] border border-slate-800 hover:border-[#38bdf8]/40 text-xs text-slate-200 text-left transition-all cursor-pointer flex items-center justify-between group"
                    >
                      <span>"{q}"</span>
                      <span className="text-sky-400 opacity-0 group-hover:opacity-100 transition-opacity font-bold">
                        →
                      </span>
                    </button>
                  ))}
                </div>
              </div>
            </div>
          ) : (
            chatHistory.map((msg) => (
              <div
                key={msg.id}
                className={`flex flex-col gap-1.5 ${
                  msg.role === 'user' ? 'items-end' : 'items-start'
                }`}
              >
                <div
                  className={`max-w-[85%] rounded-2xl p-4 text-xs leading-relaxed shadow-lg ${
                    msg.role === 'user'
                      ? 'bg-[#0284c7] text-white rounded-br-none'
                      : 'bg-[#1e293b]/80 border border-slate-800 text-slate-100 rounded-bl-none'
                  }`}
                >
                  <div className="whitespace-pre-wrap font-sans">
                    {msg.role === 'assistant' ? renderFormattedAnswer(msg.content) : msg.content}
                  </div>

                  {msg.role === 'assistant' && (
                    <div className="mt-3 pt-2.5 border-t border-slate-700/60 flex items-center justify-between text-[10px] text-slate-400">
                      <div className="flex items-center gap-2">
                        {msg.elapsed_seconds && (
                          <span className="flex items-center gap-1 font-mono">
                            <Clock className="w-3 h-3 text-sky-400" />
                            {msg.elapsed_seconds}s
                          </span>
                        )}
                        {msg.citations?.total_cited ? (
                          <span className="text-emerald-400 font-semibold font-mono">
                            {msg.citations.total_cited} direct citations
                          </span>
                        ) : null}
                      </div>

                      <button
                        onClick={() => handleCopyText(msg.content, msg.id)}
                        className="text-slate-400 hover:text-white flex items-center gap-1 cursor-pointer font-medium"
                      >
                        {copiedMsgId === msg.id ? <Check className="w-3 h-3 text-emerald-400" /> : <Copy className="w-3 h-3" />}
                        <span>{copiedMsgId === msg.id ? 'Copied' : 'Copy'}</span>
                      </button>
                    </div>
                  )}
                </div>
              </div>
            ))
          )}

          {isQuerying && (
            <div className="flex items-center gap-3 p-4 rounded-2xl bg-[#1e293b]/50 border border-sky-500/20 max-w-sm animate-pulse">
              <RefreshCw className="w-4 h-4 text-[#38bdf8] animate-spin" />
              <div className="text-xs text-sky-300 font-medium">
                Executing 6-Stage RAG Pipeline...
              </div>
            </div>
          )}

          <div ref={chatBottomRef} />
        </div>

        {/* Composer Input Form */}
        <div className="p-4 border-t border-[#1e293b] bg-[#0f172a]/90 backdrop-blur-xl">
          <form onSubmit={handleSubmitQuery} className="relative flex flex-col gap-2">
            <div className="relative">
              <textarea
                rows={2}
                placeholder="Ask anything about your knowledge base... (Press Enter to send, Shift+Enter for newline)"
                value={inputQuery}
                onChange={(e) => setInputQuery(e.target.value)}
                onKeyDown={handleKeyDown}
                disabled={isQuerying}
                className="w-full bg-[#1e293b]/90 border border-slate-700/80 rounded-xl px-4 py-2.5 text-xs text-white placeholder-slate-400 focus:outline-none focus:border-[#38bdf8] focus:ring-1 focus:ring-[#38bdf8] resize-none"
              />
              <button
                type="submit"
                disabled={isQuerying || !inputQuery.trim()}
                className="absolute right-3 bottom-3 px-4 py-1.5 rounded-lg bg-[#38bdf8] hover:bg-sky-300 disabled:opacity-40 text-[#090d16] font-bold text-xs transition-all shadow-md flex items-center gap-1.5 cursor-pointer"
              >
                {isQuerying ? <RefreshCw className="w-3.5 h-3.5 animate-spin" /> : <Sparkles className="w-3.5 h-3.5" />}
                <span>Research</span>
              </button>
            </div>
          </form>
        </div>
      </main>

      {/* =========================================================================
          RIGHT PANEL: Evidence & Citations Retrieval Panel
          ========================================================================= */}
      <aside className="w-96 h-full border-l border-[#1e293b] flex flex-col shrink-0 bg-[#0f172a]/90 backdrop-blur-xl">
        <div className="p-3 border-b border-[#1e293b] bg-[#090d16]/80 flex items-center justify-between shrink-0">
          <div className="flex items-center gap-2">
            <FileText className="w-4 h-4 text-[#38bdf8]" />
            <h2 className="font-bold text-sm text-white font-['Space_Grotesk']">
              Retrieved Evidence
            </h2>
          </div>
          <span className="text-[10px] font-mono font-bold px-2 py-0.5 rounded bg-[#1e293b] text-[#38bdf8] border border-[#38bdf8]/30">
            {currentEvidences.length} Passages
          </span>
        </div>

        {/* Evidence List */}
        <div className="flex-1 overflow-y-auto p-3 space-y-3">
          {currentEvidences.length === 0 ? (
            <div className="h-full flex flex-col items-center justify-center text-center p-6 space-y-3 text-slate-400">
              <div className="w-12 h-12 rounded-xl bg-slate-800/60 border border-slate-700 flex items-center justify-center text-slate-400 text-xl">
                🪐
              </div>
              <div className="text-xs font-semibold text-slate-200">No Evidence Retrieved Yet</div>
              <p className="text-[11px] leading-relaxed max-w-xs">
                Submit a research query to retrieve semantic evidence passages with similarity scores and direct citations.
              </p>
            </div>
          ) : (
            currentEvidences.map((ev) => {
              const isSelected = selectedEvidenceId === ev.ref_id;
              const isExpanded = expandedCards.has(ev.ref_id);
              const scorePct = Math.round(ev.similarity_score * 100);

              return (
                <div
                  key={ev.ref_id}
                  className={`p-3 rounded-xl border transition-all text-xs flex flex-col gap-2 ${
                    isSelected
                      ? 'bg-sky-950/60 border-sky-400 shadow-md ring-1 ring-sky-400'
                      : 'bg-[#1e293b]/60 border-slate-800 hover:border-slate-700'
                  }`}
                >
                  {/* Header: Ref ID, Title, Score */}
                  <div className="flex items-center justify-between gap-2">
                    <div className="flex items-center gap-1.5 truncate">
                      <span className="font-mono font-bold px-1.5 py-0.5 rounded bg-sky-950 text-sky-300 border border-sky-500/40 text-[10px]">
                        {ev.ref_id}
                      </span>
                      <a
                        href={ev.url}
                        target="_blank"
                        rel="noreferrer"
                        className="font-semibold text-slate-100 hover:text-sky-300 truncate"
                      >
                        {ev.title}
                      </a>
                    </div>
                    <span
                      className={`text-[10px] font-mono px-2 py-0.5 rounded font-bold shrink-0 ${
                        ev.similarity_score >= 0.7
                          ? 'bg-emerald-950 text-emerald-400 border border-emerald-500/30'
                          : 'bg-sky-950 text-sky-400 border border-sky-500/30'
                      }`}
                    >
                      {scorePct}% Match
                    </span>
                  </div>

                  {/* Section & Chunk metadata */}
                  <div className="text-[11px] text-slate-400 flex items-center justify-between">
                    <span>Section: <b className="text-slate-300">{ev.section}</b></span>
                    <span className="font-mono text-[10px] text-slate-500">{ev.chunk_id}</span>
                  </div>

                  {/* Score Explanation Badge */}
                  {ev.score_explanation && (
                    <div className="text-[10px] text-slate-400 bg-slate-900/60 p-1.5 rounded-lg border border-slate-800">
                      {ev.score_explanation}
                    </div>
                  )}

                  {/* Text excerpt */}
                  <div className="text-slate-200 leading-relaxed bg-[#0b1220]/60 p-2 rounded-lg border border-slate-800/80">
                    {isExpanded ? ev.full_text : `"${ev.preview}"`}
                  </div>

                  {/* Card Controls */}
                  <div className="flex items-center justify-between text-[11px] text-slate-400 pt-1">
                    <button
                      onClick={() => toggleCardExpand(ev.ref_id)}
                      className="text-sky-400 hover:text-sky-300 flex items-center gap-1 cursor-pointer font-medium"
                    >
                      {isExpanded ? (
                        <>
                          <ChevronUp className="w-3 h-3" />
                          <span>Show Less</span>
                        </>
                      ) : (
                        <>
                          <ChevronDown className="w-3 h-3" />
                          <span>Show Full Context</span>
                        </>
                      )}
                    </button>

                    <button
                      onClick={() => setInspectModalEvidence(ev)}
                      className="text-slate-400 hover:text-white cursor-pointer"
                    >
                      Inspect Full
                    </button>
                  </div>
                </div>
              );
            })
          )}
        </div>
      </aside>

      {/* Inspect Modal */}
      {inspectModalEvidence && (
        <div className="fixed inset-0 z-50 bg-black/80 backdrop-blur-md flex items-center justify-center p-4">
          <div className="w-full max-w-2xl bg-[#0f172a] border border-slate-700 rounded-2xl p-6 shadow-2xl flex flex-col gap-4 max-h-[85vh]">
            <div className="flex items-center justify-between pb-3 border-b border-slate-800">
              <div className="flex items-center gap-2">
                <span className="font-mono font-bold text-sky-400">[{inspectModalEvidence.ref_id}]</span>
                <h3 className="font-bold text-white text-sm">{inspectModalEvidence.title}</h3>
              </div>
              <button
                onClick={() => setInspectModalEvidence(null)}
                className="text-slate-400 hover:text-white px-2 py-1 rounded bg-slate-800 cursor-pointer"
              >
                ✕
              </button>
            </div>
            <div className="text-xs text-slate-400 flex items-center justify-between">
              <span>Section: <b>{inspectModalEvidence.section}</b></span>
              <span>Source: <a href={inspectModalEvidence.url} target="_blank" rel="noreferrer" className="text-sky-400 underline">{inspectModalEvidence.url}</a></span>
            </div>
            <div className="flex-1 overflow-y-auto bg-[#0a0f1d] p-4 rounded-xl border border-slate-800 text-xs text-slate-200 leading-relaxed font-sans whitespace-pre-wrap">
              {inspectModalEvidence.full_text}
            </div>
            <div className="flex justify-end gap-2 pt-2 border-t border-slate-800">
              <button
                onClick={() => {
                  navigator.clipboard.writeText(inspectModalEvidence.full_text);
                  alert('Full context copied to clipboard!');
                }}
                className="px-4 py-1.5 rounded-lg bg-sky-500 hover:bg-sky-400 text-slate-950 font-bold text-xs cursor-pointer"
              >
                Copy Text
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
