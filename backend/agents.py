"""
MULTI-AGENT ORCHESTRATOR — STRUCTURED READABLE OUTPUT
=====================================================
• Zero LangChain dependency
• 5 Agents: Summary Writer, Law Identifier, Web Research,
            Precedent Analyzer, Logic Auditor
• All prompts produce structured, emoji-marked, child-friendly output
• Output is easy to parse into structured JSON sections
"""

import re
from typing import List, Dict

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
    """Agent 1: Extracts applicable laws and IPC sections in a readable format"""

    def __init__(self, llm):
        self.llm = llm
        self.name = "Law Identifier"

    def run(self, state: AgentState) -> AgentState:
        print(f"\n[{self.name}] Working...")

        rag_section = ""
        if state.rag_context:
            rag_section = f"""
KNOWLEDGE BASE CONTEXT (Retrieved from Indian Legal Database):
{state.rag_context[:2000]}
"""

        prompt = f"""You are a Legal Law Identification Specialist who explains laws in simple, everyday language.

JUDGMENT TEXT:
{state.judgment_text[:4000]}
{rag_section}

YOUR TASK: Identify ALL applicable laws, IPC sections, and legal provisions from this judgment.
Then explain each one so clearly that even a school student could understand it.

FORMAT YOUR RESPONSE EXACTLY LIKE THIS:

🔴 CRIMINAL LAW SECTIONS
• Section [NUMBER] ([ACT NAME]) — [Short Title]
  ↳ In simple words: [Explain what this law means in 1 simple sentence, like explaining to a friend]
  ↳ Why it applies here: [1 sentence on why this law is relevant to this case]

(List ALL criminal sections found. If none, write "No criminal law sections found in this judgment.")

🟠 CIVIL LAW PROVISIONS
• [Same format as above]

(If none, write "No civil law provisions found in this judgment.")

🔵 CONSTITUTIONAL ARTICLES
• Article [NUMBER] — [Title]
  ↳ In simple words: [Simple explanation]
  ↳ Why it applies here: [1 sentence]

(If none, write "No constitutional articles cited in this judgment.")

🟢 OTHER LAWS & ACTS
• [Any other special acts, regulations, or rules mentioned]
  ↳ In simple words: [Simple explanation]

(If none, skip this section entirely.)

IMPORTANT RULES:
- Use EVERYDAY language. No legal jargon without explanation.
- Be comprehensive — don't miss any law mentioned in the judgment.
- Each explanation should be understandable by someone with zero legal knowledge.
- Keep each explanation to 1-2 sentences maximum.

EXTRACT ALL LAWS NOW:"""

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
    """Agent 3: Analyzes precedents using RAG context and web sources"""

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

        rag_section = ""
        if state.rag_context:
            rag_section = f"""
KNOWLEDGE BASE (Retrieved Legal Precedents & Laws):
{state.rag_context[:2000]}
"""

        prompt = f"""You are a Legal Precedent Analyst who explains past cases in simple, story-like language.

LAWS IDENTIFIED IN THIS CASE:
{state.laws_found[:800]}

JUDGMENT TEXT:
{state.judgment_text[:3000]}
{rag_section}
{web_context}
{sources_text}

YOUR TASK: Find and explain similar past cases (precedents) that relate to this judgment.
Make it so simple that anyone can understand — like telling stories about what happened in similar cases before.

FORMAT YOUR RESPONSE EXACTLY LIKE THIS:

📚 SIMILAR PAST CASES

1️⃣ [Case Name] ([Year])
   🏛️ Court: [Which court decided this]
   📖 What happened: [Tell the story of this case in 2-3 simple sentences]
   🔗 How it connects to our case: [1-2 sentences explaining why this old case matters for the current one]
   ⚖️ What was decided: [1 sentence about the outcome]

2️⃣ [Next case - same format]

3️⃣ [Next case - same format]

(Include 3-5 relevant past cases. If the knowledge base provided specific cases, prioritize those.)

🔗 HOW THIS CASE COMPARES TO PAST DECISIONS
[Write 2-3 sentences comparing the current case with the precedents above. Is the current judgment consistent with past decisions? Does it break new ground? Explain simply.]

💡 KEY TAKEAWAY
[One clear sentence summarizing what these past cases tell us about the current judgment.]

IMPORTANT:
- Write like you're telling stories to a friend, not writing a legal textbook.
- If you don't know a specific case, don't make one up. Use the cases provided in the knowledge base or web research.
- Keep language simple and jargon-free.

ANALYZE PRECEDENTS NOW:"""

        response = self.llm.invoke(prompt)
        state.precedent_analysis = response.content.strip()
        state.messages.append(AIMessage(content=f"[{self.name}] Precedent analysis complete"))
        state.current_agent = self.name

        print("   Done.")
        return state


