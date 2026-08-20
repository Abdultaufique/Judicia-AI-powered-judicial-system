"""
JUDICIAL AI BACKEND – GEMINI CLOUD VERSION
==========================================
• Gemini 2.5 Flash via Google AI (free tier)
• RAG with FAISS + Google Embeddings
• 5-Agent Multi-Agent Reasoning Pipeline
• DuckDuckGo Web Search
• Deployable on Render.com (free tier)
"""

import os
import io
import sys
import re
import PyPDF2
from dotenv import load_dotenv

# Fix Windows emoji encoding (no-op on Linux/Render)
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from langchain_google_genai import ChatGoogleGenerativeAI, GoogleGenerativeAIEmbeddings
from langchain_core.messages import HumanMessage
from ddgs import DDGS

# FAISS vector store (optional — only loaded if vector_store exists)
try:
    from langchain_community.vectorstores import FAISS
    FAISS_AVAILABLE = True
except ImportError:
    FAISS_AVAILABLE = False
    print("ℹ️  FAISS not available — RAG disabled")

# --------------------------------------------------
# BASIC SETUP
# --------------------------------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(BASE_DIR)
load_dotenv()

from agents import MultiAgentOrchestrator

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "")

# --------------------------------------------------
# FASTAPI
# --------------------------------------------------
app = FastAPI(
    title="Judicial AI Backend",
    version="3.0.0",
    description="AI-powered legal judgment analysis — Gemini Cloud Edition"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# --------------------------------------------------
# GEMINI LLM (PRIMARY)
# --------------------------------------------------
llm = None
if GOOGLE_API_KEY:
    try:
        llm = ChatGoogleGenerativeAI(
            model="gemini-2.5-flash",
            temperature=0.3,
            google_api_key=GOOGLE_API_KEY,
            max_output_tokens=4096
        )
        # Quick connection test
        llm.invoke([HumanMessage(content="hi")])
        print("✅ Gemini 2.5 Flash connected")
    except Exception as e:
        print("❌ Gemini error:", e)
        llm = None
else:
    print("❌ GOOGLE_API_KEY not set — set it in Render environment variables!")

# --------------------------------------------------
# GEMINI EMBEDDINGS (for RAG)
# --------------------------------------------------
embeddings = None
if GOOGLE_API_KEY:
    try:
        embeddings = GoogleGenerativeAIEmbeddings(
            model="models/text-embedding-004",
            google_api_key=GOOGLE_API_KEY
        )
        print("✅ Google Embeddings ready (text-embedding-004)")
    except Exception as e:
        print("⚠️ Embeddings error:", e)

# --------------------------------------------------
# WEB SEARCH (DuckDuckGo via ddgs — no API key needed)
# --------------------------------------------------
def ddg_search(query: str, max_results: int = 5) -> list:
    """Direct DuckDuckGo search using ddgs library."""
    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=max_results))
            return results
    except Exception as e:
        print("⚠️ DuckDuckGo search error:", e)
        return []

print("✅ DuckDuckGo Search ready (ddgs)")

# --------------------------------------------------
# VECTOR DB (RAG) — optional, skip if not built
# --------------------------------------------------
VECTOR_PATH = os.path.join(BASE_DIR, "../data/vector_store")
vector_db = None
if embeddings and os.path.exists(VECTOR_PATH):
    try:
        vector_db = FAISS.load_local(
            VECTOR_PATH,
            embeddings,
            allow_dangerous_deserialization=True
        )
        print("✅ FAISS Vector DB loaded")
    except Exception as e:
        print("⚠️ Vector DB not found — running without RAG:", e)
else:
    print("ℹ️  No vector DB found — RAG disabled (still fully functional)")

# --------------------------------------------------
# DATA MODELS
# --------------------------------------------------
class WebQuery(BaseModel):
    query: str

# --------------------------------------------------
# HELPERS
# --------------------------------------------------
def extract_text_from_pdf(data: bytes) -> str:
    try:
        reader = PyPDF2.PdfReader(io.BytesIO(data))
        text = ""
        for page in reader.pages:
            extracted = page.extract_text()
            if extracted:
                text += extracted + "\n"
        return text[:12000]   # ~3000 tokens
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid or unreadable PDF file")

def extract_urls(raw: str) -> list:
    urls = re.findall(r'https?://[^\s,\]\'"]+', raw)
    cleaned = []
    for u in urls:
        u = re.sub(r'[,\]\)\}\'\"]$', '', u)
        if u.startswith("http") and len(u) > 20:
            cleaned.append(u)
    return cleaned[:5]

