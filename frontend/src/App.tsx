// src/App.tsx
import { BrowserRouter, Routes, Route, NavLink } from "react-router-dom";
import { MessageCircle, LayoutDashboard, BarChart2, Activity, BookOpen } from "lucide-react";
import ChatWidget from "./components/chat/ChatWidget";
import AgentDashboard from "./components/dashboard/AgentDashboard";
import AnalyticsPage from "./components/analytics/AnalyticsPage";
import HowToPage from "./components/docs/HowToPage";

function Sidebar() {
  const navItems = [
    { to: "/",          icon: MessageCircle,   label: "Chat Demo" },
    { to: "/dashboard", icon: LayoutDashboard, label: "Agent Dashboard" },
    { to: "/analytics", icon: BarChart2,       label: "Analytics" },
    { to: "/how-to",    icon: BookOpen,        label: "How it works" },
  ];

  return (
    <aside className="w-16 bg-gray-900 flex flex-col items-center py-4 gap-2 flex-shrink-0">
      <div className="w-9 h-9 rounded-xl bg-blue-600 flex items-center justify-center mb-4">
        <Activity size={18} className="text-white" />
      </div>
      {navItems.map(({ to, icon: Icon, label }) => (
        <NavLink
          key={to}
          to={to}
          end={to === "/"}
          title={label}
          className={({ isActive }) =>
            `w-10 h-10 rounded-xl flex items-center justify-center transition-colors ${
              isActive
                ? "bg-blue-600 text-white"
                : "text-gray-400 hover:bg-gray-800 hover:text-white"
            }`
          }
        >
          <Icon size={18} />
        </NavLink>
      ))}
    </aside>
  );
}

function ChatDemoPage() {
  return (
    <div className="flex-1 bg-gradient-to-br from-blue-50 to-indigo-100 flex flex-col items-center justify-center p-8 relative h-full">
      <div className="text-center max-w-md">
        <div className="w-16 h-16 rounded-2xl bg-blue-600 flex items-center justify-center mx-auto mb-4 shadow-lg">
          <Activity size={28} className="text-white" />
        </div>
        <h1 className="text-2xl font-bold text-gray-900 mb-2">SupportSphere</h1>
        <p className="text-gray-500 text-sm mb-6 leading-relaxed">
          Production-grade multi-tenant AI customer support platform with voice,
          WhatsApp, fine-tuned LLM, and real-time analytics.
        </p>
        <div className="flex flex-wrap gap-2 justify-center mb-8">
          {["LangGraph Agent","Groq Llama 3.3","Whisper STT","LoRA Fine-tuned","Kafka Streaming","pgvector RAG","WhatsApp","Multi-tenant"].map((f) => (
            <span key={f} className="text-xs bg-white border border-blue-100 text-blue-700 px-3 py-1 rounded-full shadow-sm">{f}</span>
          ))}
        </div>
        <div className="bg-white rounded-2xl p-5 shadow-sm border border-gray-100 text-left">
          <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-3">Try asking:</p>
          {["Where is my order ORD-12345?","I want a refund for my purchase","The app won't let me log in","میرا آرڈر کہاں ہے؟"].map((q) => (
            <div key={q} className="flex items-center gap-2 py-2 border-b border-gray-50 last:border-0">
              <MessageCircle size={12} className="text-blue-400 flex-shrink-0" />
              <span className="text-sm text-gray-600">{q}</span>
            </div>
          ))}
        </div>
        <p className="text-xs text-gray-400 mt-4">Click the chat button in the bottom right →</p>
      </div>
      <ChatWidget />
    </div>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <div className="flex h-screen overflow-hidden bg-gray-50">
        <Sidebar />
        <main className="flex-1 overflow-hidden flex flex-col">
          <Routes>
            <Route path="/"          element={<ChatDemoPage />} />
            <Route path="/dashboard" element={<AgentDashboard />} />
            <Route path="/analytics" element={<AnalyticsPage />} />
            <Route path="/how-to"    element={<HowToPage />} />
          </Routes>
        </main>
      </div>
    </BrowserRouter>
  );
}