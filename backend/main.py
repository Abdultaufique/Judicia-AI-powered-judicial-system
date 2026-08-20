"""
JUDICIAL AI BACKEND — DYNAMIC GEMINI REST API & 5-AGENT SYSTEM + RAG
=====================================================================
• Calls Gemini API directly via httpx (no SDK, no Rust/C++ builds)
• Auto-discovers and auto-verifies working models from Google API
• Dynamic automatic failover across models (2.0-flash, 1.5-flash-002, 1.5-pro, etc.)
• 5-Agent Multi-Agent Reasoning Pipeline
• RAG: TF-IDF retrieval from Indian laws & precedents knowledge base
• Real-time DuckDuckGo Web Research
• Lightweight SQLite History persistence (zero external dependencies)
• Works on Python 3.8–3.14+, any platform (Render / Linux / Windows / macOS)
"""

import os
import io
import sys
import re
import json
import sqlite3
import datetime
from typing import List, Optional, Dict, Any

import httpx
import PyPDF2
from dotenv import load_dotenv
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# Fix Windows encoding (no-op on Linux/Render)
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

from agents import MultiAgentOrchestrator, LLMResponse
from rag_utils import LightweightRAG

# ─── Config ───────────────────────────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(BASE_DIR)
load_dotenv()

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "").strip()
DB_PATH = os.path.join(BASE_DIR, "judicial_ai.db")

# ─── SQLite History Storage (Zero External Dependencies) ───────────────────────
def init_db():
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS analyses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                filename TEXT NOT NULL,
                upload_date TEXT NOT NULL,
                summary TEXT,
                laws TEXT,
                analysis TEXT,
                web_sources TEXT,
                characters_processed INTEGER DEFAULT 0,
                precedents TEXT,
                logic_audit TEXT,
                rag_sources TEXT
            )
        """)
        conn.commit()

        # Migration: Add new columns to existing DB if they don't exist
        existing_cols = [row[1] for row in cursor.execute("PRAGMA table_info(analyses)").fetchall()]
        for col_name, col_type in [("precedents", "TEXT"), ("logic_audit", "TEXT"), ("rag_sources", "TEXT")]:
            if col_name not in existing_cols:
                try:
                    cursor.execute(f"ALTER TABLE analyses ADD COLUMN {col_name} {col_type}")
                    print(f"[DB] Added column: {col_name}")
                except Exception:
                    pass
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"[WARN] DB init warning: {e}")

init_db()

def save_analysis_record(
    filename: str, summary: str, laws: str, analysis: str,
    web_sources: list, char_count: int,
    precedents: str = "", logic_audit: str = "", rag_sources: list = None
) -> int:
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        now = datetime.datetime.utcnow().isoformat() + "Z"
        sources_json = json.dumps(web_sources)
        rag_json = json.dumps(rag_sources or [])
        cursor.execute("""
            INSERT INTO analyses (filename, upload_date, summary, laws, analysis, web_sources, characters_processed, precedents, logic_audit, rag_sources)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (filename, now, summary, laws, analysis, sources_json, char_count, precedents, logic_audit, rag_json))
        record_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return record_id
    except Exception as e:
        print(f"[WARN] Could not save analysis to DB: {e}")
        return 0

def fetch_history_records(limit: int = 50) -> list:
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, filename, upload_date, summary, laws, analysis, web_sources, characters_processed,
                   precedents, logic_audit, rag_sources
            FROM analyses
            ORDER BY id DESC
            LIMIT ?
        """, (limit,))
        rows = cursor.fetchall()
        results = []
        for r in rows:
            sources = []
            try:
                sources = json.loads(r["web_sources"]) if r["web_sources"] else []
            except Exception:
                sources = []
            rag_src = []
            try:
                rag_src = json.loads(r["rag_sources"]) if r["rag_sources"] else []
            except Exception:
                rag_src = []
            results.append({
                "id": r["id"],
                "filename": r["filename"],
                "upload_date": r["upload_date"],
                "summary": r["summary"] or "",
                "laws": r["laws"] or "",
                "analysis": r["analysis"] or "",
                "precedents": r["precedents"] or "",
                "logic_audit": r["logic_audit"] or "",
                "web_sources": sources,
                "rag_sources": rag_src,
                "characters_processed": r["characters_processed"] or 0
            })
        conn.close()
        return results
    except Exception as e:
        print(f"[WARN] Could not fetch history: {e}")
        return []

def fetch_analysis_by_id(record_id: int) -> Optional[dict]:
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, filename, upload_date, summary, laws, analysis, web_sources, characters_processed,
                   precedents, logic_audit, rag_sources
            FROM analyses
            WHERE id = ?
        """, (record_id,))
        row = cursor.fetchone()
        conn.close()
        if not row:
            return None
        sources = []
        try:
            sources = json.loads(row["web_sources"]) if row["web_sources"] else []
        except Exception:
            sources = []
        rag_src = []
        try:
            rag_src = json.loads(row["rag_sources"]) if row["rag_sources"] else []
        except Exception:
            rag_src = []
        return {
            "id": row["id"],
            "filename": row["filename"],
            "upload_date": row["upload_date"],
            "summary": row["summary"] or "",
            "laws": row["laws"] or "",
            "analysis": row["analysis"] or "",
            "precedents": row["precedents"] or "",
            "logic_audit": row["logic_audit"] or "",
            "web_sources": sources,
            "rag_sources": rag_src,
            "characters_processed": row["characters_processed"] or 0
        }
    except Exception as e:
        print(f"[WARN] Could not fetch analysis by ID: {e}")
        return None

