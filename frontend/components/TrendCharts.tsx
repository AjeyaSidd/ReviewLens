"use client";
import React from "react";
import {
  ResponsiveContainer,
  ComposedChart,
  Line,
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
  const chartData = data.map((d) => {
    const [year, month, day] = d.date.split("-").map(Number);
    const localDate = new Date(year, month - 1, day);
    const displayDate = localDate.toLocaleDateString("en-IN", {
      day: "numeric",
      month: "short",
    });
    return { ...d, displayDate };
  });

  chartData.sort((a, b) => a.date.localeCompare(b.date));

  const smoothed = chartData.map((d, i) => {
    const window = chartData.slice(Math.max(0, i - 4), i + 1);
    const avg = window.reduce((sum, w) => sum + w.avg_rating, 0) / window.length;
    return { ...d, avg_rating_smooth: parseFloat(avg.toFixed(2)) };
  });

  if (smoothed.length === 0) {
    return (
      <div className="flex h-64 items-center justify-center rounded-2xl border border-gray-800 bg-[#151B2C]/20 text-gray-500">
        No daily rollup historical logs found for the selected date range.
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="rounded-2xl border border-gray-800 bg-[#151B2C]/30 p-6">
        <h4 className="mb-6 text-lg font-bold text-gray-300">Daily Rating Trend</h4>
        <div className="h-64 w-full">
          <ResponsiveContainer width="100%" height="100%">
            <ComposedChart data={smoothed} margin={{ top: 10, right: 30, left: 0, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#1F2937" />
              <XAxis
                dataKey="displayDate"
                stroke="#9CA3AF"
                fontSize={11}
                tickLine={false}
              />
              <YAxis
                yAxisId="rating"
                stroke="#9CA3AF"
                fontSize={11}
                domain={[1, 5]}
                tickCount={5}
                tickLine={false}
              />
              <YAxis
                yAxisId="count"
                orientation="right"
                stroke="#4B5563"
                fontSize={11}
                tickLine={false}
              />
              <Tooltip
                contentStyle={{
                  backgroundColor: "#151B2C",
                  borderColor: "#374151",
                  borderRadius: "12px",
                }}
                labelStyle={{ fontWeight: "bold", color: "#9CA3AF" }}
              />
              <Legend verticalAlign="top" height={36} iconType="circle" />
              <Bar
                yAxisId="count"
                name="Review Count"
                dataKey="review_count"
                fill="#6366F1"
                opacity={0.3}
                radius={[2, 2, 0, 0]}
              />
              <Line
                yAxisId="rating"
                name="Avg Rating (5-day)"
                type="monotone"
                dataKey="avg_rating_smooth"
                stroke="#A78BFA"
                strokeWidth={2.5}
                dot={false}
                activeDot={{ r: 5 }}
              />
            </ComposedChart>
          </ResponsiveContainer>
        </div>
      </div>
    </div>
  );
}