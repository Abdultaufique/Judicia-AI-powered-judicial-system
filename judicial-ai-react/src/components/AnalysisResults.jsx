import { useState } from "react";

// ─── Helper: Parse structured text into visual sections ──────────────────────

function parseTextSections(text) {
    if (!text) return [];

    // Remove markdown bold markers
    let cleaned = text.replace(/\*\*/g, '');

    // Split into sections by emoji headers
    const sectionRegex = /^([\u{1F300}-\u{1FAD6}\u{2600}-\u{27BF}\u{FE00}-\u{FE0F}\u{1F900}-\u{1F9FF}\u{2702}-\u{27B0}✅⚠️🔍📊💡🔗📋📖⚖️🤔👤🔴🟠🟡🔵🟢📚🏛️1️⃣2️⃣3️⃣4️⃣5️⃣6️⃣7️⃣8️⃣9️⃣🔟]+)\s*(.+)/gmu;

    const lines = cleaned.split('\n');
    const sections = [];
    let currentSection = null;

    for (const line of lines) {
        const trimmed = line.trim();
        if (!trimmed) continue;

        // Check if this line starts a new section (has emoji at start)
        const emojiStart = /^[📋📖⚖️🤔👤🔴🟠🟡🔵🟢📚🏛️💡🔗🔍📊✅⚠️]/.test(trimmed) &&
            (trimmed.includes('CASE AT A GLANCE') || trimmed.includes('WHAT HAPPENED') ||
                trimmed.includes('WHAT THE COURT DECIDED') || trimmed.includes('WHY THE COURT') ||
                trimmed.includes('WHAT THIS MEANS') || trimmed.includes('CRIMINAL LAW') ||
                trimmed.includes('CIVIL LAW') || trimmed.includes('CONSTITUTIONAL') ||
                trimmed.includes('OTHER LAWS') || trimmed.includes('SIMILAR PAST') ||
                trimmed.includes('HOW THIS CASE') || trimmed.includes('KEY TAKEAWAY') ||
                trimmed.includes('STRENGTHS') || trimmed.includes('CONCERNS') ||
                trimmed.includes('EVIDENCE CHECK') || trimmed.includes('OVERALL CONSISTENCY') ||
                trimmed.includes('SCORE'));

        if (emojiStart) {
            if (currentSection) sections.push(currentSection);
            currentSection = { title: trimmed, content: [] };
        } else if (currentSection) {
            currentSection.content.push(trimmed);
        } else {
            // Content before any section header
            if (!sections.length) {
                sections.push({ title: "", content: [trimmed] });
            }
        }
    }
    if (currentSection) sections.push(currentSection);
    return sections;
}

// ─── Verdict Badge Component ─────────────────────────────────────────────────

function VerdictBadge({ text }) {
    if (!text) return null;

    const normalized = text.toUpperCase().trim();
    let color = "bg-slate-100 text-slate-700 border-slate-200";
    let glow = "";

    if (normalized.includes("GUILTY") && !normalized.includes("NOT")) {
        color = "bg-red-50 text-red-700 border-red-200";
        glow = "shadow-red-100";
    } else if (normalized.includes("NOT GUILTY") || normalized.includes("ACQUIT")) {
        color = "bg-emerald-50 text-emerald-700 border-emerald-200";
        glow = "shadow-emerald-100";
    } else if (normalized.includes("PARTIALLY") || normalized.includes("MODIFIED")) {
        color = "bg-amber-50 text-amber-700 border-amber-200";
        glow = "shadow-amber-100";
    } else if (normalized.includes("ALLOWED") || normalized.includes("UPHELD")) {
        color = "bg-blue-50 text-blue-700 border-blue-200";
        glow = "shadow-blue-100";
    } else if (normalized.includes("DISMISSED") || normalized.includes("REJECTED")) {
        color = "bg-orange-50 text-orange-700 border-orange-200";
        glow = "shadow-orange-100";
    }

    return (
        <span className={`inline-flex items-center gap-1.5 px-4 py-1.5 rounded-full text-sm font-bold border ${color} shadow-lg ${glow}`}>
            <span className="w-2 h-2 rounded-full bg-current opacity-60"></span>
            {text}
        </span>
    );
}

// ─── Section Renderer: Converts parsed sections into visual cards ────────────