class LogicAuditorAgent:
    """Agent 4: Audits the logical consistency with traffic-light ratings"""

    def __init__(self, llm):
        self.llm = llm
        self.name = "Logic Auditor"

    def run(self, state: AgentState) -> AgentState:
        print(f"\n[{self.name}] Working...")

        prompt = f"""You are a Legal Logic Auditor who checks if a court's judgment makes sense.
Your job is to explain your findings so simply that anyone can understand — like a school report card for the judgment.

LAWS APPLIED:
{state.laws_found[:600]}

JUDGMENT TEXT:
{state.judgment_text[:3000]}

PRECEDENT COMPARISON:
{state.precedent_analysis[:1200]}

YOUR TASK: Check if the court's reasoning is logical, fair, and consistent.
Then give a simple "report card" that anyone can understand.

FORMAT YOUR RESPONSE EXACTLY LIKE THIS:

✅ STRENGTHS — What the Court Got Right
• [Point 1: Explain in simple language what the court did well]
• [Point 2: Another strength]
• [Point 3: If applicable]

(List 2-4 strengths. Focus on clear reasoning, proper evidence use, fairness.)

⚠️ CONCERNS — Possible Weak Points
• [Point 1: Explain in simple language what could be questioned]
• [Point 2: Another concern]

(List 1-3 concerns. Be fair and balanced. If the judgment is solid, say so.)

🔍 EVIDENCE CHECK
• Was evidence properly considered? [Yes/Partially/No] — [Brief explanation]
• Were all sides heard fairly? [Yes/Partially/No] — [Brief explanation]
• Does the punishment fit the crime? [Yes/Partially/No] — [Brief explanation]

📊 OVERALL CONSISTENCY SCORE: [X]/10

Give a score from 1-10 based on:
- Logical reasoning (does the conclusion follow from the facts?)
- Evidence handling (were facts properly evaluated?)
- Precedent alignment (does it match similar past cases?)
- Fairness (were all parties treated justly?)

[Write 1-2 sentences explaining the score. Example: "This judgment scores 8/10 because the court clearly explained its reasoning and followed established precedents, though the sentencing could have been explained more thoroughly."]

IMPORTANT:
- Be honest but fair. Don't be overly critical or overly praising.
- Use simple, everyday language throughout.
- The score should reflect genuine analysis, not just a random number.

AUDIT THE JUDGMENT NOW:"""

        response = self.llm.invoke(prompt)
        state.logic_audit = response.content.strip()
        state.messages.append(AIMessage(content=f"[{self.name}] Logic audit complete"))
        state.current_agent = self.name

        print("   Done.")
        return state