# ─── Robust Dynamic Gemini REST Client ────────────────────────────────────────
GEMINI_BASE = "https://generativelanguage.googleapis.com"

# Candidate models in priority order
CANDIDATE_MODELS = [
    "gemini-2.0-flash",
    "gemini-2.0-flash-exp",
    "gemini-1.5-flash",
    "gemini-1.5-flash-002",
    "gemini-1.5-flash-001",
    "gemini-1.5-flash-latest",
    "gemini-1.5-flash-8b",
    "gemini-1.5-pro",
    "gemini-1.5-pro-002",
    "gemini-1.5-pro-001",
    "gemini-1.5-pro-latest",
    "gemini-1.0-pro",
    "gemini-pro",
]


class GeminiRESTClient:
    """
    Direct REST API client for Google Gemini.
    Features:
    - Auto-discovers all available models for the provided API key via ListModels
    - Auto-probes and verifies active generation capability
    - Fallback failover across candidate models if any model returns 404 or errors
    """

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.model: Optional[str] = None
        self.version: str = "v1beta"
        self._url: Optional[str] = None
        self.discovered_models: List[str] = []
        self.probe_log: List[Dict[str, Any]] = []

        if self.api_key:
            self.discover()

    def _build_url(self, model: str, version: str = "v1beta") -> str:
        # Strip leading "models/" if present
        clean_model = model.replace("models/", "")
        return f"{GEMINI_BASE}/{version}/models/{clean_model}:generateContent"

    def list_remote_models(self) -> List[str]:
        """Fetch all models supporting generateContent from Google API."""
        found = []
        for ver in ["v1beta", "v1"]:
            try:
                resp = httpx.get(
                    f"{GEMINI_BASE}/{ver}/models",
                    params={"key": self.api_key},
                    timeout=10.0
                )
                if resp.status_code == 200:
                    data = resp.json()
                    for m in data.get("models", []):
                        name = m.get("name", "")
                        methods = m.get("supportedGenerationMethods", [])
                        if "generateContent" in methods and name:
                            clean_name = name.replace("models/", "")
                            if clean_name not in found:
                                found.append(clean_name)
            except Exception as e:
                print(f"[WARN] ListModels ({ver}) error: {e}")
        return found

    def _probe_model(self, model: str, version: str) -> bool:
        """Send a minimal test request to verify the model responds."""
        url = self._build_url(model, version)
        payload = {
            "contents": [{"parts": [{"text": "Hello"}]}],
            "generationConfig": {"maxOutputTokens": 5}
        }
        try:
            resp = httpx.post(
                url,
                json=payload,
                params={"key": self.api_key},
                headers={"Content-Type": "application/json"},
                timeout=12.0
            )
            success = (resp.status_code == 200)
            self.probe_log.append({
                "model": model,
                "version": version,
                "status_code": resp.status_code,
                "success": success
            })
            if success:
                print(f"[OK] Gemini Model Verified: {model} ({version})")
                return True
            else:
                print(f"[SKIP] Gemini {model} ({version}) -> HTTP {resp.status_code}")
        except Exception as e:
            self.probe_log.append({
                "model": model,
                "version": version,
                "status_code": None,
                "error": str(e),
                "success": False
            })
            print(f"[SKIP] Gemini {model} ({version}) -> {e}")
        return False

    def discover(self) -> bool:
        """Discover and verify the best available model for this API key."""
        if not self.api_key:
            return False

        # 1. Fetch remote list of models
        remote_models = self.list_remote_models()
        self.discovered_models = remote_models

        # 2. Build candidate sequence (discovered prioritized + static fallbacks)
        ordered_candidates = []
        for cand in CANDIDATE_MODELS:
            if cand in remote_models and cand not in ordered_candidates:
                ordered_candidates.append(cand)
        for rem in remote_models:
            if rem not in ordered_candidates:
                ordered_candidates.append(rem)
        for cand in CANDIDATE_MODELS:
            if cand not in ordered_candidates:
                ordered_candidates.append(cand)

        # 3. Probe until one works
        for model in ordered_candidates:
            for ver in ["v1beta", "v1"]:
                if self._probe_model(model, ver):
                    self.model = model
                    self.version = ver
                    self._url = self._build_url(model, ver)
                    return True

        print("[ERR] Could not discover any functioning Gemini model for the provided API key.")
        return False

    def generate(self, prompt: str) -> str:
        """
        Generate text via Gemini REST API with automatic failover.
        """
        if not self._url:
            if not self.discover():
                raise RuntimeError(
                    "No working Gemini model available. Please verify your GOOGLE_API_KEY in Render settings."
                )

        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": 0.3,
                "maxOutputTokens": 4096
            }
        }

        # Try current model
        try:
            resp = httpx.post(
                self._url,
                json=payload,
                params={"key": self.api_key},
                headers={"Content-Type": "application/json"},
                timeout=120.0
            )
            if resp.status_code == 200:
                data = resp.json()
                candidates = data.get("candidates", [])
                if candidates:
                    parts = candidates[0].get("content", {}).get("parts", [])
                    if parts:
                        return parts[0].get("text", "")
                return "Analysis completed, but no text output was generated by the model."
            else:
                print(f"[WARN] Active model {self.model} returned HTTP {resp.status_code}: {resp.text[:200]}")
        except Exception as e:
            print(f"[WARN] Error calling active model {self.model}: {e}")

        # If active model failed, try re-discovering / failover
        print("[INFO] Attempting automatic Gemini model failover...")
        if self.discover():
            try:
                resp = httpx.post(
                    self._url,
                    json=payload,
                    params={"key": self.api_key},
                    headers={"Content-Type": "application/json"},
                    timeout=120.0
                )
                resp.raise_for_status()
                data = resp.json()
                candidates = data.get("candidates", [])
                if candidates:
                    parts = candidates[0].get("content", {}).get("parts", [])
                    if parts:
                        return parts[0].get("text", "")
            except Exception as e:
                raise RuntimeError(f"Gemini failover request failed: {str(e)}")

        raise RuntimeError(f"Gemini API request failed for model {self.model}. Check API key and quota.")