function RenderSection({ section, index }) {
    const title = section.title;
    const content = section.content.join('\n');

    // Detect section type for special styling
    const isScore = title.includes('OVERALL CONSISTENCY') || title.includes('SCORE');
    const isStrength = title.includes('STRENGTHS') || title.includes('Got Right');
    const isConcern = title.includes('CONCERNS') || title.includes('Weak');
    const isEvidence = title.includes('EVIDENCE CHECK');
    const isCaseGlance = title.includes('CASE AT A GLANCE');
    const isCriminal = title.includes('CRIMINAL');
    const isConstitutional = title.includes('CONSTITUTIONAL');
    const isCivil = title.includes('CIVIL');

    // Extract score if present
    let scoreMatch = null;
    if (isScore) {
        scoreMatch = content.match(/(\d+)\s*\/\s*10/);
    }

    // Color mapping
    let borderColor = "border-l-indigo-400";
    let bgColor = "bg-white";
    let titleColor = "text-slate-800";

    if (isStrength) { borderColor = "border-l-emerald-400"; bgColor = "bg-emerald-50/50"; }
    if (isConcern) { borderColor = "border-l-amber-400"; bgColor = "bg-amber-50/50"; }
    if (isEvidence) { borderColor = "border-l-blue-400"; bgColor = "bg-blue-50/50"; }
    if (isCriminal) { borderColor = "border-l-red-400"; bgColor = "bg-red-50/30"; }
    if (isConstitutional) { borderColor = "border-l-blue-500"; bgColor = "bg-blue-50/30"; }
    if (isCivil) { borderColor = "border-l-green-400"; bgColor = "bg-green-50/30"; }
    if (isCaseGlance) { borderColor = "border-l-violet-400"; bgColor = "bg-violet-50/30"; }

    return (
        <div
            key={index}
            className={`rounded-xl border-l-4 ${borderColor} ${bgColor} p-5 mb-4 
                        shadow-sm hover:shadow-md transition-all duration-300 animate-fade-in`}
            style={{ animationDelay: `${index * 80}ms` }}
        >
            {title && (
                <h3 className={`text-lg font-bold ${titleColor} mb-3`}>
                    {title}
                </h3>
            )}

            {/* Score display */}
            {isScore && scoreMatch && (
                <div className="flex items-center gap-4 mb-4">
                    <div className={`w-20 h-20 rounded-2xl flex items-center justify-center text-2xl font-black shadow-lg ${
                        parseInt(scoreMatch[1]) >= 7 ? 'bg-gradient-to-br from-emerald-400 to-green-500 text-white' :
                        parseInt(scoreMatch[1]) >= 5 ? 'bg-gradient-to-br from-amber-400 to-orange-500 text-white' :
                        'bg-gradient-to-br from-red-400 to-red-600 text-white'
                    }`}>
                        {scoreMatch[1]}/10
                    </div>
                    <div className="flex-1">
                        <div className="h-3 bg-slate-200 rounded-full overflow-hidden">
                            <div
                                className={`h-full rounded-full transition-all duration-1000 ${
                                    parseInt(scoreMatch[1]) >= 7 ? 'bg-gradient-to-r from-emerald-400 to-green-500' :
                                    parseInt(scoreMatch[1]) >= 5 ? 'bg-gradient-to-r from-amber-400 to-orange-500' :
                                    'bg-gradient-to-r from-red-400 to-red-600'
                                }`}
                                style={{ width: `${parseInt(scoreMatch[1]) * 10}%` }}
                            ></div>
                        </div>
                    </div>
                </div>
            )}

            {/* Content rendering */}
            <div className="space-y-2">
                {section.content.map((line, i) => {
                    const trimmed = line.trim();
                    if (!trimmed) return null;

                    // Bullet point with arrow
                    if (trimmed.startsWith('↳') || trimmed.startsWith('→')) {
                        return (
                            <p key={i} className="text-sm text-slate-600 leading-relaxed pl-6 italic">
                                {trimmed}
                            </p>
                        );
                    }

                    // Bullet point
                    if (trimmed.startsWith('•') || trimmed.startsWith('-') || trimmed.startsWith('*')) {
                        return (
                            <div key={i} className="flex items-start gap-2 py-1">
                                <span className="mt-1.5 w-1.5 h-1.5 rounded-full bg-indigo-400 flex-shrink-0"></span>
                                <p className="text-base text-slate-700 leading-relaxed">
                                    {trimmed.replace(/^[•\-\*]\s*/, '')}
                                </p>
                            </div>
                        );
                    }

                    // Key-value pair (e.g., "Case Name: ...")
                    const kvMatch = trimmed.match(/^(.+?):\s+(.+)$/);
                    if (kvMatch && isCaseGlance) {
                        const isVerdict = kvMatch[1].toLowerCase().includes('verdict');
                        return (
                            <div key={i} className="flex items-center gap-3 py-1.5">
                                <span className="text-sm font-semibold text-slate-500 min-w-[100px]">
                                    {kvMatch[1]}
                                </span>
                                {isVerdict ? (
                                    <VerdictBadge text={kvMatch[2]} />
                                ) : (
                                    <span className="text-base font-medium text-slate-800">
                                        {kvMatch[2]}
                                    </span>
                                )}
                            </div>
                        );
                    }

                    // Regular paragraph
                    return (
                        <p key={i} className="text-base text-slate-700 leading-relaxed">
                            {trimmed}
                        </p>
                    );
                })}
            </div>
        </div>
    );
}

