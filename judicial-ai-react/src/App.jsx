import React, { useState, useEffect } from "react";
import Header from "./components/Header";
import Sidebar from "./components/Sidebar";
import HistorySidebar from "./components/HistorySidebar";
import WelcomeScreen from "./components/WelcomeScreen";
import AnalysisResults from "./components/AnalysisResults";
import ProgressSteps from "./components/ProgressSteps";
import { analyzeDocument, fetchAnalysisById } from "./services/api";

export default function App() {
    const [file, setFile] = useState(null);
    const [loading, setLoading] = useState(false);
    const [data, setData] = useState(null);
    const [error, setError] = useState(null);
    const [progress, setProgress] = useState(0);
    const [step, setStep] = useState(0);
    const [historyOpen, setHistoryOpen] = useState(false);

    const steps = [15, 30, 50, 70, 85, 95];

    useEffect(() => {
        if (loading && step < steps.length) {
            const t = setTimeout(() => {
                setProgress(steps[step]);
                setStep((s) => s + 1);
            }, 600);
            return () => clearTimeout(t);
        }
    }, [loading, step]);

    const handleFileUpload = (newFile) => {
        setFile(newFile);
        setData(null);
        setError(null);
        setProgress(0);
        setStep(0);
    };

    const runAnalysis = async () => {
        if (!file) return;
        setLoading(true);
        setError(null);
        setData(null);
        setProgress(10);
        setStep(0);

        try {
            const res = await analyzeDocument(file);
            if (res.success && res.data) {
                setData(res.data);
                setProgress(100);
            } else {
                setError(res.error || "Analysis failed. Please check the backend connection or try another PDF.");
            }
        } catch (err) {
            setError(err.message || "An unexpected error occurred during processing.");
        } finally {
            setLoading(false);
        }
    };

    const handleSelectHistory = async (id) => {
        try {
            const res = await fetchAnalysisById(id);
            if (res.success && res.data) {
                setData(res.data);
                setFile({ name: res.data.filename });
                setError(null);
                setHistoryOpen(false);
            }
        } catch (err) {
            console.error("Error loading historical analysis:", err);
        }
    };

    return (
        <div className="flex h-screen bg-gradient-to-br from-slate-50 via-blue-50 to-indigo-50 relative overflow-hidden">
            {/* Decorative background elements */}
            <div className="absolute top-0 right-0 w-96 h-96 bg-gradient-to-br from-blue-200/30 to-indigo-300/30 rounded-full blur-3xl -translate-y-1/2 translate-x-1/2"></div>
            <div className="absolute bottom-0 left-0 w-96 h-96 bg-gradient-to-tr from-teal-200/30 to-cyan-300/30 rounded-full blur-3xl translate-y-1/2 -translate-x-1/2"></div>

            <HistorySidebar
                isOpen={historyOpen}
                onClose={() => setHistoryOpen(false)}
                onSelectHistory={handleSelectHistory}
            />

            <Sidebar
                uploadedFile={file}
                onFileUpload={handleFileUpload}
                onOpenHistory={() => setHistoryOpen(true)}
            />

            <div className="flex-1 flex flex-col relative z-10">
                <Header />

                <main className="flex-1 overflow-y-auto p-8">
                    {!file && <WelcomeScreen />}

                    {/* Error Banner */}
                    {error && (
                        <div className="max-w-3xl mx-auto mb-6">
                            <div className="bg-red-50/90 backdrop-blur-xl border border-red-200 rounded-3xl p-6 shadow-xl flex items-start gap-4">
                                <div className="flex-shrink-0 w-12 h-12 bg-red-100 rounded-2xl flex items-center justify-center text-red-600">
                                    <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                                    </svg>
                                </div>
                                <div className="flex-1">
                                    <h3 className="text-lg font-bold text-red-900 mb-1">
                                        Analysis Error
                                    </h3>
                                    <p className="text-sm text-red-700 leading-relaxed mb-4">
                                        {error}
                                    </p>
                                    <button
                                        onClick={runAnalysis}
                                        className="px-5 py-2.5 bg-red-600 hover:bg-red-700 text-white text-sm font-semibold rounded-xl transition-all shadow-md hover:shadow-lg"
                                    >
                                        Try Again
                                    </button>
                                </div>
                            </div>
                        </div>
                    )}

                    {file && !data && !loading && (
                        <div className="max-w-3xl mx-auto">
                            <div className="bg-white/80 backdrop-blur-xl rounded-3xl shadow-2xl p-10 border border-white/50 hover:shadow-indigo-200/50 transition-all duration-300">
                                <div className="flex items-start gap-4">
                                    <div className="flex-shrink-0 w-12 h-12 bg-gradient-to-br from-indigo-500 to-violet-600 rounded-2xl flex items-center justify-center shadow-lg">
                                        <svg className="w-6 h-6 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                                        </svg>
                                    </div>
                                    <div className="flex-1">
                                        <h2 className="text-2xl font-bold text-slate-900 mb-2">
                                            Document Ready for Analysis
                                        </h2>
                                        <p className="text-sm text-slate-600 font-medium bg-slate-100 inline-block px-3 py-1 rounded-lg">
                                            {file.name}
                                        </p>
                                    </div>
                                </div>

                                <button
                                    onClick={runAnalysis}
                                    className="mt-8 w-full px-8 py-4 rounded-2xl bg-gradient-to-r from-indigo-600 via-violet-600 to-purple-600 text-white font-semibold shadow-xl hover:shadow-2xl hover:scale-[1.02] active:scale-[0.98] transition-all duration-200 flex items-center justify-center gap-3 group"
                                >
                                    <svg className="w-5 h-5 group-hover:rotate-12 transition-transform" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
                                    </svg>
                                    Start AI Analysis
                                </button>
                            </div>
                        </div>
                    )}

                    {loading && (
                        <div className="max-w-3xl mx-auto">
                            <div className="bg-white/80 backdrop-blur-xl rounded-3xl shadow-2xl p-10 border border-white/50">
                                <div className="flex items-center gap-3 mb-6">
                                    <div className="relative">
                                        <div className="w-10 h-10 bg-gradient-to-br from-indigo-500 to-violet-600 rounded-xl animate-pulse"></div>
                                        <div className="absolute inset-0 bg-gradient-to-br from-indigo-500 to-violet-600 rounded-xl blur-lg opacity-50 animate-pulse"></div>
                                    </div>
                                    <h3 className="text-xl font-bold bg-gradient-to-r from-indigo-600 to-violet-600 bg-clip-text text-transparent">
                                        AI Agents Processing
                                    </h3>
                                </div>

                                <div className="relative h-4 bg-gradient-to-r from-slate-100 to-slate-200 rounded-full mb-6 overflow-hidden shadow-inner">
                                    <div
                                        className="absolute inset-0 bg-gradient-to-r from-indigo-500 via-violet-500 to-purple-500 rounded-full transition-all duration-500 ease-out shadow-lg"
                                        style={{ width: `${progress}%` }}
                                    >
                                        <div className="absolute inset-0 bg-gradient-to-r from-white/0 via-white/30 to-white/0 animate-shimmer"></div>
                                    </div>
                                </div>

                                <div className="text-center mb-6">
                                    <span className="text-2xl font-bold text-indigo-600">{progress}%</span>
                                    <span className="text-sm text-slate-500 ml-2">complete</span>
                                </div>

                                <ProgressSteps currentStep={step} />
                            </div>
                        </div>
                    )}

                    {data && (
                        <div className="max-w-6xl mx-auto">
                            <div className="mb-6 px-6 py-4 rounded-2xl bg-gradient-to-r from-emerald-500 via-teal-500 to-cyan-500 text-white font-semibold shadow-xl flex items-center justify-between animate-slide-in">
                                <div className="flex items-center gap-3">
                                    <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                                    </svg>
                                    <span>Analysis completed successfully</span>
                                </div>
                                <button
                                    onClick={() => {
                                        setData(null);
                                        setFile(null);
                                    }}
                                    className="text-xs bg-white/20 hover:bg-white/30 px-3 py-1.5 rounded-lg transition-colors"
                                >
                                    Analyze Another
                                </button>
                            </div>

                            <div className="bg-white/80 backdrop-blur-xl rounded-3xl shadow-2xl border border-white/50 overflow-hidden">
                                <AnalysisResults data={data} />
                            </div>
                        </div>
                    )}
                </main>
            </div>
        </div>
    );
}