# ─── LLM Wrapper (agents.py compatible) ───────────────────────────────────────
class GeminiLLM:
    """Wraps GeminiRESTClient with invoke() interface for agents."""

    def __init__(self, client: GeminiRESTClient):
        self.client = client

    def invoke(self, prompt) -> LLMResponse:
        if isinstance(prompt, list):
            text = "\n".join(
                m.content if hasattr(m, "content") else str(m)
                for m in prompt
            )
        else:
            text = str(prompt)

        try:
            result = self.client.generate(text)
            return LLMResponse(result)
        except Exception as e:
            return LLMResponse(f"[LLM Error: {str(e)}]")


# ─── Global LLM, RAG & Agents Initialization ──────────────────────────────────
gemini_rest: Optional[GeminiRESTClient] = None
llm: Optional[GeminiLLM] = None
multi_agent: Optional[MultiAgentOrchestrator] = None
rag_engine: Optional[LightweightRAG] = None

def init_services():
    global gemini_rest, llm, multi_agent, rag_engine, GOOGLE_API_KEY
    GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "").strip()

    # Initialize RAG engine (independent of API key)
    try:
        rag_engine = LightweightRAG()
        print(f"[OK] RAG Engine initialized: {rag_engine.num_chunks} chunks indexed")
    except Exception as e:
        print(f"[WARN] RAG initialization failed (non-critical): {e}")
        rag_engine = None

    # Initialize Gemini + Multi-Agent
    if GOOGLE_API_KEY:
        try:
            gemini_rest = GeminiRESTClient(api_key=GOOGLE_API_KEY)
            llm = GeminiLLM(gemini_rest)
            multi_agent = MultiAgentOrchestrator(llm=llm, web_search_function=web_search)
            print(f"[OK] 5-Agent pipeline initialized with model: {gemini_rest.model}")
        except Exception as e:
            print(f"[ERR] Service initialization error: {e}")
    else:
        print("[WARN] GOOGLE_API_KEY not found in environment variables.")