class SummaryWriterAgent:
    """Agent 5: Creates crystal-clear, child-friendly summary"""

    def __init__(self, llm):
        self.llm = llm
        self.name = "Summary Writer"

    def run(self, state: AgentState) -> AgentState:
        print(f"\n[{self.name}] Working...")

        prompt = f"""You are a Legal Summary Writer who turns complex court judgments into crystal-clear stories
that ANYONE can understand — even a 12-year-old student.

JUDGMENT TEXT:
{state.judgment_text[:3000]}

LAWS INVOLVED:
{state.laws_found[:500]}

PRECEDENT ANALYSIS:
{state.precedent_analysis[:600]}

LOGIC AUDIT:
{state.logic_audit[:400]}

YOUR TASK: Create a complete, easy-to-understand summary of this judgment.

FORMAT YOUR RESPONSE EXACTLY LIKE THIS:

📋 CASE AT A GLANCE
• Case Name: [Full case name if available, or "Details from judgment"]
• Court: [Which court — e.g., Supreme Court of India, High Court of Delhi, etc.]
• Date: [Date of judgment if mentioned, or "Not specified"]
• Verdict: [One word — GUILTY / NOT GUILTY / ACQUITTED / PARTIALLY ALLOWED / DISMISSED / ALLOWED]

📖 WHAT HAPPENED — The Story
[Tell the story of this case in 4-6 simple sentences. Start with WHO was involved, WHAT they did (or were accused of doing), WHEN it happened. Write like you're telling a story to a friend. Avoid any legal jargon.]

⚖️ WHAT THE COURT DECIDED
[In 2-3 clear sentences, explain exactly what the court decided. Was the person found guilty or innocent? What punishment was given? Was an appeal accepted or rejected?]

🤔 WHY THE COURT DECIDED THIS WAY
[In 3-5 bullet points, explain the court's reasoning in simple language:]
• [Reason 1 — the main reason for the decision]
• [Reason 2 — supporting evidence or logic]
• [Reason 3 — if applicable]

👤 WHAT THIS MEANS FOR ORDINARY PEOPLE
[1-2 sentences explaining the broader impact. What lesson does this case teach? How might it affect similar situations in the future?]

CRITICAL RULES:
- Write EVERY sentence as if explaining to someone who has NEVER read a law book.
- NO legal jargon. If you must use a legal term, explain it in parentheses.
  Example: "The court granted bail (permission to leave jail while the case continues)"
- Keep sentences SHORT. Maximum 20-25 words per sentence.
- Be accurate — don't invent facts not in the judgment.
- The verdict must be ONE of: GUILTY, NOT GUILTY, ACQUITTED, PARTIALLY ALLOWED, DISMISSED, ALLOWED, MODIFIED, UPHELD, OVERTURNED

WRITE THE SUMMARY NOW:"""

        response = self.llm.invoke(prompt)
        state.final_summary = response.content.strip()
        state.messages.append(AIMessage(content=f"[{self.name}] Summary complete"))
        state.current_agent = self.name

        print("   Done.")
        return state


# ─── Multi-Agent Orchestrator ─────────────────────────────────────────────────

class MultiAgentOrchestrator:
    """Runs the 5-agent legal analysis pipeline with structured output"""

    def __init__(self, llm, web_search_function=None):
        self.llm = llm
        self.law_agent       = LawIdentifierAgent(llm)
        self.web_agent       = WebResearchAgent(llm, web_search_function)
        self.precedent_agent = PrecedentAnalyzerAgent(llm)
        self.logic_agent     = LogicAuditorAgent(llm)
        self.summary_agent   = SummaryWriterAgent(llm)

    def run(self, judgment_text: str, rag_context: str = "") -> dict:
        print("\n" + "=" * 60)
        print("  MULTI-AGENT SYSTEM — 5 AGENTS ACTIVATED")
        if rag_context:
            print("  RAG CONTEXT: Active (knowledge base enriched)")
        else:
            print("  RAG CONTEXT: None (no knowledge base context)")
        print("=" * 60)

        state = AgentState(
            judgment_text=judgment_text,
            rag_context=rag_context or ""
        )

        # Run all 5 agents in sequence
        state = self.law_agent.run(state)
        state = self.web_agent.run(state)
        state = self.precedent_agent.run(state)
        state = self.logic_agent.run(state)
        state = self.summary_agent.run(state)

        print("\n" + "=" * 60)
        print("  ALL 5 AGENTS COMPLETED")
        print("=" * 60 + "\n")

        return {
            "summary":          state.final_summary,
            "laws":             state.laws_found,
            "precedents":       state.precedent_analysis,
            "logic_audit":      state.logic_audit,
            "analysis":         f"PRECEDENT ANALYSIS:\n{state.precedent_analysis}\n\nLOGIC AUDIT:\n{state.logic_audit}",
            "web_research":     state.web_research,
            "web_sources":      state.web_sources,
            "agent_messages":   [msg.content for msg in state.messages]
        }