// ─── Formatted Content Renderer ──────────────────────────────────────────────

function FormattedContent({ text }) {
    if (!text) {
        return (
            <div className="text-center py-12">
                <div className="w-16 h-16 bg-slate-100 rounded-2xl flex items-center justify-center mx-auto mb-4">
                    <svg className="w-8 h-8 text-slate-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M20 13V6a2 2 0 00-2-2H6a2 2 0 00-2 2v7m16 0v5a2 2 0 01-2 2H6a2 2 0 01-2-2v-5m16 0h-2.586a1 1 0 00-.707.293l-2.414 2.414a1 1 0 01-.707.293h-3.172a1 1 0 01-.707-.293l-2.414-2.414A1 1 0 006.586 13H4" />
                    </svg>
                </div>
                <p className="text-slate-500 font-semibold">No data available for this section</p>
            </div>
        );
    }

    const sections = parseTextSections(text);

    if (sections.length === 0) {
        // Fallback: render as plain paragraphs
        return (
            <div className="space-y-4">
                {text.split('\n\n').filter(p => p.trim()).map((para, idx) => (
                    <p key={idx} className="text-base text-slate-700 leading-relaxed">
                        {para.replace(/\*\*/g, '')}
                    </p>
                ))}
            </div>
        );
    }

    return (
        <div className="space-y-2">
            {sections.map((section, idx) => (
                <RenderSection key={idx} section={section} index={idx} />
            ))}
        </div>
    );
}

// ─── RAG Sources Panel ───────────────────────────────────────────────────────

function RagSourcesPanel({ ragSources }) {
    if (!ragSources || ragSources.length === 0) {
        return (
            <div className="text-center py-12">
                <div className="w-20 h-20 bg-purple-50 rounded-2xl flex items-center justify-center mx-auto mb-4">
                    <svg className="w-10 h-10 text-purple-300" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19.428 15.428a2 2 0 00-1.022-.547l-2.387-.477a6 6 0 00-3.86.517l-.318.158a6 6 0 01-3.86.517L6.05 15.21a2 2 0 00-1.806.547M8 4h8l-1 1v5.172a2 2 0 00.586 1.414l5 5c1.26 1.26.367 3.414-1.415 3.414H4.828c-1.782 0-2.674-2.154-1.414-3.414l5-5A2 2 0 009 10.172V5L8 4z" />
                    </svg>
                </div>
                <p className="text-slate-500 font-semibold">No knowledge base matches</p>
                <p className="text-sm text-slate-400 mt-2">RAG retrieval did not find relevant legal context for this analysis</p>
            </div>
        );
    }

    return (
        <div className="space-y-3">
            <h3 className="text-lg font-bold text-slate-900 mb-4 flex items-center gap-2">
                <span className="w-8 h-8 bg-gradient-to-br from-purple-500 to-violet-600 rounded-lg flex items-center justify-center">
                    <svg className="w-4 h-4 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19.428 15.428a2 2 0 00-1.022-.547l-2.387-.477a6 6 0 00-3.86.517l-.318.158a6 6 0 01-3.86.517L6.05 15.21a2 2 0 00-1.806.547M8 4h8l-1 1v5.172a2 2 0 00.586 1.414l5 5c1.26 1.26.367 3.414-1.415 3.414H4.828c-1.782 0-2.674-2.154-1.414-3.414l5-5A2 2 0 009 10.172V5L8 4z" />
                    </svg>
                </span>
                Knowledge Base Matches
            </h3>
            {ragSources.map((source, i) => (
                <div
                    key={i}
                    className="p-4 bg-gradient-to-r from-purple-50 to-violet-50 rounded-xl border border-purple-200 hover:border-purple-300 transition-all duration-200 animate-fade-in"
                    style={{ animationDelay: `${i * 100}ms` }}
                >
                    <div className="flex items-center justify-between mb-2">
                        <span className="text-sm font-bold text-purple-700 flex items-center gap-2">
                            <span className="w-6 h-6 bg-purple-200 rounded-full flex items-center justify-center text-xs font-black text-purple-700">
                                {i + 1}
                            </span>
                            {source.source || "Legal Knowledge Base"}
                        </span>
                        <span className={`text-xs font-semibold px-2.5 py-1 rounded-full ${
                            source.relevance >= 0.5 ? 'bg-emerald-100 text-emerald-700' :
                            source.relevance >= 0.2 ? 'bg-amber-100 text-amber-700' :
                            'bg-slate-100 text-slate-600'
                        }`}>
                            {(source.relevance * 100).toFixed(0)}% match
                        </span>
                    </div>
                    <p className="text-sm text-slate-700 leading-relaxed">
                        {source.text?.substring(0, 300)}{source.text?.length > 300 ? '...' : ''}
                    </p>
                </div>
            ))}
        </div>
    );
}

