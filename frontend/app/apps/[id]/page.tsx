"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import TrendCharts from "@/components/TrendCharts";
import ChatPanel from "@/components/ChatPanel";
import ReviewModal from "@/components/ReviewModal";

interface AppMetadata {
  id: string;
  display_name: string;
  country: string;
  play_package?: string;
  ios_app_id?: string;
  review_count: number;
  last_synced_at?: string;
  app_icon_url?: string;
}

interface Review {
  id: string;
  platform: string;
  rating: number;
  title?: string;
  body: string;
  sentiment?: string;
  review_date: string;
}

export default function AppDashboardPage({ params }: { params: { id: string } }) {
  const appId = params.id;

  const [app, setApp] = useState<AppMetadata | null>(null);
  const [trends, setTrends] = useState([]);
  const [reviews, setReviews] = useState<Review[]>([]);
  const [selectedReview, setSelectedReview] = useState<Review | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  // Date filters
  const [fromDate, setFromDate] = useState<string>("");
  const [toDate, setToDate] = useState<string>("");

  const fetchAppAndTrends = async () => {
    const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
    setLoading(true);
    setError(null);
    try {
      // 1. Fetch App Metadata
      const appRes = await fetch(`${apiUrl}/apps/${appId}`);
      if (!appRes.ok) {
        throw new Error("Failed to load app details. Is it synced and active?");
      }
      const appData = await appRes.json();
      setApp(appData);

      // 2. Fetch Aggregated Daily Rollups
      let trendsUrl = `${apiUrl}/apps/${appId}/trends`;
      const queryParams = [];
      if (fromDate) queryParams.push(`from_date=${fromDate}`);
      if (toDate) queryParams.push(`to_date=${toDate}`);
      if (queryParams.length > 0) {
        trendsUrl += `?${queryParams.join("&")}`;
      }

      const trendsRes = await fetch(trendsUrl);
      if (!trendsRes.ok) {
        throw new Error("Failed to load trends daily rollups.");
      }
      const trendsData = await trendsRes.json();
      setTrends(trendsData);

      // 3. Fetch Recent Reviews
      const reviewsRes = await fetch(`${apiUrl}/apps/${appId}/reviews?limit=50`);
      if (reviewsRes.ok) {
        const reviewsData = await reviewsRes.json();
        setReviews(reviewsData);
      }
    } catch (err: any) {
      console.error(err);
      setError(err.message || "Failed to load dashboard metrics.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchAppAndTrends();
  }, [appId]);

  const handleFilterSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    fetchAppAndTrends();
  };

  if (loading && !app) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-[#0B0F19]">
        <div className="text-center space-y-4">
          <div className="h-10 w-10 animate-spin rounded-full border-4 border-indigo-500 border-t-transparent mx-auto" />
          <p className="text-sm text-gray-400 font-medium">Loading app intelligence dashboard...</p>
        </div>
      </div>
    );
  }

  if (error && !app) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-[#0B0F19] p-6">
        <div className="rounded-2xl border border-red-500/20 bg-red-500/5 p-8 text-center max-w-md w-full">
          <span className="text-4xl">⚠️</span>
          <h4 className="mt-4 text-xl font-bold text-red-400 font-sans">Dashboard Unreachable</h4>
          <p className="mt-2 text-sm text-gray-400 leading-relaxed">{error}</p>
          <div className="mt-6 flex justify-center gap-4">
            <Link
              href="/"
              className="rounded-xl border border-gray-800 bg-gray-900 px-5 py-2 text-sm font-semibold text-gray-300 hover:bg-gray-800 transition-colors"
            >
              Back to Catalog
            </Link>
            <button
              onClick={fetchAppAndTrends}
              className="rounded-xl bg-indigo-600 px-5 py-2 text-sm font-semibold text-gray-100 hover:bg-indigo-500 transition-colors"
            >
              Retry
            </button>
          </div>
        </div>
      </div>
    );
  }

  const fallbackLetter = app?.display_name ? app.display_name.charAt(0).toUpperCase() : "";

  return (
    <div className="flex min-h-screen lg:h-screen flex-col bg-[#0B0F19] lg:overflow-hidden">
      {/* Merged Header banner - compact height */}
      <header className="border-b border-gray-800 bg-[#0F1524]/80 backdrop-blur-md z-40 flex-shrink-0">
        <div className="mx-auto max-w-7xl w-full px-6 py-3 flex flex-col md:flex-row justify-between items-center gap-4">
          <div className="flex items-center gap-4 w-full md:w-auto">
            <Link href="/" className="text-gray-500 hover:text-indigo-400 text-sm font-semibold transition-colors flex-shrink-0">
              ← Catalog
            </Link>
            <span className="h-4 w-px bg-gray-800 flex-shrink-0" />
            
            {/* Logo and Name */}
            <div className="flex items-center gap-3 min-w-0">
              {app?.app_icon_url ? (
                <img
                  src={app.app_icon_url}
                  alt={app.display_name}
                  className="w-8 h-8 rounded-lg object-cover border border-gray-800 bg-gray-950 flex-shrink-0"
                  onError={(e) => {
                    (e.target as HTMLElement).style.display = 'none';
                    const fallback = document.getElementById('header-fallback-icon');
                    if (fallback) fallback.classList.remove('hidden');
                  }}
                />
              ) : null}
              <div
                id="header-fallback-icon"
                className={`w-8 h-8 rounded-lg bg-gradient-to-br from-indigo-600 to-purple-600 flex items-center justify-center font-bold text-xs text-gray-100 flex-shrink-0 border border-indigo-500/30 ${
                  app?.app_icon_url ? "hidden" : ""
                }`}
              >
                {fallbackLetter}
              </div>
              <h2 className="text-lg font-black text-gray-100 tracking-tight truncate">
                {app?.display_name}
              </h2>
            </div>
            
            {/* Badges */}
            <div className="flex gap-1.5 flex-shrink-0">
              {app?.play_package && (
                <span className="rounded bg-emerald-500/10 border border-emerald-500/20 px-2 py-0.5 text-[10px] font-semibold text-emerald-400">Play Store</span>
              )}
              {app?.ios_app_id && (
                <span className="rounded bg-sky-500/10 border border-sky-500/20 px-2 py-0.5 text-[10px] font-semibold text-sky-400">App Store</span>
              )}
            </div>
          </div>

          {/* Quick stats compact banner */}
          <div className="flex items-center gap-6 text-xs text-gray-400 bg-gray-900/40 border border-gray-800/80 px-4 py-2 rounded-xl">
            <div>
              <span className="text-gray-500 font-medium mr-1.5">Total Reviews:</span>
              <span className="font-bold text-gray-200">{(app?.review_count || 0).toLocaleString()}</span>
            </div>
            <div className="w-px h-3 bg-gray-800" />
            <div>
              <span className="text-gray-500 font-medium mr-1.5">Synced:</span>
              <span className="font-semibold text-gray-300">
                {app?.last_synced_at
                  ? new Date(app.last_synced_at).toLocaleDateString("en-IN", {
                      day: "numeric",
                      month: "short",
                      hour: "2-digit",
                      minute: "2-digit",
                    })
                  : "Never"}
              </span>
            </div>
          </div>
        </div>
      </header>

      {/* Main split-screen container */}
      <main className="flex-1 overflow-y-auto lg:overflow-hidden p-6 max-w-7xl mx-auto w-full flex flex-col min-h-0">
        <div className="flex flex-col lg:flex-row h-full gap-6 min-h-0">
          
          {/* Left panel: Filters, Rating Trend Graph, Reviews Table */}
          <div className="w-full lg:w-1/2 flex flex-col h-full gap-4 overflow-hidden min-h-0">
            {/* Filters */}
            <div className="rounded-2xl border border-gray-800 bg-[#151B2C]/20 p-3 flex items-center justify-between gap-4 flex-shrink-0">
              <span className="text-xs font-bold text-gray-400">Filter Historical Trends</span>
              
              <form onSubmit={handleFilterSubmit} className="flex items-center gap-2">
                <input
                  type="date"
                  value={fromDate}
                  onChange={(e) => setFromDate(e.target.value)}
                  className="rounded-lg border border-gray-800 bg-[#0B0F19] px-2 py-1 text-[11px] font-semibold text-gray-400 focus:outline-none focus:border-indigo-500/50"
                />
                <span className="text-gray-600 text-xs">to</span>
                <input
                  type="date"
                  value={toDate}
                  onChange={(e) => setToDate(e.target.value)}
                  className="rounded-lg border border-gray-800 bg-[#0B0F19] px-2 py-1 text-[11px] font-semibold text-gray-400 focus:outline-none focus:border-indigo-500/50"
                />
                <button
                  type="submit"
                  className="rounded-lg bg-indigo-600 hover:bg-indigo-500 border border-indigo-500/20 px-3 py-1 text-[11px] font-bold text-gray-100 transition-colors shadow-md shadow-indigo-600/10"
                >
                  Apply
                </button>
              </form>
            </div>

            {/* Daily Rating Trend Graph */}
            <div className="flex-shrink-0">
              {loading ? (
                <div className="h-72 animate-pulse rounded-2xl border border-gray-800 bg-[#151B2C]/20" />
              ) : (
                <TrendCharts data={trends} />
              )}
            </div>

            {/* Reviews Table (Top 50 Recent Reviews) */}
            <div className="flex-1 min-h-[200px] flex flex-col border border-gray-800 rounded-2xl bg-[#121826]/40 overflow-hidden backdrop-blur-md">
              <div className="border-b border-gray-800 bg-[#151B2C]/80 px-4 py-3 flex items-center justify-between flex-shrink-0">
                <div className="flex items-center gap-2">
                  <span className="text-base">📝</span>
                  <h4 className="font-bold text-sm text-gray-200">Recent Scraped Reviews</h4>
                </div>
                <span className="rounded-full bg-indigo-500/10 border border-indigo-500/30 px-2 py-0.5 text-[10px] font-semibold text-indigo-400">
                  Latest 50
                </span>
              </div>

              <div className="flex-1 overflow-y-auto p-2">
                {reviews.length === 0 ? (
                  <div className="flex flex-col items-center justify-center h-full text-center text-gray-500 space-y-2 p-6">
                    <span className="text-3xl">📁</span>
                    <p className="text-sm font-medium text-gray-400">No reviews synced for this app yet.</p>
                  </div>
                ) : (
                  <div className="divide-y divide-gray-800/40">
                    {reviews.map((r) => (
                      <div
                        key={r.id}
                        onClick={() => setSelectedReview(r)}
                        className="py-2.5 hover:bg-[#1C253B]/40 cursor-pointer rounded-xl transition-all flex flex-col gap-1.5 group p-2"
                      >
                        <div className="flex justify-between items-center text-[10px]">
                          <div className="flex items-center gap-2">
                            {r.platform === "play_store" ? (
                              <span className="rounded bg-emerald-500/10 border border-emerald-500/30 px-1.5 py-0.5 font-bold text-[9px] text-emerald-400">Play Store</span>
                            ) : (
                              <span className="rounded bg-sky-500/10 border border-sky-500/30 px-1.5 py-0.5 font-bold text-[9px] text-sky-400">App Store</span>
                            )}
                            <span className="font-semibold text-amber-400">{"★".repeat(r.rating)}</span>
                          </div>
                          <div className="flex items-center gap-2">
                            {r.sentiment && (
                              <span
                                className={`rounded px-1.5 py-0.5 font-semibold text-[9px] ${
                                  r.sentiment === "POSITIVE"
                                    ? "bg-emerald-500/5 text-emerald-400 border border-emerald-500/20"
                                    : r.sentiment === "NEGATIVE"
                                    ? "bg-rose-500/5 text-rose-400 border border-rose-500/20"
                                    : "bg-gray-500/5 text-gray-400 border border-gray-500/20"
                                }`}
                              >
                                {r.sentiment}
                              </span>
                            )}
                            <span className="text-gray-500 font-mono text-[9px]">
                              {new Date(r.review_date).toLocaleDateString("en-IN", {
                                day: "numeric",
                                month: "short",
                              })}
                            </span>
                          </div>
                        </div>
                        <p className="text-xs text-gray-300 line-clamp-2 leading-relaxed group-hover:text-gray-100 transition-colors">
                          {r.title && <span className="font-bold block text-gray-200 mb-0.5">{r.title}</span>}
                          {r.body}
                        </p>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          </div>

          {/* Right panel: Chat UI */}
          <div className="w-full lg:w-1/2 h-[600px] lg:h-full overflow-hidden min-h-0 flex flex-col flex-shrink-0">
            <ChatPanel appId={appId} />
          </div>
        </div>
      </main>

      {/* Review details modal popup overlay */}
      {selectedReview && (
        <ReviewModal
          citation={{
            review_id: selectedReview.id,
            platform: selectedReview.platform,
            rating: selectedReview.rating,
            review_date: selectedReview.review_date,
            snippet: selectedReview.body,
          }}
          onClose={() => setSelectedReview(null)}
        />
      )}

      {/* Footer footer */}
      <footer className="border-t border-gray-800/80 bg-gray-950/20 py-4 text-center text-xs text-gray-500 flex-shrink-0">
        <p>© 2026 App Review Intelligence. All review data fetched from Google Play and Apple App Store public feeds.</p>
      </footer>
    </div>
  );
  );
}
