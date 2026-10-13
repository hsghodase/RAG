# Cognitive RAG 3D — Retrieval-Augmented Knowledge Universe

An intelligent, full-stack Retrieval-Augmented Generation (RAG) research workspace that connects Wikipedia knowledge into an interactive 3D semantic vector space. Built with high-precision vector search, factual Gemini synthesis, direct citation grounding, and WebGL knowledge visualization.

---

## 🌟 Key Features

- **Multi-Document Ingestion:** Search and ingest any Wikipedia article dynamically, with transactional parsing and clean section chunking.
- **Selective & Transactional Reloading:** Reload specific articles, refresh from Wikipedia for diffs, or re-embed without network overhead.
- **3D Semantic Vector Universe:** Real-time WebGL visualization of document clusters, chunk orbits, and retrieved citation rays using Three.js.
- **6-Stage Grounded Pipeline:**
  1. Semantic Query Encoding (`paraphrase-MiniLM-L3-v2`)
  2. High-Dimensional FAISS Vector Retrieval
  3. Dynamic Similarity Filtering & Budget Optimization
  4. Context Assembly & Prompt Grounding
  5. Gemini LLM Synthesis (`gemini-3.5-flash`, `gemini-3.1-flash-lite`, `gemini-3.8-flash`)
  6. Citation Extraction & Verification (`[REF-X]`)
- **Interactive Research Workspace:** 3-panel layout with real-time article filtering, evidence card inspection, similarity scores, and full context viewer.

---

## 🛠️ Tech Stack

- **Backend:** Python 3.10+, FastAPI, Uvicorn, Pydantic, FAISS, Sentence-Transformers, Google Gemini API
- **Frontend:** React 19, TypeScript, Vite, Tailwind CSS, Three.js, Lucide Icons

---

## 🚀 Quick Start Guide

### 1. Clone the Repository
```bash
git clone https://github.com/hsghodase/RAG.git
cd RAG
```

### 2. Configure Environment Variables
Copy `.env.example` to `.env` and add your Google Gemini API key:
```bash
cp .env.example .env
```
Edit `.env`:
```env
GEMINI_API_KEY=your_gemini_api_key_here
LLM_MODEL=gemini-3.5-flash
TEMPERATURE=0.3
TOP_K=5
SIMILARITY_THRESHOLD=0.20
CHUNK_SIZE=500
CHUNK_OVERLAP=75
```
> **Note:** Never commit your `.env` file containing real API keys.

### 3. Backend Setup
```bash
# Create and activate virtual environment
python -m venv venv
# Windows:
venv\Scripts\activate
# Linux/macOS:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Start FastAPI backend
python -m uvicorn backend.api.server:app --host 127.0.0.1 --port 8000 --reload
```
The backend API documentation will be available at `http://127.0.0.1:8000/docs`.

### 4. Frontend Setup
```bash
cd frontend
npm install
npm run dev
```
Open `http://localhost:8080` (or the port shown in terminal) to launch the application.

---

## 🧪 Testing

Run backend tests:
```bash
pytest tests/
```

Verify frontend build:
```bash
cd frontend
npm run build
```

---

## 🔒 Security & Privacy

- All sensitive credentials and API keys are strictly kept in `.env` (gitignored).
- Vector embeddings and cached content can be re-indexed locally on CPU or CUDA without leaking context.
- Sanitized client error handling ensures API keys are never exposed in responses or client state.
