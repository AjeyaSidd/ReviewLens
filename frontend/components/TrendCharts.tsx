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
  // Helper to parse date locally to avoid timezone shifts
  const parseLocalDate = (dateStr: string) => {
    const [year, month, day] = dateStr.split("-").map(Number);
    return new Date(year, month - 1, day);
  };

  // Helper to get the Monday of the week for a given date
  const getMonday = (dateStr: string) => {
    const d = parseLocalDate(dateStr);
    const day = d.getDay();
    const diff = d.getDate() - day + (day === 0 ? -6 : 1);
    const monday = new Date(d.setDate(diff));
    const yyyy = monday.getFullYear();
    const mm = String(monday.getMonth() + 1).padStart(2, '0');
    const dd = String(monday.getDate()).padStart(2, '0');
    return `${yyyy}-${mm}-${dd}`;
  };

  // Group by week Monday
  const groups: { [key: string]: { date: string; total_rating_sum: number; total_reviews: number } } = {};

  data.forEach((item) => {
    const weekKey = getMonday(item.date);
    if (!groups[weekKey]) {
      groups[weekKey] = {
        date: weekKey,
        total_rating_sum: 0,
        total_reviews: 0,
      };
    }
    const count = item.review_count || 0;
    const rating = item.avg_rating || 0;
    groups[weekKey].total_rating_sum += rating * count;
    groups[weekKey].total_reviews += count;
  });

  const chartData = Object.values(groups).map((g) => {
    const avg_rating = g.total_reviews > 0 ? parseFloat((g.total_rating_sum / g.total_reviews).toFixed(2)) : 0;
    
    // Format display date: "W/o DD MMM"
    const [year, month, day] = g.date.split("-").map(Number);
    const localDate = new Date(year, month - 1, day);
    const displayDate = "W/o " + localDate.toLocaleDateString("en-IN", {
      day: "numeric",
      month: "short",
    });

    return {
      date: g.date,
      avg_rating,
      review_count: g.total_reviews,
      displayDate,
    };
  });

  // Sort chronologically
  chartData.sort((a, b) => a.date.localeCompare(b.date));

  if (chartData.length === 0) {
    return (
      <div className="flex h-64 items-center justify-center rounded-2xl border border-gray-800 bg-[#151B2C]/20 text-gray-500">
        No daily rollup historical logs found for the selected date range.
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Chart 1: Weekly Rating Trend */}
      <div className="rounded-2xl border border-gray-800 bg-[#151B2C]/30 p-6">
        <h4 className="mb-6 text-lg font-bold text-gray-300">Weekly Rating Trend</h4>
        <div className="h-64 w-full">
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
    </div>
  );
}
