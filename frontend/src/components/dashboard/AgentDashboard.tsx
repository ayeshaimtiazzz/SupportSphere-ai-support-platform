// src/components/dashboard/AgentDashboard.tsx
import { useState, useEffect } from "react";
import {
  MessageSquare, Clock, AlertTriangle, CheckCircle,
  ChevronRight, Zap, User, Globe, Phone,
} from "lucide-react";
import { Conversation } from "../../types";
import { sendMessage } from "../../services/api";

// ── Mock conversations for the ticket queue ─────────────────
const MOCK_CONVERSATIONS: Conversation[] = [
  {
    id: "conv-001", customer_name: "Ahmed Khan",
    customer_email: "ahmed@example.com", status: "open",
    channel: "web", intent: "order_status", language: "en",
    created_at: new Date(Date.now() - 5 * 60000).toISOString(),
    updated_at: new Date().toISOString(),
    last_message: "Where is my order ORD-12345?",
  },
  {
    id: "conv-002", customer_name: "Sara Ahmed",
    customer_email: "sara@example.com", status: "escalated",
    channel: "whatsapp", intent: "refund_request", language: "en",
    created_at: new Date(Date.now() - 15 * 60000).toISOString(),
    updated_at: new Date().toISOString(),
    last_message: "I want a refund for my damaged item",
  },
  {
    id: "conv-003", customer_name: "Ali Hassan",
    status: "in_progress", channel: "voice",
    intent: "technical_issue", language: "en",
    created_at: new Date(Date.now() - 2 * 60000).toISOString(),
    updated_at: new Date().toISOString(),
    last_message: "The app keeps crashing on login",
  },
  {
    id: "conv-004", customer_name: "Fatima Malik",
    status: "open", channel: "web",
    intent: "billing", language: "ur",
    created_at: new Date(Date.now() - 30 * 60000).toISOString(),
    updated_at: new Date().toISOString(),
    last_message: "میرا بل غلط ہے",
  },
];

