import {
  SystemStatus, AppConfig, DocumentMeta, GraphData,
  RetrievedEvidence, PipelineStage, CitationData,
  BackgroundTask, ConnectionTestResult
} from '../types';

const API_BASE = '/api';

async function handleResponse<T>(res: Response): Promise<T> {
  if (!res.ok) {
    let errorDetail = 'API Request failed';
    try {
      const errJson = await res.json();
      if (typeof errJson.detail === 'string') {
        errorDetail = errJson.detail;
      } else if (errJson.detail?.message) {
        errorDetail = errJson.detail.message;
      } else if (errJson.message) {
        errorDetail = errJson.message;
      } else {
        errorDetail = JSON.stringify(errJson.detail || errJson);
      }
    } catch {
      errorDetail = `HTTP ${res.status}: ${res.statusText}`;
    }
    throw new Error(errorDetail);
  }
  return res.json();
}

export const api = {
  async getHealth(): Promise<any> {
    const res = await fetch(`${API_BASE}/health`);
    return handleResponse(res);
  },

  async getStatus(): Promise<SystemStatus> {
    const res = await fetch(`${API_BASE}/status`);
    return handleResponse<SystemStatus>(res);
  },

  async getConfig(): Promise<AppConfig> {
    const res = await fetch(`${API_BASE}/config`);
    return handleResponse<AppConfig>(res);
  },

  async updateConfig(params: Partial<AppConfig> & { gemini_api_key?: string }): Promise<any> {
    const res = await fetch(`${API_BASE}/config`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(params),
    });
    return handleResponse(res);
  },

  async testConnection(): Promise<ConnectionTestResult> {
    const res = await fetch(`${API_BASE}/config/test-connection`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
    });
    return handleResponse<ConnectionTestResult>(res);
  },

  async getTopics(): Promise<Record<string, string[]>> {
    const res = await fetch(`${API_BASE}/topics`);
    return handleResponse<Record<string, string[]>>(res);
  },

  async loadArticles(articles: string[], topicName?: string): Promise<{
    success: boolean;
    message: string;
    articles: DocumentMeta[];
    total_chunks: number;
    history: any[];
    status_map: Record<string, string>;
  }> {
    const res = await fetch(`${API_BASE}/articles/load`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ articles, topic_name: topicName }),
    });
    return handleResponse(res);
  },

  async reloadArticles(articles: string[], mode: string = 'reload_selected', asyncMode: boolean = true): Promise<{
    success: boolean;
    task_id?: string;
    message: string;
    status_map?: Record<string, string>;
    articles?: DocumentMeta[];
    total_chunks?: number;
  }> {
    const res = await fetch(`${API_BASE}/articles/reload`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ articles, mode, async_mode: asyncMode }),
    });
    return handleResponse(res);
  },

  async getTaskStatus(taskId: string): Promise<BackgroundTask> {
    const res = await fetch(`${API_BASE}/tasks/${taskId}`);
    return handleResponse<BackgroundTask>(res);
  },

  async getArticles(): Promise<{
    count: number;
    total_tracked?: number;
    articles: DocumentMeta[];
    total_chunks: number;
    history: any[];
    cache_stats?: any;
  }> {
    const res = await fetch(`${API_BASE}/articles`);
    return handleResponse(res);
  },

  async removeArticle(title: string, deleteFromHistory: boolean = false): Promise<{
    success: boolean;
    message: string;
    articles: DocumentMeta[];
    total_chunks: number;
    history: any[];
  }> {
    const res = await fetch(`${API_BASE}/articles/remove`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ title, delete_from_history: deleteFromHistory }),
    });
    return handleResponse(res);
  },

  async queryRag(query: string, topK?: number, threshold?: number, articleFilter?: string[]): Promise<{
    success: boolean;
    query: string;
    answer: string;
    citations: CitationData;
    evidences: RetrievedEvidence[];
    stages: PipelineStage[];
    elapsed_seconds: number;
  }> {
    const res = await fetch(`${API_BASE}/query`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        query,
        top_k: topK,
        similarity_threshold: threshold,
        article_filter: articleFilter && articleFilter.length > 0 ? articleFilter : null
      }),
    });
    return handleResponse(res);
  },

  async getGraph(): Promise<GraphData> {
    const res = await fetch(`${API_BASE}/graph`);
    return handleResponse<GraphData>(res);
  },

  async clearChat(): Promise<{ status: string; message: string }> {
    const res = await fetch(`${API_BASE}/chat/clear`, { method: 'POST' });
    return handleResponse(res);
  },

  async clearCache(): Promise<{ status: string; message: string }> {
    const res = await fetch(`${API_BASE}/cache/clear`, { method: 'POST' });
    return handleResponse(res);
  },
};
