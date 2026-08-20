"""
MULTI-AGENT ORCHESTRATOR — GEMINI CLOUD VERSION
================================================
• Zero LangChain dependency
• Uses google-genai SDK directly (pure Python)
• 5 Agents: Law Identifier, Web Research,
            Precedent Analyzer, Logic Auditor, Summary Writer
"""

import re
from typing import List

# ─── Simple Message Types (replacing LangChain) ───────────────────────────────

class HumanMessage:
    def __init__(self, content: str):
        self.content = content

class AIMessage:
    def __init__(self, content: str):
        self.content = content

class LLMResponse:
    """Wraps raw string response to mimic LangChain response.content"""
    def __init__(self, text: str):
        self.content = text

# ─── Agent State ──────────────────────────────────────────────────────────────

class AgentState:
    def __init__(self, judgment_text: str, rag_context: str = ""):
        self.judgment_text = judgment_text
        self.rag_context = rag_context
        self.web_research = ""
        self.web_sources: List[dict] = []
        self.laws_found = ""
        self.precedent_analysis = ""
        self.logic_audit = ""
        self.final_summary = ""
        self.messages: List[AIMessage] = []
        self.current_agent = "initializing"

# ─── Individual Agents ────────────────────────────────────────────────────────

class LawIdentifierAgent:
    """Agent 1: Extracts applicable laws and IPC sections"""

    def __init__(self, llm):
        self.llm = llm
        self.name = "Law Identifier"

    def run(self, state: AgentState) -> AgentState:
        print(f"\n[{self.name}] Working...")

        prompt = f"""You are a Legal Law Identification Specialist.

YOUR JOB: Identify ALL applicable laws, IPC sections, and legal provisions from this judgment.

JUDGMENT TEXT:
{state.judgment_text[:3000]}

RAG CONTEXT (similar cases):
{state.rag_context[:1000]}

INSTRUCTIONS:
- Extract all IPC sections, Acts, and legal provisions mentioned
- Format each as: "Section XXX (Act Name) - Description"
- Include articles of Constitution if mentioned
- Be comprehensive and precise
- Organize by category (Criminal, Civil, Constitutional, etc.)

EXTRACT LAWS:"""

        response = self.llm.invoke(prompt)
        laws = response.content.strip()

        state.laws_found = laws
        state.messages.append(AIMessage(content=f"[{self.name}] Found laws: {laws[:80]}..."))
        state.current_agent = self.name

        print(f"   Done: {laws[:80]}...")
        return state


class WebResearchAgent:
    """Agent 2: Uses DuckDuckGo for real-time legal web research"""

    def __init__(self, llm, web_search_function=None):
        self.llm = llm
        self.web_search_function = web_search_function
        self.name = "Web Research"

    def _extract_primary_section(self, laws: str, text: str) -> str:
        priority_sections = [
            ("302", "Murder"), ("304A", "Death by Negligence"),
            ("376", "Sexual Assault"), ("307", "Attempt to Murder"),
            ("498A", "Cruelty to Wife"), ("420", "Cheating"),
            ("379", "Theft"), ("506", "Criminal Intimidation"),
        ]
        for section, _ in priority_sections:
            if f"Section {section}" in laws or section in text[:2000]:
                return f"Section {section} IPC"
        match = re.search(r'Section (\d+[A-Z]*)', laws or text)
        if match:
            return f"Section {match.group(1)} IPC"
        return "IPC"

    def run(self, state: AgentState) -> AgentState:
        print(f"\n[{self.name}] Working...")

        if not self.web_search_function:
            state.web_research = "Web search not configured"
            state.web_sources = []
            state.current_agent = self.name
            return state

        try:
            primary_section = self._extract_primary_section(
                state.laws_found, state.judgment_text
            )
            search_query = f"{primary_section} case law India recent judgment"
            print(f"   Searching: {search_query}")

            result = self.web_search_function(search_query)
            state.web_sources = result.get("sources", [])
            state.web_research = result.get("answer", "")
            state.messages.append(
                AIMessage(content=f"[{self.name}] Found {len(state.web_sources)} sources")
            )
        except Exception as e:
            print(f"   Web research error: {e}")
            state.web_research = f"Web research error: {str(e)}"
            state.web_sources = []

        state.current_agent = self.name
        return state


