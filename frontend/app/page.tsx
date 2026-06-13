"use client";

import React, { useEffect, useState } from "react";
import CatalogCard from "@/components/CatalogCard";

interface AppData {
  id: string;
  display_name: string;
  country: string;
  play_package?: string;
  ios_app_id?: string;
  review_count: number;
  last_synced_at?: string;
  app_icon_url?: string;
  scrape_status?: string;
}

export default function HomePage() {
  const [apps, setApps] = useState<AppData[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchCatalog = async () => {
      const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
      try {
        const res = await fetch(`${apiUrl}/catalog`);
        if (!res.ok) {
          throw new Error(`Failed to load catalog | status=${res.status}`);
        }
        const data = await res.json();
        setApps(data);
      } catch (err: any) {
        console.error(err);
        setError(err.message || "Failed to fetch catalog.");
      } finally {
        setLoading(false);
      }
    };

    fetchCatalog();
  }, []);

  return (
    <div className="flex min-h-screen flex-col bg-[#0B0F19]">
      {/* Header */}
      <header className="border-b border-gray-800 bg-[#0F1524]/60 backdrop-blur-md sticky top-0 z-40">
        <div className="mx-auto max-w-7xl px-6 py-2.5 flex justify-between items-center">
          <div className="flex items-center gap-3">
            <span className="text-xl">🧠</span>
            <h1 className="text-lg font-black bg-gradient-to-r from-indigo-400 to-purple-400 bg-clip-text text-transparent tracking-tight">
              ReviewLens
            </h1>
          </div>
          <div className="text-xs text-gray-500 font-medium">
            
          </div>
        </div>
      </header>

      {/* Main content */}
      <main className="flex-1 mx-auto max-w-7xl w-full px-6 py-6">
        {/* Hero Section */}
        <section className="mb-8 text-center max-w-2xl mx-auto">
          <h2 className="text-2xl md:text-3xl font-black text-gray-100 tracking-tight leading-tight">
            Know What Your Users Are Really Saying with{" "}
            <span className="bg-gradient-to-r from-indigo-400 via-violet-400 to-purple-400 bg-clip-text text-transparent">
              ReviewLens
            </span>
          </h2>
          <span className="block mt-2 text-base md:text-lg font-medium text-gray-400 leading-relaxed">
			Track daily ratings, spot trends over time, ask anything about your product, and get answers backed by real user feedback.
		</span>
        </section>

        {/* Catalog Grid */}
        <section>
          <div className="flex justify-between items-center mb-8 border-b border-gray-800/60 pb-4">
            <h3 className="text-2xl font-bold text-gray-200">Tracked Catalog</h3>
            <span className="rounded-full bg-gray-900 border border-gray-800 px-3 py-1 text-sm font-semibold text-gray-400">
              {apps.length} Active Apps
            </span>
          </div>

          {loading ? (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
              {[...Array(3)].map((_, i) => (
                <div key={i} className="h-48 animate-pulse rounded-2xl border border-gray-800 bg-[#151B2C]/50" />
              ))}
            </div>
          ) : error ? (
            <div className="rounded-2xl border border-red-500/20 bg-red-500/5 p-6 text-center">
              <span className="text-3xl">⚠️</span>
              <h4 className="mt-2 text-lg font-bold text-red-400">Connection Failed</h4>
              <p className="mt-2 text-sm text-gray-400">{error}</p>
              <p className="mt-1 text-xs text-gray-500">Is your FastAPI server running at {process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"}?</p>
            </div>
          ) : apps.length === 0 ? (
            <div className="rounded-2xl border border-gray-800 bg-[#151B2C]/30 p-12 text-center max-w-lg mx-auto">
              <span className="text-4xl">📁</span>
              <h4 className="mt-4 text-lg font-bold text-gray-300">Catalog is Empty</h4>
              <p className="mt-2 text-sm text-gray-400">
                Log in to the backend Swagger docs at `/docs` using your `X-Admin-Key` and run `POST /admin/apps` to register a tracked package!
              </p>
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
              {apps.map((app) => (
                <CatalogCard key={app.id} app={app} />
              ))}
            </div>
          )}
        </section>
      </main>

      {/* Footer */}
      <footer className="border-t border-gray-800/80 bg-gray-950/20 py-8 text-center text-xs text-gray-500">
        <p>© 2026 App Review Intelligence. All review data fetched from Google Play and Apple App Store public feeds.</p>
        <p className="mt-1">This product is for internal PM analysis and is not affiliated with Apple Inc. or Google LLC.</p>
      </footer>
    </div>
  );
}
