// src/components/analytics/AnalyticsPage.tsx
import { useState, useEffect } from "react";
import {
  BarChart, Bar, LineChart, Line, PieChart, Pie, Cell,
  XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer,
} from "recharts";
import { TrendingUp, MessageSquare, Clock, AlertTriangle } from "lucide-react";
import { getDailyMetrics } from "../../services/api";
import { DailyMetric } from "../../types";

const INTENT_COLORS = ["#3b82f6", "#10b981", "#f59e0b", "#ef4444", "#8b5cf6"];
const INTENTS = ["order_status", "refund_request", "technical_issue", "billing", "general_faq"];

function KpiCard({
  title, value, subtitle, icon: Icon, color,
}: {
  title: string; value: string; subtitle: string;
  icon: any; color: string;
}) {
  return (
    <div className="bg-white rounded-xl border border-gray-200 p-5 shadow-sm">
      <div className="flex items-center justify-between mb-3">
        <span className="text-sm text-gray-500 font-medium">{title}</span>
        <div className={`w-9 h-9 rounded-lg flex items-center justify-center ${color}`}>
          <Icon size={18} className="text-white" />
        </div>
      </div>
      <p className="text-2xl font-bold text-gray-900">{value}</p>
      <p className="text-xs text-gray-400 mt-1">{subtitle}</p>
    </div>
  );
}

