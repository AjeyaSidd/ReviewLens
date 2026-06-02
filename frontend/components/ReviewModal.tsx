import React from "react";

interface Citation {
  review_id: string;
  platform: string;
  rating: number;
  review_date: string;
  snippet: string;
  body?: string;  // optional full body fallback
}

export default function ReviewModal({
  citation,
  onClose,
}: {
  citation: Citation;
  onClose: () => void;
}) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4 animate-fadeIn">
      <div className="relative w-full max-w-xl rounded-2xl border border-gray-800 bg-[#151B2C] p-8 shadow-2xl shadow-black/80">
        
        {/* Close Button */}
        <button
          onClick={onClose}
          className="absolute right-6 top-6 rounded-full border border-gray-800 bg-gray-900 p-2 text-gray-400 hover:bg-gray-800 hover:text-gray-200 transition-colors"
        >
          ✕
        </button>

        {/* Modal Title */}
        <h4 className="text-xl font-bold text-gray-100 flex items-center gap-2">
          <span>📝</span> Source Citation Details
        </h4>

        {/* Citation Metadata */}
        <div className="mt-6 flex flex-wrap gap-4 border-b border-gray-800 pb-4 text-sm text-gray-400">
          <div>
            <span className="block text-xs text-gray-500 uppercase tracking-wider">Review ID</span>
            <span className="font-mono text-gray-300">{citation.review_id}</span>
          </div>
          <div>
            <span className="block text-xs text-gray-500 uppercase tracking-wider">Platform</span>
            <span className="font-semibold text-indigo-400 capitalize">
              {citation.platform.replace("_", " ")}
            </span>
          </div>
          <div>
            <span className="block text-xs text-gray-500 uppercase tracking-wider">Rating</span>
            <span className="font-bold text-amber-400">{"★".repeat(citation.rating)}</span>
          </div>
          <div>
            <span className="block text-xs text-gray-500 uppercase tracking-wider">Review Date</span>
            <span className="font-medium text-gray-300">
              {new Date(citation.review_date).toLocaleDateString("en-IN", {
                day: "numeric",
                month: "short",
                year: "numeric",
              })}
            </span>
          </div>
        </div>

        {/* Review body content */}
        <div className="mt-6 space-y-4">
          <div>
            <span className="block text-xs text-gray-500 uppercase tracking-wider">Cited Snippet</span>
            <blockquote className="mt-2 rounded-xl border-l-4 border-indigo-500 bg-indigo-500/5 p-4 text-sm text-gray-300 italic leading-relaxed">
              "{citation.snippet}"
            </blockquote>
          </div>
        </div>

        {/* Confirm OK footer */}
        <div className="mt-8 flex justify-end">
          <button
            onClick={onClose}
            className="rounded-xl bg-indigo-600 hover:bg-indigo-500 border border-indigo-500/20 px-6 py-2 text-sm font-semibold text-gray-100 transition-colors shadow-lg shadow-indigo-600/20"
          >
            Got it
          </button>
        </div>
      </div>
    </div>
  );
}
