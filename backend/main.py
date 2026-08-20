"""
JUDICIAL AI BACKEND — RENDER CLOUD VERSION
==========================================
• Google Gemini 2.0 Flash via google-genai SDK (pure Python, no Rust)
• 5-Agent Multi-Agent Reasoning Pipeline
• DuckDuckGo Web Search (pure Python)
• Zero LangChain / Zero compilation required
• Compatible with Python 3.11–3.14+
"""

import os
import io
import sys
import re
import PyPDF2
from dotenv import load_dotenv

# Fix Windows emoji encoding (harmless on Linux/Render)
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import google.genai as genai

from agents import MultiAgentOrchestrator, LLMResponse

# ─── Setup ────────────────────────────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(BASE_DIR)
load_dotenv()

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "")
GEMINI_MODEL   = "gemini-2.0-flash"

# ─── FastAPI App ──────────────────────────────────────────────────────────────
app = FastAPI(
    title="Judicial AI — Gemini Cloud Backend",
    version="4.0.0",
    description="AI-powered legal judgment analysis using Gemini 2.0 Flash"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── Gemini Client ────────────────────────────────────────────────────────────
gemini_client = None
if GOOGLE_API_KEY:
    try:
        gemini_client = genai.Client(api_key=GOOGLE_API_KEY)
        # Quick test
        gemini_client.models.generate_content(
            model=GEMINI_MODEL,
            contents="ping"
        )
        print(f"[OK] Gemini {GEMINI_MODEL} connected")
    except Exception as e:
        print(f"[ERR] Gemini connection failed: {e}")
        gemini_client = None
else:
    print("[ERR] GOOGLE_API_KEY not set — add it in Render Environment Variables!")

# ─── LLM Wrapper ─────────────────────────────────────────────────────────────
class GeminiLLM:
    """Drop-in LLM wrapper using google-genai SDK directly"""

    def __init__(self, client, model: str = GEMINI_MODEL):
        self.client = client
        self.model  = model

    def invoke(self, prompt) -> LLMResponse:
        # Accept both string and list-of-messages (from agents.py)
        if isinstance(prompt, list):
            text = "\n".join(
                m.content if hasattr(m, "content") else str(m)
                for m in prompt
            )
        else:
            text = str(prompt)

        try:
            response = self.client.models.generate_content(
                model=self.model,
                contents=text
            )
            return LLMResponse(response.text or "")
        except Exception as e:
            return LLMResponse(f"[LLM Error: {str(e)}]")

llm = GeminiLLM(gemini_client) if gemini_client else None

# ─── DuckDuckGo Search (raw httpx — zero extra packages) ──────────────────────
def ddg_search(query: str, max_results: int = 5) -> list:
    """
    Calls DuckDuckGo Lite HTML endpoint directly using httpx.
    Returns list of {title, href, body} dicts.
    """
    try:
        import httpx, re as _re
        resp = httpx.post(
            "https://html.duckduckgo.com/html/",
            data={"q": query, "b": ""},
            headers={"User-Agent": "Mozilla/5.0 (compatible; JudiciaAI/4.0)"},
            timeout=10.0,
            follow_redirects=True
        )
        # Parse results from HTML
        results = []
        titles   = _re.findall(r'class="result__a"[^>]*>([^<]+)</a>', resp.text)
        urls     = _re.findall(r'class="result__url"[^>]*>\s*([^\s<]+)', resp.text)
        snippets = _re.findall(r'class="result__snippet"[^>]*>([^<]+)</a>', resp.text)

        for i in range(min(max_results, len(titles), len(urls))):
            results.append({
                "title": titles[i].strip(),
                "href":  "https://" + urls[i].strip().lstrip("https://"),
                "body":  snippets[i].strip() if i < len(snippets) else ""
            })
        return results
    except Exception as e:
        print(f"[WARN] DuckDuckGo search error: {e}")
        return []

def web_search(query: str) -> dict:
    """
    Returns: {"answer": str, "sources": [{"title", "url", "snippet"}]}
    """
    try:
        raw = ddg_search(query)
        if not raw:
            return {"answer": "No web sources found", "sources": []}

        sources = [
            {
                "title":   r.get("title",  f"Legal Source {i+1}"),
                "url":     r.get("href",   ""),
                "snippet": r.get("body",   "")[:300]
            }
            for i, r in enumerate(raw) if r.get("href")
        ]

        if not sources:
            return {"answer": "No usable sources found", "sources": []}

        # Summarize with Gemini
        if llm:
            snippets = "\n".join([
                f"- {s['title']}: {s['snippet']}" for s in sources[:3]
            ])
            prompt = (
                f"You are a legal research assistant.\n"
                f"Query: {query}\n"
                f"Search results:\n{snippets}\n"
                f"Write a 2-paragraph legal analysis."
            )
            response = llm.invoke(prompt)
            answer = response.content.strip()
        else:
            answer = f"Found {len(sources)} sources (Gemini not configured)."

        return {"answer": answer, "sources": sources}

    except Exception as e:
        return {"answer": f"Search error: {str(e)}", "sources": []}

# ─── Multi-Agent System ───────────────────────────────────────────────────────
multi_agent = None
if llm:
    try:
        multi_agent = MultiAgentOrchestrator(
            llm=llm,
            web_search_function=web_search
        )
        print("[OK] 5-Agent pipeline ready")
    except Exception as e:
        print(f"[ERR] Multi-Agent init failed: {e}")

# ─── Helpers ──────────────────────────────────────────────────────────────────
def extract_text_from_pdf(data: bytes) -> str:
    try:
        reader = PyPDF2.PdfReader(io.BytesIO(data))
        text = ""
        for page in reader.pages:
            t = page.extract_text()
            if t:
                text += t + "\n"
        return text[:12000]
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid or unreadable PDF")

def run_analysis(text: str) -> dict:
    if not multi_agent:
        return {
            "summary":  "Backend not configured — set GOOGLE_API_KEY in Render.",
            "analysis": "",
            "laws":     "",
            "web_sources": []
        }
    return multi_agent.run(judgment_text=text, rag_context="")

# ─── API Endpoints ────────────────────────────────────────────────────────────
class WebQuery(BaseModel):
    query: str

@app.post("/analyze")
async def analyze_pdf(file: UploadFile = File(...)):
    """Analyze a legal judgment PDF."""
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files supported")

    data = await file.read()
    if len(data) > 20 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="PDF too large (max 20 MB)")

    text = extract_text_from_pdf(data)
    if len(text.strip()) < 50:
        raise HTTPException(status_code=400, detail="PDF is empty or unreadable")

    result = run_analysis(text)
    return {
        "filename":            file.filename,
        "summary":             result.get("summary", ""),
        "laws":                result.get("laws", ""),
        "analysis":            result.get("analysis", ""),
        "web_sources":         result.get("web_sources", []),
        "characters_processed": len(text)
    }

@app.post("/web-search")
def manual_search(query: WebQuery):
    """Run a legal web search."""
    return web_search(query.query)

@app.get("/health")
def health():
    """Health check — used by Render."""
    return {
        "status":      "online",
        "version":     "4.0.0",
        "gemini":      bool(gemini_client),
        "multi_agent": bool(multi_agent),
        "model":       GEMINI_MODEL
    }

@app.get("/")
def root():
    return {
        "message": "Judicial AI Backend v4.0 — Gemini Cloud",
        "docs":    "/docs",
        "health":  "/health"
    }

# ─── Startup Log ──────────────────────────────────────────────────────────────
@app.on_event("startup")
async def startup():
    sep = "=" * 55
    print(f"\n{sep}")
    print("  JUDICIAL AI BACKEND v4.0 — GEMINI CLOUD")
    print(sep)
    print(f"  Gemini:     {GEMINI_MODEL if gemini_client else 'NOT CONFIGURED'}")
    print(f"  Agents:     {'5-agent pipeline active' if multi_agent else 'Not initialized'}")
    print(f"  Web Search: DuckDuckGo (pure Python)")
    print(f"  API Docs:   /docs")
    print(f"{sep}\n")

# ─── Local Dev Only ───────────────────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
