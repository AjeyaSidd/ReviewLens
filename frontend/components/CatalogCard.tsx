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
}

export default function CatalogCard({ app }: { app: AppData }) {
  const formattedDate = app.last_synced_at
    ? new Date(app.last_synced_at).toLocaleDateString("en-IN", {
        day: "numeric",
        month: "short",
        year: "numeric",
      })
    : "Never";

  return (
    <Link href={`/apps/${app.id}`}>
      <div className="group relative block rounded-2xl border border-gray-800 bg-[#151B2C] p-6 shadow-lg transition-all duration-300 hover:-translate-y-1 hover:border-indigo-500/50 hover:bg-[#1C253B] hover:shadow-indigo-500/10">
        
        {/* Flag & Country badge */}
        <div className="absolute right-6 top-6 rounded-md bg-gray-900 border border-gray-800 px-2 py-0.5 text-xs text-gray-400 font-semibold uppercase tracking-wider">
          🇮🇳 {app.country}
        </div>

        {/* Title */}
        <h3 className="text-xl font-bold text-gray-100 group-hover:text-indigo-400 transition-colors">
          {app.display_name}
        </h3>

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