// ─── Main Component ──────────────────────────────────────────────────────────

export default function AnalysisResults({ data }) {
    const tabs = [
        {
            name: "Summary",
            emoji: "📖",
            icon: (
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                </svg>
            )
        },
        {
            name: "Laws Used",
            emoji: "📜",
            icon: (
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253" />
                </svg>
            )
        },
        {
            name: "Past Cases",
            emoji: "📚",
            icon: (
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10" />
                </svg>
            )
        },
        {
            name: "Consistency",
            emoji: "✅",
            icon: (
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
            )
        },
        {
            name: "Knowledge Base",
            emoji: "🧠",
            icon: (
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19.428 15.428a2 2 0 00-1.022-.547l-2.387-.477a6 6 0 00-3.86.517l-.318.158a6 6 0 01-3.86.517L6.05 15.21a2 2 0 00-1.806.547M8 4h8l-1 1v5.172a2 2 0 00.586 1.414l5 5c1.26 1.26.367 3.414-1.415 3.414H4.828c-1.782 0-2.674-2.154-1.414-3.414l5-5A2 2 0 009 10.172V5L8 4z" />
                </svg>
            )
        },
        {
            name: "Sources",
            emoji: "🌐",
            icon: (
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13.828 10.172a4 4 0 00-5.656 0l-4 4a4 4 0 105.656 5.656l1.102-1.101m-.758-4.899a4 4 0 005.656 0l4-4a4 4 0 00-5.656-5.656l-1.1 1.1" />
                </svg>
            )
        }
    ];

    const [active, setActive] = useState(0);

    // Extract verdict from summary for the top badge
    const extractVerdict = () => {
        if (!data?.summary) return null;
        const match = data.summary.match(/Verdict:\s*(.+?)(?:\n|$)/i);
        if (match) return match[1].trim();
        return null;
    };

    const verdict = extractVerdict();

    const sections = [
        // Tab 0: Summary
        <FormattedContent text={data.summary} />,

        // Tab 1: Laws Used
        <FormattedContent text={data.laws} />,

        // Tab 2: Past Cases (Precedents)
        <FormattedContent text={data.precedents || data.analysis} />,

        // Tab 3: Consistency Check (Logic Audit)
        <FormattedContent text={data.logic_audit || ""} />,

        // Tab 4: Knowledge Base (RAG Sources)
        <RagSourcesPanel ragSources={data.rag_sources} />,

        // Tab 5: Web Sources
        data.web_sources?.length > 0 ? (
            <div className="space-y-3">
                <h3 className="text-lg font-bold text-slate-900 mb-4 flex items-center gap-2">
                    <span className="w-8 h-8 bg-gradient-to-br from-indigo-500 to-violet-600 rounded-lg flex items-center justify-center">
                        <svg className="w-4 h-4 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
                        </svg>
                    </span>
                    Referenced Web Sources
                </h3>
                {data.web_sources.map((s, i) => (
                    <a
                        key={i}
                        href={s.url}
                        target="_blank"
                        rel="noreferrer"
                        className="flex items-start gap-4 p-5 bg-gradient-to-r from-blue-50 to-indigo-50 hover:from-blue-100 hover:to-indigo-100 rounded-xl border border-indigo-200 hover:border-indigo-300 transition-all duration-200 group animate-fade-in"
                        style={{ animationDelay: `${i * 100}ms` }}
                    >
                        <div className="flex-shrink-0 w-12 h-12 bg-gradient-to-br from-indigo-500 to-violet-600 rounded-xl flex items-center justify-center shadow-md group-hover:scale-110 transition-transform">
                            <svg className="w-6 h-6 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
                            </svg>
                        </div>
                        <div className="flex-1 min-w-0">
                            <p className="text-base font-bold text-indigo-700 group-hover:text-indigo-900 mb-2 line-clamp-2">
                                {s.title}
                            </p>
                            <p className="text-sm text-slate-600 truncate mb-2">
                                {s.url}
                            </p>
                            {s.snippet && (
                                <p className="text-sm text-slate-600 leading-relaxed">
                                    {s.snippet}
                                </p>
                            )}
                        </div>
                        <svg className="w-5 h-5 text-indigo-400 group-hover:translate-x-1 transition-transform flex-shrink-0 mt-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                        </svg>
                    </a>
                ))}
            </div>
        ) : (
            <div className="text-center py-12">
                <div className="w-20 h-20 bg-slate-100 rounded-2xl flex items-center justify-center mx-auto mb-4">
                    <svg className="w-10 h-10 text-slate-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13.828 10.172a4 4 0 00-5.656 0l-4 4a4 4 0 105.656 5.656l1.102-1.101m-.758-4.899a4 4 0 005.656 0l4-4a4 4 0 00-5.656-5.656l-1.1 1.1" />
                    </svg>
                </div>
                <p className="text-slate-500 font-semibold">No sources available</p>
                <p className="text-sm text-slate-400 mt-2">Web research did not return any sources for this analysis</p>
            </div>
        )
    ];

    return (
        <div>
            {/* Verdict Badge Hero */}
            {verdict && (
                <div className="px-6 pt-6 pb-2 flex items-center justify-center">
                    <VerdictBadge text={verdict} />
                </div>
            )}

            {/* Tabs Navigation */}
            <div className="flex flex-wrap gap-2 px-6 pt-4 pb-4 border-b border-slate-200 bg-gradient-to-r from-slate-50 to-slate-100">
                {tabs.map((tab, i) => (
                    <button
                        key={i}
                        onClick={() => setActive(i)}
                        className={`flex items-center gap-2 px-4 py-2.5 rounded-xl text-sm font-bold transition-all duration-200 ${active === i
                            ? "bg-gradient-to-r from-indigo-600 to-violet-600 text-white shadow-lg scale-105"
                            : "text-slate-600 hover:text-indigo-600 hover:bg-white/70 hover:shadow-sm"
                            }`}
                    >
                        <span className="text-base">{tab.emoji}</span>
                        <span className={active === i ? "text-white" : ""}>
                            {tab.icon}
                        </span>
                        <span className="hidden sm:inline">{tab.name}</span>
                    </button>
                ))}
            </div>

            {/* Content Area */}
            <div className="p-6 sm:p-8">
                <div className="max-w-none">
                    {sections[active] || (
                        <div className="text-center py-12">
                            <div className="w-16 h-16 bg-slate-100 rounded-2xl flex items-center justify-center mx-auto mb-4">
                                <svg className="w-8 h-8 text-slate-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M20 13V6a2 2 0 00-2-2H6a2 2 0 00-2 2v7m16 0v5a2 2 0 01-2 2H6a2 2 0 01-2-2v-5m16 0h-2.586a1 1 0 00-.707.293l-2.414 2.414a1 1 0 01-.707.293h-3.172a1 1 0 01-.707-.293l-2.414-2.414A1 1 0 006.586 13H4" />
                                </svg>
                            </div>
                            <p className="text-slate-500 font-semibold">No data available for this section</p>
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
}