export default function AnalyticsPage() {
  const [metrics, setMetrics] = useState<DailyMetric[]>([]);
  const [loading, setLoading] = useState(true);
  const [days, setDays] = useState(7);

  useEffect(() => {
    getDailyMetrics(days)
      .then(setMetrics)
      .finally(() => setLoading(false));
  }, [days]);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-screen bg-gray-50">
        <div className="text-center">
          <div className="w-10 h-10 border-4 border-blue-600 border-t-transparent rounded-full animate-spin mx-auto mb-3" />
          <p className="text-gray-500 text-sm">Loading analytics...</p>
        </div>
      </div>
    );
  }

  const totals = metrics.reduce(
    (acc, m) => ({
      conversations: acc.conversations + m.total_conversations,
      resolved: acc.resolved + m.resolved_conversations,
      escalated: acc.escalated + m.escalated_conversations,
      avgCsat: acc.avgCsat + m.avg_csat_score / metrics.length,
      avgResTime: acc.avgResTime + m.avg_resolution_time_sec / metrics.length,
    }),
    { conversations: 0, resolved: 0, escalated: 0, avgCsat: 0, avgResTime: 0 }
  );

  const intentData = INTENTS.map((intent) => ({
    name: intent.replace("_", " "),
    value: metrics.reduce((sum, m) => sum + (m.intent_breakdown[intent] || 0), 0),
  }));

  const fmtTime = (sec: number) =>
    sec < 60 ? `${Math.round(sec)}s` : `${Math.round(sec / 60)}m`;

  return (
    <div className="h-screen overflow-y-auto bg-gray-50 p-6">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-xl font-bold text-gray-900">Analytics</h1>
          <p className="text-sm text-gray-500 mt-0.5">SupportSphere Platform Metrics</p>
        </div>
        <div className="flex gap-2">
          {[7, 14, 30].map((d) => (
            <button
              key={d}
              onClick={() => setDays(d)}
              className={`text-xs px-3 py-1.5 rounded-lg font-medium transition-colors ${
                days === d
                  ? "bg-blue-600 text-white"
                  : "bg-white border border-gray-200 text-gray-600 hover:bg-gray-50"
              }`}
            >
              {d}d
            </button>
          ))}
        </div>
      </div>

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
        <KpiCard title="Total Conversations" value={totals.conversations.toLocaleString()} subtitle={`Last ${days} days`} icon={MessageSquare} color="bg-blue-500" />
        <KpiCard title="Resolution Rate" value={`${Math.round((totals.resolved / totals.conversations) * 100)}%`} subtitle={`${totals.resolved} resolved`} icon={TrendingUp} color="bg-green-500" />
        <KpiCard title="Avg Resolution Time" value={fmtTime(totals.avgResTime)} subtitle="Per conversation" icon={Clock} color="bg-yellow-500" />
        <KpiCard title="Escalation Rate" value={`${Math.round((totals.escalated / totals.conversations) * 100)}%`} subtitle={`${totals.escalated} escalated`} icon={AlertTriangle} color="bg-red-500" />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 mb-4">
        <div className="bg-white rounded-xl border border-gray-200 p-5 shadow-sm">
          <h3 className="text-sm font-semibold text-gray-800 mb-4">Daily Conversation Volume</h3>
          <ResponsiveContainer width="100%" height={220}>
            <BarChart data={metrics} margin={{ top: 0, right: 0, left: -20, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
              <XAxis dataKey="date" tick={{ fontSize: 11, fill: "#9ca3af" }} tickFormatter={(d) => d.slice(5)} />
              <YAxis tick={{ fontSize: 11, fill: "#9ca3af" }} />
              <Tooltip contentStyle={{ fontSize: 12, borderRadius: 8, border: "1px solid #e5e7eb" }} formatter={(v: any) => [v, ""]} />
              <Legend iconSize={10} wrapperStyle={{ fontSize: 11 }} />
              <Bar dataKey="total_conversations" name="Total" fill="#3b82f6" radius={[4, 4, 0, 0]} />
              <Bar dataKey="resolved_conversations" name="Resolved" fill="#10b981" radius={[4, 4, 0, 0]} />
              <Bar dataKey="escalated_conversations" name="Escalated" fill="#ef4444" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>

        <div className="bg-white rounded-xl border border-gray-200 p-5 shadow-sm">
          <h3 className="text-sm font-semibold text-gray-800 mb-4">CSAT Score Trend</h3>
          <ResponsiveContainer width="100%" height={220}>
            <LineChart data={metrics} margin={{ top: 0, right: 0, left: -20, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
              <XAxis dataKey="date" tick={{ fontSize: 11, fill: "#9ca3af" }} tickFormatter={(d) => d.slice(5)} />
              <YAxis domain={[1, 5]} tick={{ fontSize: 11, fill: "#9ca3af" }} />
              <Tooltip contentStyle={{ fontSize: 12, borderRadius: 8, border: "1px solid #e5e7eb" }} formatter={(v: any) => [`${Number(v).toFixed(1)} / 5`, "CSAT"]} />
              <Line type="monotone" dataKey="avg_csat_score" stroke="#f59e0b" strokeWidth={2.5} dot={{ fill: "#f59e0b", r: 3 }} activeDot={{ r: 5 }} name="CSAT" />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <div className="bg-white rounded-xl border border-gray-200 p-5 shadow-sm">
          <h3 className="text-sm font-semibold text-gray-800 mb-4">Intent Distribution</h3>
          <div className="flex items-center gap-4">
            <ResponsiveContainer width="55%" height={200}>
              <PieChart>
                <Pie data={intentData} cx="50%" cy="50%" innerRadius={50} outerRadius={80} dataKey="value" paddingAngle={2}>
                  {intentData.map((_, i) => (
                    <Cell key={i} fill={INTENT_COLORS[i % INTENT_COLORS.length]} />
                  ))}
                </Pie>
                <Tooltip contentStyle={{ fontSize: 12, borderRadius: 8 }} formatter={(v: any) => [v, "tickets"]} />
              </PieChart>
            </ResponsiveContainer>
            <div className="flex flex-col gap-2">
              {intentData.map((d, i) => (
                <div key={i} className="flex items-center gap-2">
                  <span className="w-3 h-3 rounded-full flex-shrink-0" style={{ backgroundColor: INTENT_COLORS[i] }} />
                  <span className="text-xs text-gray-600 capitalize">{d.name}</span>
                  <span className="text-xs font-semibold text-gray-900 ml-auto">{d.value}</span>
                </div>
              ))}
            </div>
          </div>
        </div>

        <div className="bg-white rounded-xl border border-gray-200 p-5 shadow-sm">
          <h3 className="text-sm font-semibold text-gray-800 mb-4">Avg Resolution Time (seconds)</h3>
          <ResponsiveContainer width="100%" height={200}>
            <BarChart data={metrics} layout="vertical" margin={{ top: 0, right: 20, left: 10, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
              <XAxis type="number" tick={{ fontSize: 11, fill: "#9ca3af" }} />
              <YAxis type="category" dataKey="date" tick={{ fontSize: 10, fill: "#9ca3af" }} tickFormatter={(d) => d.slice(5)} width={40} />
              <Tooltip contentStyle={{ fontSize: 12, borderRadius: 8 }} formatter={(v: any) => [`${Math.round(v)}s`, "Avg time"]} />
              <Bar dataKey="avg_resolution_time_sec" fill="#8b5cf6" radius={[0, 4, 4, 0]} name="Resolution time" />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>
    </div>
  );
}