export interface SystemStatus {
  online: boolean;
  device: string;
  embedding_model: string;
  llm_model: string;
  has_api_key: boolean;
  documents_loaded: number;
  total_chunks: number;
  cached_indexes: number;
  cached_embeddings?: number;
  chat_turns: number;
}

export interface AppConfig {
  llm_model: string;
  temperature: number;
  max_output_tokens: number;
  top_k: number;
  similarity_threshold: number;
  chunk_size: number;
  chunk_overlap: number;
  context_token_budget?: number;
  device: string;
  embedding_model: string;
  has_api_key: boolean;
  api_key_masked?: string;
}

export interface DocumentMeta {
  article_id?: string;
  title: string;
  url: string;
  char_count: number;
  token_count?: number;
  chunks_count: number;
  type: string;
  status?: 'indexed' | 'saved' | 'failed' | 'stale' | 'loading';
  last_error?: string | null;
  is_active?: boolean;
  loaded_at?: number;
  last_updated?: number;
}

export interface ArticleRecord extends DocumentMeta {
  article_id: string;
  status: 'indexed' | 'saved' | 'failed' | 'stale' | 'loading';
  is_active: boolean;
}

export interface ArticleHistoryItem {
  title: string;
  url: string;
  char_count: number;
  chunks_count: number;
  type: string;
  loaded_at: number;
  last_accessed?: number;
  is_active: boolean;
}

export interface BackgroundTask {
  task_id: string;
  name: string;
  status: 'queued' | 'running' | 'completed' | 'failed';
  stage: string;
  progress: number;
  current_item: string;
  total_items: number;
  completed_items: number;
  failed_items: number;
  elapsed_seconds: number;
  errors: string[];
  result_message?: string;
}

export interface ConnectionTestResult {
  success: boolean;
  message: string;
  info?: {
    active_model?: string;
    latency_ms?: number;
    sdk?: string;
    status?: string;
  };
}

export interface RetrievedEvidence {
  ref_id: string;
  chunk_id: string;
  article_id?: string;
  title: string;
  section: string;
  url: string;
  source_type: string;
  similarity_score: number;
  score_explanation?: string;
  full_text: string;
  preview: string;
  char_count: number;
  token_count?: number;
  vector_coords: {
    x: number;
    y: number;
    z: number;
  };
  is_directly_cited?: boolean;
}

export interface PipelineStage {
  stage: 'QUERY' | 'UNDERSTAND' | 'RETRIEVE' | 'RERANK' | 'GENERATE' | 'CITE';
  title: string;
  description: string;
  time_ms: number;
}

export interface CitationData {
  total_retrieved: number;
  total_cited: number;
  cited_keys: string[];
  cards: RetrievedEvidence[];
}

export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  citations?: CitationData;
  evidences?: RetrievedEvidence[];
  stages?: PipelineStage[];
  elapsed_seconds?: number;
  timestamp: number;
  isError?: boolean;
}

export interface GraphNode {
  id: string;
  name: string;
  type: 'document' | 'chunk' | 'query';
  val: number;
  color: string;
  x: number;
  y: number;
  z: number;
  url?: string;
  char_count?: number;
  chunks_count?: number;
  is_retrieved?: boolean;
  section?: string;
  doc_title?: string;
  preview?: string;
}

export interface GraphLink {
  source: string;
  target: string;
  type: 'membership' | 'retrieval_ray';
  color: string;
  animated?: boolean;
}

export interface GraphData {
  nodes: GraphNode[];
  links: GraphLink[];
  stats: {
    total_nodes: number;
    total_links: number;
    documents: number;
    chunks: number;
    retrieved: number;
  };
}