# --------------------------------------------------
# WEB SEARCH FUNCTION
# --------------------------------------------------
def web_search(query: str) -> dict:
    """
    Returns: {"answer": str, "sources": [{"title": str, "url": str, "snippet": str}]}
    """
    try:
        raw = ddg_search(query, max_results=5)
        if not raw:
            return {"answer": "No web sources found", "sources": []}

        sources = [
            {
                "title": r.get("title", f"Legal Source {i+1}"),
                "url": r.get("href", ""),
                "snippet": r.get("body", "Relevant legal information")
            }
            for i, r in enumerate(raw) if r.get("href")
        ]

        if not sources:
            return {"answer": "No usable web sources found", "sources": []}

        # Use Gemini to summarize if available
        if llm:
            snippets = "\n".join([f"- {s['title']}: {s['snippet'][:200]}" for s in sources])
            prompt = f"""You are a legal research assistant.
Query: {query}
Search Results:
{snippets}
Provide a concise legal analysis (2 paragraphs max)."""
            response = llm.invoke(prompt)
            answer = response.content.strip()
        else:
            answer = f"Found {len(sources)} sources."

        return {"answer": answer, "sources": sources}

    except Exception as e:
        return {"answer": f"Web search error: {str(e)}", "sources": []}

# --------------------------------------------------
# MULTI-AGENT SYSTEM
# --------------------------------------------------
multi_agent = None
if llm:
    try:
        multi_agent = MultiAgentOrchestrator(
            llm=llm,
            web_search_function=web_search
        )
        print("✅ 5-Agent pipeline initialized")
    except Exception as e:
        print("❌ Multi-Agent failed:", e)

# --------------------------------------------------
# CORE ANALYSIS
# --------------------------------------------------
def run_analysis(text: str) -> dict:
    # RAG context retrieval
    context = ""
    if vector_db:
        try:
            docs = vector_db.similarity_search(text[:2000], k=3)
            context = "\n".join(d.page_content for d in docs)
        except Exception as e:
            print("⚠️ RAG search error:", e)

    if not multi_agent:
        return {
            "summary": "Backend not configured. Please set GOOGLE_API_KEY.",
            "analysis": "",
            "laws": "",
            "web_sources": []
        }

    return multi_agent.run(judgment_text=text, rag_context=context)

# --------------------------------------------------
# API ENDPOINTS
# --------------------------------------------------
@app.post("/analyze")
async def analyze_pdf(file: UploadFile = File(...)):
    """Upload a legal judgment PDF for AI analysis."""
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported")

    data = await file.read()
    if len(data) > 20 * 1024 * 1024:  # 20MB limit
        raise HTTPException(status_code=413, detail="PDF too large (max 20MB)")

    text = extract_text_from_pdf(data)
    if len(text.strip()) < 100:
        raise HTTPException(status_code=400, detail="PDF appears to be empty or unreadable")

    result = run_analysis(text)

    return {
        "filename": file.filename,
        "summary": result.get("summary", ""),
        "laws": result.get("laws", ""),
        "analysis": result.get("analysis", ""),
        "web_sources": result.get("web_sources", []),
        "characters_processed": len(text)
    }

@app.post("/web-search")
def manual_web_search(query: WebQuery):
    """Perform a legal web search query."""
    return web_search(query.query)

@app.get("/health")
def health():
    """Health check endpoint for Render."""
    return {
        "status": "online",
        "version": "3.0.0",
        "llm": "gemini-2.5-flash" if llm else "not configured",
        "gemini": bool(llm),
        "embeddings": bool(embeddings),
        "vector_db": bool(vector_db),
        "multi_agent": bool(multi_agent),
        "web_search": bool(search_tool)
    }

@app.get("/")
def root():
    """Root endpoint."""
    return {
        "message": "Judicial AI Backend v3.0 — Gemini Edition",
        "docs": "/docs",
        "health": "/health"
    }

# --------------------------------------------------
# STARTUP EVENT
# --------------------------------------------------
@app.on_event("startup")
async def startup():
    print("\n" + "="*60)
    print("  JUDICIAL AI BACKEND v3.0 — GEMINI CLOUD EDITION")
    print("="*60)
    print(f"  LLM:        {'Gemini 2.5 Flash' if llm else 'NOT CONFIGURED'}")
    print(f"  Embeddings: {'Google text-embedding-004' if embeddings else 'Disabled'}")
    print(f"  Vector DB:  {'FAISS loaded' if vector_db else 'Not loaded'}")
    print(f"  Agents:     {'5-agent pipeline' if multi_agent else 'Not initialized'}")
    print(f"  Web Search: {'DuckDuckGo active' if search_tool else 'Disabled'}")
    print("="*60)
    print("  API Docs: /docs")
    print("="*60 + "\n")

# --------------------------------------------------
# RUN (local dev only — Render uses uvicorn directly)
# --------------------------------------------------
if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