# ─── DuckDuckGo Search (raw httpx) ───────────────────────────────────────────
def ddg_search(query: str, max_results: int = 5) -> list:
    """Direct DuckDuckGo Lite HTML scrape via httpx."""
    try:
        resp = httpx.post(
            "https://html.duckduckgo.com/html/",
            data={"q": query, "b": ""},
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) JudiciaAI/5.0"},
            timeout=12.0,
            follow_redirects=True
        )
        titles   = re.findall(r'class="result__a"[^>]*>([^<]+)</a>', resp.text)
        urls     = re.findall(r'class="result__url"[^>]*>\s*([^\s<]+)', resp.text)
        snippets = re.findall(r'class="result__snippet"[^>]*>([^<]+)</a>', resp.text)

        results = []
        for i in range(min(max_results, len(titles), len(urls))):
            raw_url = urls[i].strip()
            if not raw_url.startswith("http"):
                raw_url = "https://" + raw_url.lstrip("/")
            results.append({
                "title": titles[i].strip(),
                "href":  raw_url,
                "body":  snippets[i].strip() if i < len(snippets) else ""
            })
        return results
    except Exception as e:
        print(f"[WARN] DDG search error: {e}")
        return []


def web_search(query: str) -> dict:
    """Returns {answer, sources} dict."""
    try:
        raw = ddg_search(query)
        if not raw:
            return {"answer": "No web sources found for this query.", "sources": []}

        sources = [
            {
                "title":   r.get("title",  f"Source {i+1}"),
                "url":     r.get("href",   ""),
                "snippet": r.get("body",   "")[:300]
            }
            for i, r in enumerate(raw) if r.get("href")
        ]

        if not sources:
            return {"answer": "No usable web sources found.", "sources": []}

        if llm:
            snippets_text = "\n".join([
                f"- {s['title']}: {s['snippet']}" for s in sources[:3]
            ])
            prompt = (
                f"Legal research query: {query}\n"
                f"Search results:\n{snippets_text}\n"
                f"Provide a concise 2-paragraph legal analysis referencing the findings."
            )
            answer = llm.invoke(prompt).content.strip()
        else:
            answer = f"Found {len(sources)} relevant web sources."

        return {"answer": answer, "sources": sources}

    except Exception as e:
        return {"answer": f"Search error: {str(e)}", "sources": []}


# ─── FastAPI App ──────────────────────────────────────────────────────────────
app = FastAPI(
    title="Judicial AI — Gemini REST Backend + RAG",
    version="6.0.0",
    description="AI-powered legal analysis via Gemini REST API, Multi-Agent reasoning & RAG"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── Helpers ──────────────────────────────────────────────────────────────────
def extract_text_from_pdf(data: bytes) -> str:
    try:
        reader = PyPDF2.PdfReader(io.BytesIO(data))
        text = ""
        for page in reader.pages:
            t = page.extract_text()
            if t:
                text += t + "\n"
        return text[:15000]
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid or unreadable PDF document.")


def run_analysis(text: str) -> dict:
    global multi_agent, gemini_rest, llm, rag_engine
    if not multi_agent:
        init_services()
    if not multi_agent:
        return {
            "summary": "Backend not configured — GOOGLE_API_KEY is missing or invalid in Render Environment settings.",
            "laws": "No laws identified (Gemini API key missing).",
            "analysis": "Please configure GOOGLE_API_KEY in the deployment environment variables to enable AI analysis.",
            "precedents": "",
            "logic_audit": "",
            "web_sources": [],
            "rag_sources": []
        }

    # ─── RAG Retrieval ────────────────────────────────────────────────────
    rag_context = ""
    rag_sources = []
    if rag_engine and rag_engine.is_ready:
        try:
            rag_result = rag_engine.retrieve_for_judgment(text)
            rag_context = rag_result.get("context", "")
            rag_sources = rag_result.get("sources", [])
            print(f"[RAG] Retrieved {len(rag_sources)} relevant chunks for this judgment")
        except Exception as e:
            print(f"[WARN] RAG retrieval error (non-critical): {e}")

    # ─── Run Multi-Agent Pipeline ─────────────────────────────────────────
    result = multi_agent.run(judgment_text=text, rag_context=rag_context)
    result["rag_sources"] = rag_sources
    return result


# ─── API Endpoints ────────────────────────────────────────────────────────────
class WebQuery(BaseModel):
    query: str


@app.post("/analyze")
async def analyze_pdf(file: UploadFile = File(...)):
    """Analyze a legal judgment PDF and save to history."""
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported.")

    data = await file.read()
    if len(data) > 25 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="PDF is too large (maximum size is 25 MB).")

    text = extract_text_from_pdf(data)
    if len(text.strip()) < 30:
        raise HTTPException(status_code=400, detail="PDF contains insufficient readable text.")

    result = run_analysis(text)

    summary = result.get("summary", "")
    laws = result.get("laws", "")
    analysis = result.get("analysis", "")
    precedents = result.get("precedents", "")
    logic_audit = result.get("logic_audit", "")
    web_sources = result.get("web_sources", [])
    rag_sources = result.get("rag_sources", [])

    # Save to SQLite history
    record_id = save_analysis_record(
        filename=file.filename,
        summary=summary,
        laws=laws,
        analysis=analysis,
        web_sources=web_sources,
        char_count=len(text),
        precedents=precedents,
        logic_audit=logic_audit,
        rag_sources=rag_sources
    )

    return {
        "id":                   record_id,
        "filename":             file.filename,
        "summary":              summary,
        "laws":                 laws,
        "analysis":             analysis,
        "precedents":           precedents,
        "logic_audit":          logic_audit,
        "web_sources":          web_sources,
        "rag_sources":          rag_sources,
        "characters_processed": len(text)
    }


