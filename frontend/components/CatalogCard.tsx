import React from "react";
import Link from "next/link";

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

export default function CatalogCard({ app }: { app: AppData }) {
  const formattedDate = app.last_synced_at
    ? new Date(app.last_synced_at).toLocaleDateString("en-IN", {
        day: "numeric",
        month: "short",
        year: "numeric",
      })
    : "Never";

  const fallbackLetter = app.display_name.charAt(0).toUpperCase();

  return (
    <Link href={`/apps/${app.id}`}>
      <div className="group relative block rounded-2xl border border-gray-800 bg-[#151B2C] p-6 shadow-lg transition-all duration-300 hover:-translate-y-1 hover:border-indigo-500/50 hover:bg-[#1C253B] hover:shadow-indigo-500/10">
        
        {/* Flag, Country, & Scrape Status badges */}
        <div className="absolute right-6 top-6 flex items-center gap-2">
          {app.scrape_status && app.scrape_status !== "ready" && (
            <span className={`rounded-md border px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider ${
              app.scrape_status === "failed" ? "bg-red-500/10 border-red-500/30 text-red-400" :
              app.scrape_status === "running" ? "bg-amber-500/10 border-amber-500/30 text-amber-400 animate-pulse" :
              "bg-gray-500/10 border-gray-500/30 text-gray-400"
            }`}>
              {app.scrape_status === "running" ? "Syncing" : app.scrape_status}
            </span>
          )}
          <div className="rounded-md bg-gray-900 border border-gray-800 px-2 py-0.5 text-xs text-gray-400 font-semibold uppercase tracking-wider">
            🇮🇳 {app.country}
          </div>
        </div>

        {/* Logo and Title */}
        <div className="flex items-center gap-4">
          {app.app_icon_url ? (
            <img
              src={app.app_icon_url}
              alt={app.display_name}
              className="w-12 h-12 rounded-xl object-cover border border-gray-800 bg-gray-950 flex-shrink-0"
              onError={(e) => {
                (e.target as HTMLElement).style.display = 'none';
                const parent = (e.target as HTMLElement).parentElement;
                if (parent) {
                  const fallback = parent.querySelector('.fallback-icon');
                  if (fallback) fallback.classList.remove('hidden');
                }
              }}
            />
          ) : null}
          <div
            className={`fallback-icon w-12 h-12 rounded-xl bg-gradient-to-br from-indigo-600 to-purple-600 flex items-center justify-center font-bold text-gray-100 flex-shrink-0 border border-indigo-500/30 ${
              app.app_icon_url ? "hidden" : ""
            }`}
          >
            {fallbackLetter}
          </div>
          <h3 className="text-xl font-bold text-gray-100 group-hover:text-indigo-400 transition-colors line-clamp-1">
            {app.display_name}
          </h3>
        </div>

        {/* Platforms Badge tags */}
        <div className="mt-4 flex gap-2">
          {app.play_package && (
            <span className="rounded-full bg-emerald-500/10 border border-emerald-500/30 px-3 py-1 text-xs font-medium text-emerald-400">
              Google Play
            </span>
          )}
          {app.ios_app_id && (
            <span className="rounded-full bg-sky-500/10 border border-sky-500/30 px-3 py-1 text-xs font-medium text-sky-400">
              App Store
            </span>
          )}
        </div>

        {/* Stats */}
        <div className="mt-6 grid grid-cols-2 gap-4 border-t border-gray-800/80 pt-4 text-sm">
          <div>
            <span className="block text-gray-500">Reviews</span>
            <span className="font-bold text-gray-200">{app.review_count.toLocaleString()}</span>
          </div>
          <div>
            <span className="block text-gray-500">Last Synced</span>
            <span className="font-medium text-gray-300">{formattedDate}</span>
          </div>
        </div>
      </div>
    </Link>
  );
}
