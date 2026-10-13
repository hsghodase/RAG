import os
import time
from pathlib import Path
import streamlit as st

# Environment setup
os.environ['TOKENIZERS_PARALLELISM'] = 'false'

from backend.config import settings, update_settings, CACHE_DIR
from backend.rag.engine import rag_engine
from backend.rag.generation import RAGGenerator

# Page setup
st.set_page_config(
    page_title="Cognitive RAG Universe — 3D Research Platform",
    page_icon="🌌",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom Styling (Dark spatial AI lab aesthetic)
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;500;600;700&family=Inter:wght@300;400;500;600&display=swap');

* {
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
}

h1, h2, h3, h4 {
    font-family: 'Space Grotesk', sans-serif;
    letter-spacing: -0.02em;
}

/* Base Dark Theme */
.stApp {
    background: radial-gradient(circle at 50% 0%, #0d1527 0%, #050811 100%);
    color: #e2e8f0;
}

/* Hero Badge */
.hero-badge {
    display: inline-flex;
    align-items: center;
    gap: 8px;
    background: rgba(6, 182, 212, 0.1);
    border: 1px solid rgba(6, 182, 212, 0.3);
    color: #38bdf8;
    padding: 6px 14px;
    border-radius: 9999px;
    font-size: 0.85rem;
    font-weight: 500;
    margin-bottom: 12px;
}

.hero-title {
    font-size: 2.6rem;
    font-weight: 700;
    background: linear-gradient(135deg, #ffffff 0%, #94a3b8 50%, #38bdf8 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    margin-bottom: 0.5rem;
}

.hero-subtitle {
    color: #94a3b8;
    font-size: 1.05rem;
    margin-bottom: 1.5rem;
}

/* Glassmorphism Cards */
.glass-panel {
    background: rgba(15, 23, 42, 0.7);
    backdrop-filter: blur(16px);
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 14px;
    padding: 1.25rem;
    margin-bottom: 1rem;
    box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.37);
}

/* Pipeline Stage Ribbon */
.pipeline-container {
    display: flex;
    align-items: center;
    gap: 8px;
    background: rgba(15, 23, 42, 0.8);
    border: 1px solid rgba(56, 189, 248, 0.2);
    border-radius: 12px;
    padding: 10px 16px;
    margin: 16px 0;
    overflow-x: auto;
}

.pipeline-step {
    display: flex;
    align-items: center;
    gap: 6px;
    color: #38bdf8;
    font-weight: 600;
    font-size: 0.85rem;
}

.pipeline-arrow {
    color: #475569;
    font-size: 0.9rem;
}

/* Source Reference Cards */
.source-card {
    background: rgba(30, 41, 59, 0.6);
    border: 1px solid rgba(255, 255, 255, 0.07);
    border-left: 3px solid #06b6d4;
    border-radius: 10px;
    padding: 1rem;
    margin: 0.75rem 0;
    transition: all 0.2s ease;
}

.source-card:hover {
    border-color: rgba(6, 182, 212, 0.4);
    transform: translateY(-2px);
    box-shadow: 0 4px 20px rgba(6, 182, 212, 0.15);
}

/* Custom Scrollbars */
::-webkit-scrollbar {
    width: 6px;
    height: 6px;
}
::-webkit-scrollbar-thumb {
    background: rgba(100, 116, 139, 0.4);
    border-radius: 4px;
}
::-webkit-scrollbar-thumb:hover {
    background: rgba(148, 163, 184, 0.6);
}
</style>
""", unsafe_allow_html=True)

# Session State Initialization
for key, default in [
    ('chat_history', []),
    ('current_articles', []),
    ('active_citations', None),
    ('active_stages', None),
    ('loading_status', 'idle'),
]:
    if key not in st.session_state:
        st.session_state[key] = default

# Sync RAG engine state with session state
if rag_engine.doc_titles and not st.session_state.current_articles:
    st.session_state.current_articles = rag_engine.doc_titles

# Top Header
col_h1, col_h2 = st.columns([3, 1])
with col_h1:
    st.markdown('<div class="hero-badge">🌌 KNOWLEDGE AS A 3D UNIVERSE · RAG 2.0</div>', unsafe_allow_html=True)
    st.markdown('<h1 class="hero-title">Cognitive Research Workspace</h1>', unsafe_allow_html=True)
    st.markdown('<p class="hero-subtitle">Turn knowledge into grounded answers with vector retrieval, citations, and semantic spatial intelligence.</p>', unsafe_allow_html=True)

with col_h2:
    has_key = bool(settings.gemini_api_key)
    docs_count = len(rag_engine.doc_titles)
    st.markdown(f"""
    <div class="glass-panel" style="text-align: right; padding: 0.9rem;">
        <div style="font-size: 0.8rem; color: #94a3b8;">SYSTEM STATUS</div>
        <div style="color: {'#10b981' if has_key else '#f59e0b'}; font-weight: 600; font-size: 0.95rem;">
            {'● RAG Engine Online' if has_key else '▲ API Key Required'}
        </div>
        <div style="font-size: 0.8rem; color: #64748b; margin-top: 4px;">
            {docs_count} Documents · {len(rag_engine.chunk_nodes)} Chunks
        </div>
    </div>
    """, unsafe_allow_html=True)

# API Configuration if missing
if not settings.gemini_api_key:
    with st.expander("🔑 Google Gemini API Configuration", expanded=True):
        st.markdown("Enter your Gemini API key from [Google AI Studio](https://aistudio.google.com/) to activate grounded research generation.")
        col_k1, col_k2 = st.columns([4, 1])
        with col_k1:
            key_input = st.text_input("Gemini API Key:", type="password", placeholder="AIzaSy...", label_visibility="collapsed")
        with col_k2:
            if st.button("Save Key", type="primary", use_container_width=True):
                if key_input.strip():
                    update_settings(gemini_api_key=key_input.strip())
                    st.success("API key configured!")
                    time.sleep(1)
                    st.rerun()

# Sidebar Navigation & Source Management
with st.sidebar:
    st.markdown("### ◈ Knowledge Sources")
    st.markdown("Load Wikipedia articles into vector space")
    
    custom_input = st.text_area(
        "Wikipedia Articles (comma-separated):",
        placeholder="Artificial Intelligence, Machine Learning, Deep Learning",
        height=100
    )
    
    if st.button("📥 Ingest & Build Index", type="primary", use_container_width=True):
        if custom_input.strip():
            articles = [a.strip() for a in custom_input.split(",") if a.strip()]
            with st.spinner(f"Ingesting {len(articles)} articles and creating vector index..."):
                success, msg, status_map = rag_engine.ingest_wikipedia_articles(articles)
                if success:
                    st.session_state.current_articles = rag_engine.doc_titles
                    st.success(msg)
                    st.rerun()
                else:
                    st.error(msg)
        else:
            st.warning("Please enter article titles.")
            
    st.markdown("---")
    
    # Quick Topics
    st.markdown("#### ⚡ Quick Start Topics")
    topics = {
        "AI & ML": ["Artificial Intelligence", "Machine Learning", "Deep Learning"],
        "Science": ["Physics", "Chemistry", "Biology"],
        "Quantum": ["Quantum computing", "Quantum mechanics", "Qubit"],
        "Economics": ["Economics", "Inflation", "Monetary Policy"],
    }
    
    for t_name, t_arts in topics.items():
        if st.button(f"◉ {t_name}", use_container_width=True):
            with st.spinner(f"Ingesting {t_name} knowledge cluster..."):
                success, msg, _ = rag_engine.ingest_wikipedia_articles(t_arts)
                if success:
                    st.session_state.current_articles = rag_engine.doc_titles
                    st.success(msg)
                    st.rerun()
                else:
                    st.error(msg)
                    
    st.markdown("---")
    
    # Loaded Articles List
    if rag_engine.doc_titles:
        st.markdown(f"#### 📚 Loaded Documents ({len(rag_engine.doc_titles)})")
        for doc in rag_engine.doc_metadata_list:
            title = doc["title"]
            url = doc.get("url", f"https://en.wikipedia.org/wiki/{title.replace(' ', '_')}")
            chunks = doc.get("chunks_count", 0)
            st.markdown(f"• [{title}]({url}) `({chunks} chunks)`")
            
        st.markdown("---")
        
    # Actions
    col_a1, col_a2 = st.columns(2)
    with col_a1:
        if st.button("Clear Chat", use_container_width=True):
            rag_engine.clear_chat()
            st.session_state.chat_history = []
            st.rerun()
    with col_a2:
        if st.button("Clear Cache", use_container_width=True):
            success, msg = rag_engine.clear_cache()
            if success:
                st.success(msg)
                time.sleep(1)
                st.rerun()

# Main Workspace Layout: Two large interactive columns (Research Chat on Left/Center, Evidence Panel on Right)
col_chat, col_evidence = st.columns([5, 4])

with col_chat:
    st.markdown("### 💬 Grounded AI Research")
    
    # Query input
    with st.form("query_form", clear_on_submit=True):
        col_q1, col_q2 = st.columns([5, 1])
        with col_q1:
            user_query = st.text_input(
                "Ask anything about your knowledge base...",
                placeholder="What are the fundamental architectures of generative AI?",
                label_visibility="collapsed"
            )
        with col_q2:
            submitted = st.form_submit_button("Research", type="primary", use_container_width=True)

    if submitted and user_query.strip():
        if not rag_engine.index:
            st.warning("Please load or select a knowledge topic first.")
        else:
            with st.spinner("Executing 6-Stage RAG Pipeline..."):
                res = rag_engine.query_rag(user_query.strip())
                if res.get("success"):
                    st.session_state.active_stages = res.get("stages")
                    st.session_state.active_citations = res.get("citations")
                    st.rerun()
                else:
                    st.error(res.get("error", "Query execution failed."))

    # Show active RAG pipeline ribbon if stages exist
    if st.session_state.active_stages:
        stages = st.session_state.active_stages
        st.markdown(f"""
        <div class="pipeline-container">
            <span class="pipeline-step">🔍 1. QUERY</span>
            <span class="pipeline-arrow">→</span>
            <span class="pipeline-step">🧠 2. UNDERSTAND</span>
            <span class="pipeline-arrow">→</span>
            <span class="pipeline-step">⚡ 3. RETRIEVE ({len(rag_engine.last_retrieved)} chunks)</span>
            <span class="pipeline-arrow">→</span>
            <span class="pipeline-step">🎯 4. RERANK</span>
            <span class="pipeline-arrow">→</span>
            <span class="pipeline-step">✨ 5. GENERATE</span>
            <span class="pipeline-arrow">→</span>
            <span class="pipeline-step">📑 6. CITE</span>
        </div>
        """, unsafe_allow_html=True)

    # Chat history display
    if rag_engine.chat_history:
        for idx, entry in enumerate(reversed(rag_engine.chat_history)):
            with st.chat_message("user"):
                st.write(entry["query"])
            with st.chat_message("assistant"):
                st.markdown(entry["answer"])
                st.caption(f"⏱️ Generated in {entry.get('elapsed_seconds', 0)}s via {settings.llm_model} · {entry.get('citations', {}).get('total_cited', 0)} citations")
    else:
        st.info("💡 **Ready to Research.** Ask any question above or choose a Quick Start Topic from the sidebar to inspect vector evidence.")

# Right Column: Evidence & Source Inspection Panel
with col_evidence:
    st.markdown("### 📑 Evidence & Retrieval Panel")
    
    if rag_engine.last_retrieved:
        st.markdown(f"**Retrieved {len(rag_engine.last_retrieved)} relevant chunks** from vector space:")
        
        for ev in rag_engine.last_retrieved:
            score = ev.similarity_score
            st.markdown(f"""
            <div class="source-card">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px;">
                    <span style="font-weight: 600; color: #38bdf8;">[{ev.ref_id}] {ev.title}</span>
                    <span style="background: rgba(16, 185, 129, 0.15); color: #10b981; padding: 2px 8px; border-radius: 6px; font-size: 0.8rem; font-weight: 600;">
                        Score: {score:.4f}
                    </span>
                </div>
                <div style="font-size: 0.8rem; color: #94a3b8; margin-bottom: 6px;">
                    Section: <b>{ev.section}</b> · ID: <code>{ev.chunk_id}</code>
                </div>
                <div style="font-size: 0.85rem; color: #cbd5e1; font-style: italic; line-height: 1.5;">
                    "{ev.preview}"
                </div>
            </div>
            """, unsafe_allow_html=True)
            
            with st.expander(f"Inspect Full Context [{ev.ref_id}]", expanded=False):
                st.markdown(f"**Source URL:** [{ev.url}]({ev.url})")
                st.text_area(f"Full Text ({ev.char_count} chars):", value=ev.full_text, height=180, key=f"src_txt_{ev.chunk_id}")
    else:
        st.markdown("""
        <div class="glass-panel" style="text-align: center; padding: 2rem;">
            <div style="font-size: 2.5rem; margin-bottom: 10px;">🪐</div>
            <div style="font-weight: 600; font-size: 1.1rem; color: #e2e8f0;">No Vector Evidence Retrieved Yet</div>
            <p style="color: #64748b; font-size: 0.9rem; margin-top: 6px;">
                Ask a question to see semantic similarity scores, section context, and cited source passages in real-time.
            </p>
        </div>
        """, unsafe_allow_html=True)