class PrecedentAnalyzerAgent:
    """Agent 3: Analyzes precedents using local and web sources"""

    def __init__(self, llm):
        self.llm = llm
        self.name = "Precedent Analyzer"

    def run(self, state: AgentState) -> AgentState:
        print(f"\n[{self.name}] Working...")

        web_context = ""
        if state.web_research:
            web_context = f"\nWEB RESEARCH FINDINGS:\n{state.web_research[:800]}\n"

        sources_text = ""
        if state.web_sources:
            sources_text = "\nWEB SOURCES:\n" + "\n".join([
                f"- {s.get('title', 'Source')}: {s.get('url', 'N/A')}"
                for s in state.web_sources[:3]
            ])

        prompt = f"""You are a Legal Precedent Analysis Specialist.

LAWS IDENTIFIED:
{state.laws_found[:500]}

JUDGMENT TEXT:
{state.judgment_text[:3000]}

RAG CONTEXT:
{state.rag_context[:1000]}
{web_context}
{sources_text}

ANALYZE:
1. What precedents are relevant to these laws?
2. How should this judgment compare with precedents?
3. What guidelines are established for these sections?
4. Are there any conflicting decisions?

PRECEDENT ANALYSIS (3-4 paragraphs):"""

        response = self.llm.invoke(prompt)
        state.precedent_analysis = response.content.strip()
        state.messages.append(AIMessage(content=f"[{self.name}] Precedent analysis complete"))
        state.current_agent = self.name

        print("   Done.")
        return state


class LogicAuditorAgent:
    """Agent 4: Audits the logical consistency of the judgment"""

    def __init__(self, llm):
        self.llm = llm
        self.name = "Logic Auditor"

    def run(self, state: AgentState) -> AgentState:
        print(f"\n[{self.name}] Working...")

        prompt = f"""You are a Legal Logic Consistency Auditor.

LAWS APPLIED:
{state.laws_found[:500]}

JUDGMENT TEXT:
{state.judgment_text[:3000]}

PRECEDENT COMPARISON:
{state.precedent_analysis[:1000]}

AUDIT CHECKLIST:
- Are facts and findings consistent?
- Does the conclusion follow from reasoning?
- Are there logical gaps or contradictions?
- Is the burden of proof properly addressed?
- Are all relevant points addressed?

LOGIC AUDIT (2-3 paragraphs):"""

        response = self.llm.invoke(prompt)
        state.logic_audit = response.content.strip()
        state.messages.append(AIMessage(content=f"[{self.name}] Logic audit complete"))
        state.current_agent = self.name

        print("   Done.")
        return state


class SummaryWriterAgent:
    """Agent 5: Creates citizen-friendly summary"""

    def __init__(self, llm):
        self.llm = llm
        self.name = "Summary Writer"

    def run(self, state: AgentState) -> AgentState:
        print(f"\n[{self.name}] Working...")

        prompt = f"""Create a simple, citizen-friendly summary of this legal judgment.

JUDGMENT:
{state.judgment_text[:2000]}

LAWS INVOLVED:
{state.laws_found[:300]}

ANALYSIS:
{state.precedent_analysis[:500]}

STRUCTURE YOUR SUMMARY:
1. What happened? (The case briefly)
2. What did the court decide?
3. Why did the court decide this way?
4. What does this mean?

REQUIREMENTS:
- Use simple, everyday language
- Avoid legal jargon (explain if necessary)
- 4-6 sentences maximum
- Understandable for someone with no legal background

SUMMARY:"""

        response = self.llm.invoke(prompt)
        state.final_summary = response.content.strip()
        state.messages.append(AIMessage(content=f"[{self.name}] Summary complete"))
        state.current_agent = self.name

        print("   Done.")
        return state


# ─── Multi-Agent Orchestrator ─────────────────────────────────────────────────

class MultiAgentOrchestrator:
    """Runs the 5-agent legal analysis pipeline"""

    def __init__(self, llm, web_search_function=None):
        self.llm = llm
        self.law_agent      = LawIdentifierAgent(llm)
        self.web_agent      = WebResearchAgent(llm, web_search_function)
        self.precedent_agent = PrecedentAnalyzerAgent(llm)
        self.logic_agent    = LogicAuditorAgent(llm)
        self.summary_agent  = SummaryWriterAgent(llm)

    def run(self, judgment_text: str, rag_context: str = "") -> dict:
        print("\n" + "="*60)
        print("  MULTI-AGENT SYSTEM — 5 AGENTS ACTIVATED")
        print("="*60)

        state = AgentState(
            judgment_text=judgment_text,
            rag_context=rag_context or ""
        )

        state = self.law_agent.run(state)
        state = self.web_agent.run(state)
        state = self.precedent_agent.run(state)
        state = self.logic_agent.run(state)
        state = self.summary_agent.run(state)

        print("\n" + "="*60)
        print("  ALL 5 AGENTS COMPLETED")
        print("="*60 + "\n")

        return {
            "laws": state.laws_found,
            "summary": state.final_summary,
            "analysis": f"PRECEDENT ANALYSIS:\n{state.precedent_analysis}\n\nLOGIC AUDIT:\n{state.logic_audit}",
            "web_research": state.web_research,
            "web_sources": state.web_sources,
            "agent_messages": [msg.content for msg in state.messages]
        }