// ── Status badge ────────────────────────────────────────────
function StatusBadge({ status }: { status: string }) {
  const styles: Record<string, string> = {
    open:        "bg-blue-100 text-blue-700",
    in_progress: "bg-yellow-100 text-yellow-700",
    escalated:   "bg-red-100 text-red-700",
    resolved:    "bg-green-100 text-green-700",
  };
  return (
    <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${styles[status] || "bg-gray-100 text-gray-600"}`}>
      {status.replace("_", " ")}
    </span>
  );
}

// ── Channel icon ────────────────────────────────────────────
function ChannelIcon({ channel }: { channel: string }) {
  if (channel === "whatsapp") return <Phone size={12} className="text-green-500" />;
  if (channel === "voice")    return <Globe size={12} className="text-purple-500" />;
  return <Globe size={12} className="text-blue-500" />;
}

// ── Time ago ────────────────────────────────────────────────
function timeAgo(dateStr: string): string {
  const diff = Math.floor((Date.now() - new Date(dateStr).getTime()) / 1000);
  if (diff < 60) return `${diff}s ago`;
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
  return `${Math.floor(diff / 3600)}h ago`;
}

// ── Co-pilot panel ──────────────────────────────────────────
function CopilotPanel({ conversation }: { conversation: Conversation | null }) {
  const [suggestions, setSuggestions] = useState<string[]>([]);
  const [loading, setLoading] = useState(false);
  const [copied, setCopied] = useState<number | null>(null);

  useEffect(() => {
    if (!conversation) return;
    setLoading(true);
    setSuggestions([]);

    // Generate suggestions by calling the agent with copilot mode
    sendMessage(conversation.last_message || "Help needed", conversation.id)
      .then((result) => {
        if (result.suggested_replies?.length) {
          setSuggestions(result.suggested_replies);
        } else {
          // Fallback suggestions based on intent
          setSuggestions([
            "Thank you for contacting us. I'm looking into this right now and will get back to you shortly.",
            "I understand your concern. Let me check the details and provide you with an update immediately.",
            "I apologize for any inconvenience. I'll resolve this for you right away.",
          ]);
        }
      })
      .catch(() => {
        setSuggestions([
          "Thank you for reaching out. I'm here to help.",
          "I'll look into this immediately and get back to you.",
          "I apologize for any trouble. Let me resolve this for you.",
        ]);
      })
      .finally(() => setLoading(false));
  }, [conversation?.id]);

  const copyToClipboard = (text: string, idx: number) => {
    navigator.clipboard.writeText(text);
    setCopied(idx);
    setTimeout(() => setCopied(null), 2000);
  };

  if (!conversation) {
    return (
      <div className="flex flex-col items-center justify-center h-full text-gray-400 p-6 text-center">
        <Zap size={32} className="mb-3 opacity-40" />
        <p className="text-sm font-medium">AI Co-pilot</p>
        <p className="text-xs mt-1">Select a conversation to see suggested replies</p>
      </div>
    );
  }

  return (
    <div className="p-4 flex flex-col h-full">
      <div className="flex items-center gap-2 mb-4">
        <Zap size={16} className="text-yellow-500" />
        <span className="text-sm font-semibold text-gray-800">AI Suggested Replies</span>
      </div>

      <div className="bg-blue-50 rounded-lg p-3 mb-4 text-xs text-blue-700">
        <span className="font-medium">Customer:</span> {conversation.last_message}
      </div>

      {loading ? (
        <div className="flex flex-col gap-3">
          {[1, 2, 3].map((i) => (
            <div key={i} className="h-20 bg-gray-100 rounded-lg animate-pulse" />
          ))}
        </div>
      ) : (
        <div className="flex flex-col gap-3 overflow-y-auto">
          {suggestions.map((s, i) => (
            <div key={i} className="bg-white border border-gray-200 rounded-lg p-3 hover:border-blue-300 transition-colors">
              <p className="text-xs text-gray-700 leading-relaxed mb-2">{s}</p>
              <button
                onClick={() => copyToClipboard(s, i)}
                className={`text-xs px-3 py-1 rounded-md transition-colors font-medium ${
                  copied === i
                    ? "bg-green-100 text-green-700"
                    : "bg-blue-50 text-blue-600 hover:bg-blue-100"
                }`}
              >
                {copied === i ? "✓ Copied!" : "Use this reply"}
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// ── Main dashboard ──────────────────────────────────────────
export default function AgentDashboard() {
  const [selected, setSelected] = useState<Conversation | null>(null);
  const [filter, setFilter] = useState<string>("all");

  const filtered = MOCK_CONVERSATIONS.filter(
    (c) => filter === "all" || c.status === filter
  );

  const stats = {
    open:     MOCK_CONVERSATIONS.filter((c) => c.status === "open").length,
    escalated: MOCK_CONVERSATIONS.filter((c) => c.status === "escalated").length,
    resolved: MOCK_CONVERSATIONS.filter((c) => c.status === "resolved").length,
  };

  return (
    <div className="flex h-screen bg-gray-50">
      {/* LEFT: Ticket queue */}
      <div className="w-80 bg-white border-r border-gray-200 flex flex-col">
        {/* Header */}
        <div className="px-4 py-4 border-b border-gray-100">
          <h2 className="font-semibold text-gray-900">Agent Dashboard</h2>
          <p className="text-xs text-gray-500 mt-0.5">SupportSphere AI Platform</p>
        </div>

        {/* Stats row */}
        <div className="grid grid-cols-3 gap-2 p-3 border-b border-gray-100">
          <div className="text-center">
            <p className="text-lg font-bold text-blue-600">{stats.open}</p>
            <p className="text-xs text-gray-500">Open</p>
          </div>
          <div className="text-center">
            <p className="text-lg font-bold text-red-500">{stats.escalated}</p>
            <p className="text-xs text-gray-500">Escalated</p>
          </div>
          <div className="text-center">
            <p className="text-lg font-bold text-green-600">{stats.resolved}</p>
            <p className="text-xs text-gray-500">Resolved</p>
          </div>
        </div>

        {/* Filter tabs */}
        <div className="flex gap-1 p-2 border-b border-gray-100">
          {["all", "open", "escalated", "resolved"].map((f) => (
            <button
              key={f}
              onClick={() => setFilter(f)}
              className={`flex-1 text-xs py-1.5 rounded-md font-medium transition-colors ${
                filter === f
                  ? "bg-blue-600 text-white"
                  : "text-gray-500 hover:bg-gray-100"
              }`}
            >
              {f.charAt(0).toUpperCase() + f.slice(1)}
            </button>
          ))}
        </div>

        {/* Ticket list */}
        <div className="flex-1 overflow-y-auto">
          {filtered.map((conv) => (
            <button
              key={conv.id}
              onClick={() => setSelected(conv)}
              className={`w-full text-left px-4 py-3 border-b border-gray-50 hover:bg-gray-50 transition-colors ${
                selected?.id === conv.id ? "bg-blue-50 border-l-2 border-l-blue-600" : ""
              }`}
            >
              <div className="flex items-start justify-between mb-1">
                <div className="flex items-center gap-1.5">
                  <User size={12} className="text-gray-400" />
                  <span className="text-xs font-semibold text-gray-800">
                    {conv.customer_name}
                  </span>
                  <ChannelIcon channel={conv.channel} />
                </div>
                <span className="text-xs text-gray-400">{timeAgo(conv.created_at)}</span>
              </div>
              <p className="text-xs text-gray-500 truncate mb-2">{conv.last_message}</p>
              <div className="flex items-center justify-between">
                <StatusBadge status={conv.status} />
                {conv.intent && (
                  <span className="text-xs text-gray-400">{conv.intent.replace("_", " ")}</span>
                )}
              </div>
            </button>
          ))}
        </div>
      </div>

      {/* CENTER: Conversation view */}
      <div className="flex-1 flex flex-col">
        {selected ? (
          <>
            <div className="bg-white border-b border-gray-200 px-6 py-4 flex items-center justify-between">
              <div>
                <h3 className="font-semibold text-gray-900">{selected.customer_name}</h3>
                <div className="flex items-center gap-3 mt-0.5">
                  <StatusBadge status={selected.status} />
                  <span className="text-xs text-gray-500">
                    {selected.channel} · {selected.language.toUpperCase()}
                  </span>
                </div>
              </div>
              <div className="flex gap-2">
                <button className="text-xs px-3 py-1.5 bg-green-50 text-green-700 border border-green-200 rounded-lg hover:bg-green-100 transition-colors font-medium">
                  <CheckCircle size={12} className="inline mr-1" />
                  Resolve
                </button>
                <button className="text-xs px-3 py-1.5 bg-red-50 text-red-700 border border-red-200 rounded-lg hover:bg-red-100 transition-colors font-medium">
                  <AlertTriangle size={12} className="inline mr-1" />
                  Escalate
                </button>
              </div>
            </div>

            <div className="flex-1 flex items-center justify-center text-gray-400">
              <div className="text-center">
                <MessageSquare size={40} className="mx-auto mb-3 opacity-30" />
                <p className="text-sm">Conversation history loads from DB</p>
                <p className="text-xs mt-1 text-gray-300">
                  Start Docker + connect PostgreSQL to see messages
                </p>
                <div className="mt-4 p-3 bg-gray-50 rounded-lg text-xs text-left text-gray-500 max-w-xs">
                  <p className="font-medium text-gray-700 mb-1">Latest message:</p>
                  <p>"{selected.last_message}"</p>
                </div>
              </div>
            </div>
          </>
        ) : (
          <div className="flex-1 flex items-center justify-center text-gray-400">
            <div className="text-center">
              <MessageSquare size={40} className="mx-auto mb-3 opacity-30" />
              <p className="text-sm">Select a conversation from the queue</p>
            </div>
          </div>
        )}
      </div>

      {/* RIGHT: AI Co-pilot */}
      <div className="w-72 bg-white border-l border-gray-200 flex flex-col">
        <div className="px-4 py-4 border-b border-gray-100">
          <div className="flex items-center gap-2">
            <Zap size={16} className="text-yellow-500" />
            <span className="font-semibold text-sm text-gray-900">AI Co-pilot</span>
          </div>
        </div>
        <div className="flex-1 overflow-hidden">
          <CopilotPanel conversation={selected} />
        </div>
      </div>
    </div>
  );
}