@app.get("/history")
def get_history():
    """Retrieve list of past document analyses."""
    return fetch_history_records(limit=50)


@app.get("/history/{record_id}")
def get_history_by_id(record_id: int):
    """Retrieve a specific past analysis by ID."""
    record = fetch_analysis_by_id(record_id)
    if not record:
        raise HTTPException(status_code=404, detail="Analysis record not found.")
    return record


@app.post("/web-search")
def manual_search(query: WebQuery):
    """Run a legal web search with DuckDuckGo and LLM synthesis."""
    if not query.query.strip():
        raise HTTPException(status_code=400, detail="Query cannot be empty.")
    return web_search(query.query.strip())


@app.get("/health")
def health():
    """Health check endpoint used by Render and frontend."""
    return {
        "status":      "online",
        "version":     "6.0.0",
        "gemini":      bool(gemini_rest and gemini_rest.model),
        "multi_agent": bool(multi_agent),
        "rag":         bool(rag_engine and rag_engine.is_ready),
        "rag_chunks":  rag_engine.num_chunks if rag_engine else 0,
        "model":       gemini_rest.model if gemini_rest else None,
        "api_type":    "REST (direct auto-discovery) + RAG"
    }


@app.get("/rag/status")
def rag_status():
    """Status of the RAG knowledge base engine."""
    if rag_engine:
        return rag_engine.status()
    return {
        "is_ready": False,
        "num_chunks": 0,
        "files_loaded": [],
        "data_dir": "",
        "features": 0
    }


@app.get("/debug/models")
def debug_models():
    """Diagnostic endpoint to inspect discovered models and probe results."""
    return {
        "google_api_key_set": bool(GOOGLE_API_KEY),
        "active_model":       gemini_rest.model if gemini_rest else None,
        "active_version":     gemini_rest.version if gemini_rest else None,
        "active_url":         gemini_rest._url if gemini_rest else None,
        "discovered_models":  gemini_rest.discovered_models if gemini_rest else [],
        "probe_log":          gemini_rest.probe_log if gemini_rest else []
    }


@app.get("/")
def root():
    return {
        "message": "Judicial AI Backend v6.0 — Dynamic Gemini REST + RAG",
        "docs":    "/docs",
        "health":  "/health",
        "rag":     "/rag/status",
        "debug":   "/debug/models"
    }


# ─── Startup Event ────────────────────────────────────────────────────────────
@app.on_event("startup")
async def startup():
    init_services()
    sep = "=" * 60
    print(f"\n{sep}")
    print("  JUDICIAL AI BACKEND v6.0 — GEMINI REST + RAG")
    print(sep)
    print(f"  Active Model: {gemini_rest.model if gemini_rest else 'NOT INITIALIZED'}")
    print(f"  API Type:     Direct REST (dynamic model auto-discovery)")
    print(f"  RAG Engine:   {'Active (' + str(rag_engine.num_chunks) + ' chunks)' if rag_engine and rag_engine.is_ready else 'Inactive'}")
    print(f"  Agents:       {'5-agent pipeline ready' if multi_agent else 'Not initialized'}")
    print(f"  Web Search:   DuckDuckGo Lite (raw httpx)")
    print(f"  Database:     SQLite ({DB_PATH})")
    print(f"  API Docs:     /docs")
    print(f"{sep}\n")


# ─── Local Dev Entry Point ───────────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=True)
