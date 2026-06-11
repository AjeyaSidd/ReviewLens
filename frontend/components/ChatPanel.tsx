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
      text: "Hello! I am your App Review Intelligence assistant. Ask me anything about user experience feedback or recent trend rollups!",
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
    <div className="flex flex-col h-full border border-gray-800 rounded-2xl bg-[#121826]/40 overflow-hidden backdrop-blur-md">
      {/* Panel Header */}
      <div className="border-b border-gray-800 bg-[#151B2C]/80 px-6 py-4 flex items-center gap-2">
        <span className="text-lg">💬</span>
        <h4 className="font-bold text-gray-200">AI Review Copilot</h4>
      </div>

      {/* Message Feed */}
      <div className="flex-1 overflow-y-auto p-6 space-y-6">
        {messages.map((msg, i) => (
          <div
            key={i}
            className={`flex flex-col max-w-[85%] ${
              msg.sender === "user" ? "ml-auto items-end" : "mr-auto items-start"
            }`}
          >
            {/* Message Bubble */}
            <div
              className={`rounded-2xl px-5 py-3.5 text-sm leading-relaxed ${
                msg.sender === "user"
                  ? "bg-indigo-600 text-gray-100 rounded-tr-none shadow-md shadow-indigo-600/10"
                  : "bg-[#1C253B] border border-gray-800/80 text-gray-300 rounded-tl-none"
              }`}
            >
              {msg.text}
            </div>

            {/* RAG Metrics summary banner */}
            {msg.metrics && Object.keys(msg.metrics).length > 0 && (
              <div className="mt-2 w-full rounded-xl bg-gray-900/60 border border-gray-800 p-3 text-xs text-gray-400 font-mono">
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
                    className="flex items-center gap-2 rounded-lg border border-gray-800/60 bg-[#161C2C] hover:bg-[#1E273D] hover:border-indigo-500/30 px-3 py-1.5 text-xs text-gray-400 hover:text-gray-200 transition-all text-left"
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
            <div className="rounded-2xl px-5 py-3.5 text-sm bg-[#1C253B] border border-gray-800/80 text-gray-400 rounded-tl-none flex items-center gap-2">
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
      <div className="px-6 pb-3 pt-2 border-t border-gray-800/40 bg-[#121826]/20 flex flex-wrap gap-2">
        <span className="text-xs text-gray-500 font-semibold w-full mb-0.5">💡 Quick Prompts (Click to edit)</span>
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
            className="rounded-full border border-gray-800 hover:border-indigo-500/40 bg-gray-900/60 hover:bg-indigo-500/5 px-3 py-1 text-xs text-gray-400 hover:text-gray-200 transition-all font-medium"
          >
            {s.label}
          </button>
        ))}
      </div>

      {/* Input Form */}
      <form onSubmit={handleSend} className="border-t border-gray-800 bg-[#151B2C]/40 p-4 flex gap-2">
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Ask about logins, UI feedback, star aggregates..."
          disabled={sending}
          className="flex-1 rounded-xl border border-gray-800 bg-[#0B0F19] px-4 py-2.5 text-sm text-gray-200 placeholder-gray-600 focus:border-indigo-500/50 focus:outline-none transition-all disabled:opacity-50"
        />
        <button
          type="submit"
          disabled={sending || !input.trim()}
          className="rounded-xl bg-indigo-600 hover:bg-indigo-500 border border-indigo-500/20 px-5 py-2.5 text-sm font-semibold text-gray-100 transition-all disabled:opacity-50 shadow-md shadow-indigo-600/10"
        >
          Send
        </button>
      </form>

      {/* Popup Citation modal details */}
      {activeCitation && (
        <ReviewModal citation={activeCitation} onClose={() => setActiveCitation(null)} />
      )}
    </div>
  );
}
