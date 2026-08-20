"""
JUDICIAL AI BACKEND — GEMINI REST API DIRECT
============================================
• Calls Gemini API directly via httpx (no SDK, no grpcio, no Rust)
• 5-Agent Multi-Agent Reasoning Pipeline
• DuckDuckGo Web Search (raw httpx)
• Zero external AI dependencies
• Works on Python 3.8–3.14+, any platform
"""

import os
import io
import sys
import re
import json
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

# ─── Config ───────────────────────────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(BASE_DIR)
load_dotenv()

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "")
GEMINI_MODEL   = "gemini-1.5-flash"     # Available in v1beta REST API
GEMINI_URL     = (
    "https://generativelanguage.googleapis.com/v1beta/models/"
    f"{GEMINI_MODEL}:generateContent"
)

# ─── FastAPI App ──────────────────────────────────────────────────────────────
app = FastAPI(
    title="Judicial AI — Gemini REST Backend",
    version="5.0.0",
    description="AI-powered legal analysis via Gemini REST API"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── Gemini REST Client ───────────────────────────────────────────────────────
class GeminiRESTClient:
    """
    Calls Gemini via direct REST API — no SDK needed.
    Uses: https://generativelanguage.googleapis.com/v1beta/models/...
    Compatible with all AI Studio API keys.
    """

    def __init__(self, api_key: str, model: str = GEMINI_MODEL):
        self.api_key = api_key
        self.model   = model
        self.url     = (
            f"https://generativelanguage.googleapis.com/v1beta/models/"
            f"{model}:generateContent"
        )

    def generate(self, prompt: str) -> str:
        payload = {
            "contents": [
                {"parts": [{"text": prompt}]}
            ],
            "generationConfig": {
                "temperature": 0.3,
                "maxOutputTokens": 4096
            }
        }
        try:
            resp = httpx.post(
                self.url,
                json=payload,
                params={"key": self.api_key},
                headers={"Content-Type": "application/json"},
                timeout=120.0
            )
            resp.raise_for_status()
            data = resp.json()
            return data["candidates"][0]["content"]["parts"][0]["text"]
        except httpx.HTTPStatusError as e:
            raise RuntimeError(f"Gemini API error {e.response.status_code}: {e.response.text}")
        except Exception as e:
            raise RuntimeError(f"Gemini request failed: {str(e)}")


# ─── LLM Wrapper (compatible with agents.py) ─────────────────────────────────
class GeminiLLM:
    """Wraps GeminiRESTClient with agents.py-compatible .invoke() interface"""

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


# ─── Initialize ───────────────────────────────────────────────────────────────
gemini_rest = None
llm         = None

if GOOGLE_API_KEY:
    gemini_rest = GeminiRESTClient(api_key=GOOGLE_API_KEY, model=GEMINI_MODEL)
    llm = GeminiLLM(gemini_rest)
    print(f"[OK] Gemini REST client ready ({GEMINI_MODEL})")
else:
    print("[ERR] GOOGLE_API_KEY not set in Render Environment Variables!")

# ─── DuckDuckGo Search (raw httpx) ───────────────────────────────────────────
def ddg_search(query: str, max_results: int = 5) -> list:
    """Direct DuckDuckGo Lite HTML scrape via httpx"""
    try:
        resp = httpx.post(
            "https://html.duckduckgo.com/html/",
            data={"q": query, "b": ""},
            headers={"User-Agent": "Mozilla/5.0 (compatible; JudiciaAI/5.0)"},
            timeout=10.0,
            follow_redirects=True
        )
        titles   = re.findall(r'class="result__a"[^>]*>([^<]+)</a>', resp.text)
        urls     = re.findall(r'class="result__url"[^>]*>\s*([^\s<]+)', resp.text)
        snippets = re.findall(r'class="result__snippet"[^>]*>([^<]+)</a>', resp.text)

        results = []
        for i in range(min(max_results, len(titles), len(urls))):
            results.append({
                "title": titles[i].strip(),
                "href":  "https://" + urls[i].strip().lstrip("https://"),
                "body":  snippets[i].strip() if i < len(snippets) else ""
            })
        return results
    except Exception as e:
        print(f"[WARN] DDG search error: {e}")
        return []


def web_search(query: str) -> dict:
    """Returns {answer, sources} dict"""
    try:
        raw = ddg_search(query)
        if not raw:
            return {"answer": "No web sources found", "sources": []}

        sources = [
            {
                "title":   r.get("title",  f"Source {i+1}"),
                "url":     r.get("href",   ""),
                "snippet": r.get("body",   "")[:300]
            }
            for i, r in enumerate(raw) if r.get("href")
        ]

        if not sources:
            return {"answer": "No usable sources found", "sources": []}

        if llm:
            snippets_text = "\n".join([
                f"- {s['title']}: {s['snippet']}" for s in sources[:3]
            ])
            prompt = (
                f"Legal research query: {query}\n"
                f"Search results:\n{snippets_text}\n"
                f"Provide a concise 2-paragraph legal analysis."
            )
            answer = llm.invoke(prompt).content.strip()
        else:
            answer = f"Found {len(sources)} sources."

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
            "summary":     "Backend not configured — set GOOGLE_API_KEY in Render.",
            "analysis":    "",
            "laws":        "",
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
        "filename":             file.filename,
        "summary":              result.get("summary", ""),
        "laws":                 result.get("laws", ""),
        "analysis":             result.get("analysis", ""),
        "web_sources":          result.get("web_sources", []),
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
        "version":     "5.0.0",
        "gemini":      bool(gemini_rest),
        "multi_agent": bool(multi_agent),
        "model":       GEMINI_MODEL,
        "api_type":    "REST (direct)"
    }


@app.get("/")
def root():
    return {
        "message": "Judicial AI Backend v5.0 — Gemini REST Direct",
        "docs":    "/docs",
        "health":  "/health"
    }


# ─── Startup Log ──────────────────────────────────────────────────────────────
@app.on_event("startup")
async def startup():
    sep = "=" * 55
    print(f"\n{sep}")
    print("  JUDICIAL AI BACKEND v5.0 — GEMINI REST DIRECT")
    print(sep)
    print(f"  Gemini:     {GEMINI_MODEL if gemini_rest else 'NOT CONFIGURED'}")
    print(f"  API Type:   Direct REST (no SDK)")
    print(f"  Agents:     {'5-agent pipeline active' if multi_agent else 'Not initialized'}")
    print(f"  Web Search: DuckDuckGo (raw httpx)")
    print(f"  API Docs:   /docs")
    print(f"{sep}\n")


# ─── Local Dev Only ───────────────────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
