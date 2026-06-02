"use client";

import React from "react";
import {
  ResponsiveContainer,
  LineChart,
  Line,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
} from "recharts";

interface RollupData {
  date: string;
  review_count: number;
  avg_rating: number;
  avg_sentiment: number | null;
  star_1: number;
  star_2: number;
  star_3: number;
  star_4: number;
  star_5: number;
}

export default function TrendCharts({ data }: { data: RollupData[] }) {
  // Format dates for display
  const chartData = data.map((d) => ({
    ...d,
    displayDate: new Date(d.date).toLocaleDateString("en-IN", {
      day: "numeric",
      month: "short",
    }),
    sentiment: d.avg_sentiment !== null ? parseFloat(d.avg_sentiment.toFixed(2)) : 0,
  }));

  if (chartData.length === 0) {
    return (
      <div className="flex h-64 items-center justify-center rounded-2xl border border-gray-800 bg-[#151B2C]/20 text-gray-500">
        No daily rollup historical logs found for the selected date range.
      </div>
    );
  }

  return (
    <div className="space-y-12">
      {/* Chart 1: Daily Rating Trend */}
      <div className="rounded-2xl border border-gray-800 bg-[#151B2C]/30 p-6">
        <h4 className="mb-6 text-lg font-bold text-gray-300">Daily Rating Trend</h4>
        <div className="h-72 w-full">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={chartData} margin={{ top: 10, right: 30, left: 0, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#1F2937" />
              <XAxis dataKey="displayDate" stroke="#9CA3AF" fontSize={11} tickLine={false} />
              <YAxis stroke="#9CA3AF" fontSize={11} domain={[1, 5]} tickCount={5} tickLine={false} />
              <Tooltip
                contentStyle={{ backgroundColor: "#151B2C", borderColor: "#374151", borderRadius: "12px" }}
                labelStyle={{ fontWeight: "bold", color: "#9CA3AF" }}
              />
              <Legend verticalAlign="top" height={36} iconType="circle" />
              <Line
                name="Average Rating"
                type="monotone"
                dataKey="avg_rating"
                stroke="#6366F1"
                strokeWidth={3}
                dot={{ r: 4, strokeWidth: 2, fill: "#0B0F19" }}
                activeDot={{ r: 6 }}
              />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Chart 2: Daily Sentiment score */}
      <div className="rounded-2xl border border-gray-800 bg-[#151B2C]/30 p-6">
        <h4 className="mb-6 text-lg font-bold text-gray-300">Daily Sentiment Scores (-1.0 to 1.0)</h4>
        <div className="h-72 w-full">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={chartData} margin={{ top: 10, right: 30, left: 0, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#1F2937" />
              <XAxis dataKey="displayDate" stroke="#9CA3AF" fontSize={11} tickLine={false} />
              <YAxis stroke="#9CA3AF" fontSize={11} domain={[-1, 1]} tickCount={5} tickLine={false} />
              <Tooltip
                contentStyle={{ backgroundColor: "#151B2C", borderColor: "#374151", borderRadius: "12px" }}
                labelStyle={{ fontWeight: "bold", color: "#9CA3AF" }}
              />
              <Legend verticalAlign="top" height={36} iconType="rect" />
              <Bar
                name="Avg Sentiment"
                dataKey="sentiment"
                fill="#10B981"
                radius={[4, 4, 0, 0]}
                maxBarSize={48}
              />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>
    </div>
  );
}
