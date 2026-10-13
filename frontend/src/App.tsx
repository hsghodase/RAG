import React, { useState, useEffect, useCallback, useRef } from 'react';
import { Navbar } from './components/Navbar';
import { LandingHero } from './components/LandingHero';
import { ThreePanelWorkspace } from './components/ThreePanelWorkspace';
import { GraphExplorer } from './components/GraphExplorer';
import { SettingsModal } from './components/SettingsModal';
import { api } from './services/api';
import {
  SystemStatus, AppConfig, DocumentMeta, ArticleHistoryItem, GraphData,
  RetrievedEvidence, PipelineStage, ChatMessage, BackgroundTask
} from './types';

export const App: React.FC = () => {
  const [activeTab, setActiveTab] = useState<'overview' | 'workspace' | 'graph'>('workspace');
  const [status, setStatus] = useState<SystemStatus | null>(null);
  const [config, setConfig] = useState<AppConfig | null>(null);
  const [documents, setDocuments] = useState<DocumentMeta[]>([]);
  const [articleHistory, setArticleHistory] = useState<ArticleHistoryItem[]>([]);
  const [graphData, setGraphData] = useState<GraphData | null>(null);

  const [chatHistory, setChatHistory] = useState<ChatMessage[]>([]);
  const [currentEvidences, setCurrentEvidences] = useState<RetrievedEvidence[]>([]);
  const [currentStages, setCurrentStages] = useState<PipelineStage[] | null>(null);
  const [selectedEvidenceId, setSelectedEvidenceId] = useState<string | null>(null);

  const [isQuerying, setIsQuerying] = useState(false);
  const [loadingTopic, setLoadingTopic] = useState<string | null>(null);
  const [isSettingsOpen, setIsSettingsOpen] = useState(false);
  const [globalError, setGlobalError] = useState<{ what: string; why: string; how: string } | null>(null);
  
  // Background reload/ingestion task tracking
  const [activeTask, setActiveTask] = useState<BackgroundTask | null>(null);
  const pollingIntervalRef = useRef<any>(null);

  // Initial Data Fetch
  const refreshAllData = useCallback(async () => {
    try {
      const [statusRes, configRes, articlesRes, graphRes] = await Promise.all([
        api.getStatus().catch(() => null),
        api.getConfig().catch(() => null),
        api.getArticles().catch(() => ({ count: 0, articles: [], total_chunks: 0, history: [] })),
        api.getGraph().catch(() => null),
      ]);

      if (statusRes) setStatus(statusRes);
      if (configRes) setConfig(configRes);
      if (articlesRes?.articles) setDocuments(articlesRes.articles);
      if (articlesRes?.history) setArticleHistory(articlesRes.history);
      if (graphRes) setGraphData(graphRes);
    } catch (e) {
      console.error('Error refreshing system state:', e);
    }
  }, []);

  useEffect(() => {
    refreshAllData();
  }, [refreshAllData]);

  // Clean up polling interval on unmount
  useEffect(() => {
    return () => {
      if (pollingIntervalRef.current) clearInterval(pollingIntervalRef.current);
    };
  }, []);

  // Poll background task progress
  const startTaskPolling = (taskId: string) => {
    if (pollingIntervalRef.current) clearInterval(pollingIntervalRef.current);

    pollingIntervalRef.current = setInterval(async () => {
      try {
        const task = await api.getTaskStatus(taskId);
        setActiveTask(task);
        if (task.status === 'completed' || task.status === 'failed') {
          clearInterval(pollingIntervalRef.current);
          pollingIntervalRef.current = null;
          await refreshAllData();
          setTimeout(() => setActiveTask(null), 5000);
        }
      } catch (e) {
        clearInterval(pollingIntervalRef.current);
        pollingIntervalRef.current = null;
      }
    }, 1000);
  };

  // Execute RAG Query with Scope Filtering
  const handleSendQuery = async (queryText: string, articleFilter?: string[]) => {
    if (!queryText.trim()) return;

    setIsQuerying(true);
    setGlobalError(null);

    // Optimistically add user message
    const userMsg: ChatMessage = {
      id: `user_${Date.now()}`,
      role: 'user',
      content: queryText,
      timestamp: Date.now(),
    };
    setChatHistory((prev) => [...prev, userMsg]);

    try {
      const res = await api.queryRag(queryText, undefined, undefined, articleFilter);

      const assistantMsg: ChatMessage = {
        id: `assistant_${Date.now()}`,
        role: 'assistant',
        content: res.answer,
        citations: res.citations,
        evidences: res.evidences,
        stages: res.stages,
        elapsed_seconds: res.elapsed_seconds,
        timestamp: Date.now(),
      };

      setChatHistory((prev) => [...prev, assistantMsg]);
      setCurrentEvidences(res.evidences || []);
      setCurrentStages(res.stages || []);

      // If citations exist, highlight first cited card
      if (res.citations?.cited_keys?.length) {
        setSelectedEvidenceId(res.citations.cited_keys[0]);
      } else if (res.evidences?.length) {
        setSelectedEvidenceId(res.evidences[0].ref_id);
      }

      // Refresh 3D Graph with active query node and retrieval rays
      const updatedGraph = await api.getGraph();
      setGraphData(updatedGraph);
    } catch (err: any) {
      const errMsg = err.message || 'Could not complete vector retrieval or generation.';
      
      // Preserve chat history: append assistant error response so workspace is never broken/empty
      const assistantErrorMsg: ChatMessage = {
        id: `assistant_${Date.now()}`,
        role: 'assistant',
        content: `⚠️ **Query Execution Notice**\n\n${errMsg}\n\nPlease verify your Google Gemini API key in **Settings** or check your knowledge base.`,
        isError: true,
        timestamp: Date.now(),
      };
      setChatHistory((prev) => [...prev, assistantErrorMsg]);

      setGlobalError({
        what: 'Query Notice',
        why: errMsg,
        how: 'Verify your Gemini API key in Settings or check article loading.',
      });
    } finally {
      setIsQuerying(false);
    }
  };

  // Transactional article reloading
  const handleReloadArticles = async (articles: string[], mode: string) => {
    setGlobalError(null);
    try {
      const res = await api.reloadArticles(articles, mode, true);
      if (res.task_id) {
        setActiveTask({
          task_id: res.task_id,
          name: mode.replace('_', ' '),
          status: 'queued',
          stage: 'Queued',
          progress: 0.0,
          current_item: 'Initializing...',
          total_items: articles.length,
          completed_items: 0,
          failed_items: 0,
          elapsed_seconds: 0,
          errors: []
        });
        startTaskPolling(res.task_id);
      } else {
        await refreshAllData();
      }
    } catch (err: any) {
      setGlobalError({
        what: 'Article Reload Failed',
        why: err.message || 'Failed to reload selected articles.',
        how: 'Check network connectivity or retry with Reprocess Content.',
      });
      throw err;
    }
  };

  // Ingest custom articles
  const handleLoadCustomArticles = async (articles: string[]) => {
    setGlobalError(null);
    try {
      const res = await api.loadArticles(articles);
      await refreshAllData();
      return res;
    } catch (err: any) {
      setGlobalError({
        what: 'Article Ingestion Failed',
        why: err.message || 'Wikipedia could not find or download the specified titles.',
        how: 'Verify spelling of Wikipedia article titles (e.g., "Artificial intelligence").',
      });
      throw err;
    }
  };

  // Remove / Unload article from workspace or permanently delete from history
  const handleRemoveArticle = async (title: string, deleteFromHistory: boolean = false) => {
    setGlobalError(null);
    try {
      await api.removeArticle(title, deleteFromHistory);
      await refreshAllData();
    } catch (err: any) {
      setGlobalError({
        what: 'Article Removal Failed',
        why: err.message || 'Could not remove article from knowledge base.',
        how: 'Check connection or retry.',
      });
      throw err;
    }
  };

  // Ingest quick start topic
  const handleLoadTopic = async (topicId: string) => {
    setLoadingTopic(topicId);
    setGlobalError(null);
    try {
      await api.loadArticles([], topicId);
      await refreshAllData();
      setActiveTab('workspace');
    } catch (err: any) {
      setGlobalError({
        what: 'Topic Cluster Loading Failed',
        why: err.message || 'Network error while retrieving Wikipedia articles.',
        how: 'Check internet connection or retry loading the topic.',
      });
    } finally {
      setLoadingTopic(null);
    }
  };

  const handleClearChat = async () => {
    await api.clearChat();
    setChatHistory([]);
    setCurrentEvidences([]);
    setCurrentStages(null);
    setSelectedEvidenceId(null);
    const updatedGraph = await api.getGraph();
    setGraphData(updatedGraph);
  };

  const handleClearCache = async () => {
    await api.clearCache();
    await refreshAllData();
  };

  const handleSaveSettings = async (updated: Partial<AppConfig> & { gemini_api_key?: string }) => {
    await api.updateConfig(updated);
    await refreshAllData();
  };

  return (
    <div className="w-full min-h-screen bg-slate-950 text-slate-100 flex flex-col font-sans select-text">
      {/* Top Navigation */}
      <Navbar
        activeTab={activeTab}
        setActiveTab={setActiveTab}
        status={status}
        onOpenSettings={() => setIsSettingsOpen(true)}
      />

      {/* Global Error Banner */}
      {globalError && (
        <div className="w-full bg-rose-950/80 border-b border-rose-500/30 px-6 py-2.5 flex items-center justify-between text-xs backdrop-blur-md z-30">
          <div className="flex items-center gap-3">
            <span className="font-bold text-rose-300 font-['Space_Grotesk']">
              {globalError.what}:
            </span>
            <span className="text-slate-200">{globalError.why}</span>
            <span className="text-rose-300 font-medium bg-rose-900/40 px-2 py-0.5 rounded">
              Solution: {globalError.how}
            </span>
          </div>
          <button
            onClick={() => setGlobalError(null)}
            className="text-rose-400 hover:text-white font-mono px-2 py-0.5"
          >
            ✕
          </button>
        </div>
      )}

      {/* Main Viewport */}
      <div className="flex-1 w-full relative">
        {activeTab === 'overview' && (
          <LandingHero
            onStartResearch={() => setActiveTab('workspace')}
            onExploreGraph={() => setActiveTab('graph')}
            onLoadTopic={handleLoadTopic}
            graphData={graphData}
            status={status}
            loadingTopic={loadingTopic}
          />
        )}

        {activeTab === 'workspace' && (
          <ThreePanelWorkspace
            documents={documents}
            articleHistory={articleHistory}
            chatHistory={chatHistory}
            currentEvidences={currentEvidences}
            currentStages={currentStages}
            isQuerying={isQuerying}
            onSendQuery={handleSendQuery}
            onLoadCustomArticles={async (articles) => {
              await handleLoadCustomArticles(articles);
            }}
            onReloadArticles={handleReloadArticles}
            onRemoveArticle={handleRemoveArticle}
            onClearChat={handleClearChat}
            onClearCache={handleClearCache}
            selectedEvidenceId={selectedEvidenceId}
            setSelectedEvidenceId={setSelectedEvidenceId}
            onOpenSettings={() => setIsSettingsOpen(true)}
            activeTask={activeTask}
          />
        )}

        {activeTab === 'graph' && (
          <GraphExplorer
            graphData={graphData}
            onRefreshGraph={refreshAllData}
          />
        )}
      </div>

      {/* Settings Modal */}
      <SettingsModal
        isOpen={isSettingsOpen}
        onClose={() => setIsSettingsOpen(false)}
        config={config}
        onSave={handleSaveSettings}
      />
    </div>
  );
};

export default App;
