"use client";

import React, { useState, useRef, useEffect } from "react";
import ReviewModal from "./ReviewModal";

interface Citation {
  review_id: string;
  platform: string;
  rating: number;
  review_date: string;
  snippet: string;
}

interface Message {
  sender: "user" | "assistant";
  text: string;
  metrics?: any;
  citations?: Citation[];
}

export default function ChatPanel({ appId }: { appId: string }) {
  const [messages, setMessages] = useState<Message[]>([
    {
      sender: "assistant",
      text: "Greetings! I can help you identify key user pain points, track feature requests, spot emerging issues, and compare feedback across platforms and time periods. What would you like to explore?",
    },
  ]);
  const [input, setInput] = useState<string>("");
  const [sending, setSending] = useState<boolean>(false);
  const [activeCitation, setActiveCitation] = useState<Citation | null>(null);

  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, sending]);

  const handleSend = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim() || sending) return;

    const userText = input;
    setInput("");
    setMessages((prev) => [...prev, { sender: "user", text: userText }]);
    setSending(true);

    const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

    try {
      const res = await fetch(`${apiUrl}/apps/${appId}/chat`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ message: userText }),
      });

      if (!res.ok) {
        throw new Error(`Chat API error | status=${res.status}`);
      }

      const data = await res.json();
      
      setMessages((prev) => [
        ...prev,
        {
          sender: "assistant",
          text: data.answer,
          metrics: data.metrics,
          citations: data.citations || [],
        },
      ]);
    } catch (err: any) {
      console.error(err);
      setMessages((prev) => [
        ...prev,
        {
          sender: "assistant",
          text: "⚠️ I encountered an error attempting to process your request. Please ensure your backend server is online and try again.",
        },
      ]);
    } finally {
      setSending(false);
    }
  };

  return (
    <div className="flex flex-col h-full border border-gray-800/80 rounded-2xl bg-[#0E1320] overflow-hidden">
      {/* Panel Header */}
      <div className="border-b border-gray-800 bg-[#12192C] px-6 py-4 flex items-center gap-2">
        <span className="text-lg">💬</span>
        <h4 className="font-bold text-gray-200">ReviewLens</h4>
      </div>

      {/* Message Feed */}
      <div className="flex-1 overflow-y-auto p-6 space-y-6 bg-[#0B0F19]/60">
        {messages.map((msg, i) => (
          <div
            key={i}
            className={`flex flex-col max-w-[85%] ${
              msg.sender === "user" ? "ml-auto items-end" : "mr-auto items-start"
            }`}
          >
            {/* Message Bubble */}
            <div
              className={`rounded-2xl px-5 py-3 text-sm leading-relaxed ${
                msg.sender === "user"
                  ? "bg-indigo-600 text-gray-100 rounded-tr-none shadow-md shadow-indigo-600/10 border border-indigo-500/20"
                  : "bg-[#182035] border border-gray-800 text-gray-200 rounded-tl-none"
              }`}
            >
              {msg.text}
            </div>

            {/* RAG Metrics summary banner */}
            {msg.metrics && Object.keys(msg.metrics).length > 0 && (
              <div className="mt-2 w-full rounded-xl bg-gray-950/80 border border-gray-800/60 p-3 text-xs text-gray-400 font-mono">
                <span className="font-bold text-indigo-400 uppercase tracking-wider block mb-1">Calculated aggregates:</span>
                {JSON.stringify(msg.metrics, null, 2)}
              </div>
            )}

            {/* RAG Citations cards */}
            {msg.citations && msg.citations.length > 0 && (
              <div className="mt-3 flex flex-wrap gap-2 w-full">
                {msg.citations.map((cit, idx) => (
                  <button
                    key={idx}
                    onClick={() => setActiveCitation(cit)}
                    className="flex items-center gap-2 rounded-lg border border-gray-800 bg-[#121829] hover:bg-[#1C253E] hover:border-indigo-500/30 px-3 py-1.5 text-xs text-gray-400 hover:text-gray-200 transition-all text-left"
                  >
                    <span>★ {cit.rating}</span>
                    <span className="font-medium truncate max-w-[120px]">
                      "{cit.snippet}"
                    </span>
                  </button>
                ))}
              </div>
            )}
          </div>
        ))}

        {sending && (
          <div className="flex mr-auto items-start max-w-[85%]">
            <div className="rounded-2xl px-5 py-3.5 text-sm bg-[#182035] border border-gray-800 text-gray-400 rounded-tl-none flex items-center gap-2">
              <span className="flex gap-1">
                <span className="h-2 w-2 rounded-full bg-indigo-500 animate-bounce" style={{ animationDelay: "0ms" }} />
                <span className="h-2 w-2 rounded-full bg-indigo-500 animate-bounce" style={{ animationDelay: "150ms" }} />
                <span className="h-2 w-2 rounded-full bg-indigo-500 animate-bounce" style={{ animationDelay: "300ms" }} />
              </span>
              Copilot is analyzing reviews...
            </div>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* Suggestion Pills */}
      <div className="px-6 pb-3 pt-2 border-t border-gray-800/40 bg-[#121829]/60 flex flex-wrap gap-2">
        <span className="text-[10px] text-gray-500 font-bold w-full mb-0.5 uppercase tracking-wider">💡 Quick Prompts</span>
        {[
          { label: "🔴 Crashes & Bugs", text: "Are there any recent crashes or login bugs reported?" },
          { label: "💡 Feature Requests", text: "What feature requests or improvements are users asking for?" },
          { label: "🌟 iOS vs Android", text: "Compare the positive and negative feedback between iOS and Android." },
          { label: "📈 Top Complaints", text: "What are the top 3 complaints shared by negative reviews?" }
        ].map((s, idx) => (
          <button
            key={idx}
            type="button"
            onClick={() => setInput(s.text)}
            className="rounded-full border border-gray-800 hover:border-indigo-500/40 bg-gray-950 hover:bg-indigo-500/5 px-2.5 py-0.5 text-xs text-gray-400 hover:text-gray-200 transition-all font-medium"
          >
            {s.label}
          </button>
        ))}
      </div>

      {/* Input Form Box (Claude web client style) */}
      <div className="border-t border-gray-800 bg-[#111726] p-4">
        <form onSubmit={handleSend} className="relative flex items-center bg-[#1D2436] border border-gray-750 focus-within:border-gray-500 rounded-xl px-2 py-1.5 transition-all shadow-inner">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Ask about logins, UI feedback, star aggregates..."
            disabled={sending}
            className="flex-1 bg-transparent border-0 outline-none focus:outline-none focus:ring-0 px-3 py-1.5 text-sm text-gray-100 placeholder-gray-500 disabled:opacity-50"
          />
          <button
            type="submit"
            disabled={sending || !input.trim()}
            className="rounded-lg bg-indigo-600 hover:bg-indigo-500 disabled:bg-gray-800 disabled:text-gray-600 text-gray-100 px-4 py-1.5 text-xs font-bold transition-all flex items-center gap-1.5 shadow-md flex-shrink-0"
          >
            <span>Send</span>
            <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2.5" d="M14 5l7 7m0 0l-7 7m7-7H3"/>
            </svg>
          </button>
        </form>
      </div>

      {/* Popup Citation modal details */}
      {activeCitation && (
        <ReviewModal citation={activeCitation} onClose={() => setActiveCitation(null)} />
      )}
    </div>
  );
}
