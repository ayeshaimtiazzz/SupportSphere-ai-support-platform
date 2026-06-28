// src/components/docs/HowToPage.tsx
import { MessageCircle, LayoutDashboard, BarChart2, Mic, Phone, Zap, Database, Activity, ChevronRight } from "lucide-react";

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="mb-8">
      <h2 className="text-base font-bold text-gray-900 mb-4 pb-2 border-b border-gray-100">{title}</h2>
      {children}
    </div>
  );
}

function Step({ n, title, desc }: { n: number; title: string; desc: string }) {
  return (
    <div className="flex gap-4 mb-4">
      <div className="w-7 h-7 rounded-full bg-blue-600 text-white text-xs font-bold flex items-center justify-center flex-shrink-0 mt-0.5">
        {n}
      </div>
      <div>
        <p className="text-sm font-semibold text-gray-800">{title}</p>
        <p className="text-sm text-gray-500 mt-0.5 leading-relaxed">{desc}</p>
      </div>
    </div>
  );
}

function FeatureCard({ icon: Icon, title, desc, color }: { icon: any; title: string; desc: string; color: string }) {
  return (
    <div className="bg-white border border-gray-200 rounded-xl p-4 shadow-sm">
      <div className={`w-9 h-9 rounded-lg flex items-center justify-center mb-3 ${color}`}>
        <Icon size={18} className="text-white" />
      </div>
      <p className="text-sm font-semibold text-gray-800 mb-1">{title}</p>
      <p className="text-xs text-gray-500 leading-relaxed">{desc}</p>
    </div>
  );
}

function TechBadge({ name, desc }: { name: string; desc: string }) {
  return (
    <div className="flex items-start gap-3 py-2.5 border-b border-gray-50 last:border-0">
      <span className="text-xs font-mono bg-gray-100 text-gray-700 px-2 py-0.5 rounded flex-shrink-0 mt-0.5">{name}</span>
      <span className="text-xs text-gray-500">{desc}</span>
    </div>
  );
}

export default function HowToPage() {
  return (
    <div className="h-screen overflow-y-auto bg-gray-50">
      <div className="max-w-3xl mx-auto p-6">

        {/* Hero */}
        <div className="bg-gradient-to-br from-blue-600 to-indigo-700 rounded-2xl p-6 mb-8 text-white">
          <div className="flex items-center gap-3 mb-3">
            <div className="w-10 h-10 rounded-xl bg-white/20 flex items-center justify-center">
              <Activity size={22} className="text-white" />
            </div>
            <div>
              <h1 className="text-xl font-bold">SupportSphere</h1>
              <p className="text-blue-200 text-xs">Production-Grade AI Customer Support Platform</p>
            </div>
          </div>
          <p className="text-blue-100 text-sm leading-relaxed">
            A multi-tenant AI customer support system with voice input, WhatsApp integration,
            a fine-tuned LLM, real-time analytics, and an agent co-pilot dashboard.
            Built with LangGraph, FastAPI, React, Kafka, and PostgreSQL.
          </p>
        </div>

        {/* Navigation guide */}
        <Section title="How to Navigate">
          <div className="grid grid-cols-1 gap-3">
            {[
              {
                icon: MessageCircle, color: "bg-blue-500",
                title: "Chat Demo (this page's left icon)",
                desc: "Try the AI support agent. Type a message or use the microphone button for voice input. The agent classifies your intent, searches the knowledge base, and calls tools to answer.",
              },
              {
                icon: LayoutDashboard, color: "bg-purple-500",
                title: "Agent Dashboard (middle icon)",
                desc: "View the ticket queue. Click any conversation to open it. The right panel shows AI-generated reply suggestions — click 'Use this reply' to copy them.",
              },
              {
                icon: BarChart2, color: "bg-green-500",
                title: "Analytics (third icon)",
                desc: "Platform metrics: daily conversation volume, CSAT trends, intent distribution, and resolution times. Toggle between 7, 14, and 30 day views.",
              },
            ].map((item) => (
              <div key={item.title} className="flex items-start gap-4 bg-white border border-gray-200 rounded-xl p-4 shadow-sm">
                <div className={`w-9 h-9 rounded-lg flex items-center justify-center flex-shrink-0 ${item.color}`}>
                  <item.icon size={18} className="text-white" />
                </div>
                <div>
                  <p className="text-sm font-semibold text-gray-800">{item.title}</p>
                  <p className="text-xs text-gray-500 mt-1 leading-relaxed">{item.desc}</p>
                </div>
              </div>
            ))}
          </div>
        </Section>

        {/* How the chat works */}
        <Section title="How the Chat Agent Works">
          <div className="bg-white border border-gray-200 rounded-xl p-5 shadow-sm">
            <Step n={1} title="You send a message" desc="Type in the chat widget or click the mic button to record a voice message. Voice is transcribed by Groq's Whisper model." />
            <Step n={2} title="Language detection" desc="The agent detects if you're writing in English or Urdu and adjusts its response language accordingly." />
            <Step n={3} title="Intent classification" desc="Groq Llama 3.3-70B classifies your message into: order_status, refund_request, technical_issue, billing, general_faq, or unknown." />
            <Step n={4} title="RAG retrieval" desc="Your query is embedded using sentence-transformers and searched against the tenant's knowledge base in PostgreSQL (pgvector)." />
            <Step n={5} title="Tool call (if needed)" desc="For order/billing/refund intents, the agent calls the appropriate tool to look up real data from your systems." />
            <Step n={6} title="Response generation" desc="The LLM generates a response using the system prompt, retrieved documents, and tool results. Response is returned in under 3 seconds." />
          </div>
        </Section>

        {/* Features */}
        <Section title="Key Features">
          <div className="grid grid-cols-2 gap-3">
            <FeatureCard icon={Mic} color="bg-blue-500" title="Voice Input"
              desc="Click the mic in the chat widget, speak, and your words are transcribed by Groq Whisper and sent to the agent." />
            <FeatureCard icon={Phone} color="bg-green-500" title="WhatsApp"
              desc="Send a WhatsApp message to the Twilio sandbox number and get an AI reply — same agent, different channel." />
            <FeatureCard icon={Zap} color="bg-yellow-500" title="AI Co-pilot"
              desc="Human agents see 3 AI-suggested replies when they open a ticket. Click to copy and send." />
            <FeatureCard icon={Database} color="bg-purple-500" title="Multi-tenant"
              desc="Each company has its own isolated knowledge base, conversation history, and custom AI persona." />
            <FeatureCard icon={BarChart2} color="bg-red-500" title="Real-time Analytics"
              desc="Kafka streams every event. A consumer aggregates them into daily metrics shown in the analytics page." />
            <FeatureCard icon={Activity} color="bg-indigo-500" title="Fine-tuned LLM"
              desc="Mistral-7B fine-tuned on 26k customer support examples using QLoRA — uploaded to HuggingFace Hub." />
          </div>
        </Section>

        {/* Try these */}
        <Section title="Try These in the Chat">
          <div className="bg-white border border-gray-200 rounded-xl overflow-hidden shadow-sm">
            {[
              { msg: "Where is my order ORD-12345?", intent: "order_status", note: "Triggers tool call + order lookup" },
              { msg: "I want a refund for my last purchase", intent: "refund_request", note: "Triggers refund processor tool" },
              { msg: "The app keeps crashing when I log in", intent: "technical_issue", note: "RAG search in knowledge base" },
              { msg: "What payment methods do you accept?", intent: "general_faq", note: "Knowledge base retrieval" },
              { msg: "میرا آرڈر کہاں ہے؟", intent: "Urdu", note: "Urdu language detection + response" },
              { msg: "xyzxyz gibberish message", intent: "unknown", note: "Low confidence → escalation after 3 tries" },
            ].map((item, i) => (
              <div key={i} className="flex items-center gap-4 px-4 py-3 border-b border-gray-50 last:border-0 hover:bg-gray-50 transition-colors">
                <ChevronRight size={14} className="text-blue-400 flex-shrink-0" />
                <div className="flex-1">
                  <p className="text-sm text-gray-800 font-medium">"{item.msg}"</p>
                  <p className="text-xs text-gray-400 mt-0.5">{item.note}</p>
                </div>
                <span className="text-xs bg-blue-50 text-blue-600 px-2 py-0.5 rounded-full font-medium flex-shrink-0">
                  {item.intent}
                </span>
              </div>
            ))}
          </div>
        </Section>

        {/* Tech stack */}
        <Section title="Tech Stack">
          <div className="bg-white border border-gray-200 rounded-xl p-4 shadow-sm">
            <TechBadge name="LangGraph" desc="8-node stateful agent graph: intake → language_detect → classify → rag_lookup → tool_call → resolve/escalate" />
            <TechBadge name="Groq" desc="Llama 3.3-70B for intent classification + response generation. Whisper-large-v3 for voice transcription." />
            <TechBadge name="Mistral-7B" desc="Fine-tuned on 26k Bitext customer support examples using QLoRA (rank=16) on Google Colab T4." />
            <TechBadge name="pgvector" desc="PostgreSQL extension for vector similarity search. Stores knowledge base embeddings (384-dim sentence-transformers)." />
            <TechBadge name="Kafka" desc="Event streaming for every conversation action. Analytics consumer aggregates into daily_metrics table." />
            <TechBadge name="Redis" desc="Sliding window rate limiting per tenant API key. Session caching." />
            <TechBadge name="FastAPI" desc="Async REST API + WebSocket endpoints. Prometheus metrics at /metrics." />
            <TechBadge name="Twilio" desc="WhatsApp webhook integration — any WhatsApp message becomes a support ticket." />
            <TechBadge name="React + TS" desc="Chat widget, agent dashboard, analytics charts (Recharts), and this docs page." />
            <TechBadge name="Docker Compose" desc="Orchestrates PostgreSQL, Redis, Kafka, Zookeeper, Prometheus, and Grafana." />
          </div>
        </Section>

        {/* Architecture note */}
        <Section title="Architecture Overview">
          <div className="bg-white border border-gray-200 rounded-xl p-4 shadow-sm text-xs font-mono text-gray-600 leading-loose">
            <p className="text-gray-400 mb-2"># Request flow</p>
            <p>Customer (Web/WhatsApp/Voice)</p>
            <p className="pl-4 text-blue-500">↓ HTTP/WebSocket/Twilio webhook</p>
            <p>FastAPI Backend (port 8000)</p>
            <p className="pl-4 text-blue-500">↓ API key auth + rate limiting (Redis)</p>
            <p>LangGraph Agent (8 nodes)</p>
            <p className="pl-4 text-blue-500">↓ publishes events</p>
            <p>Kafka (conversation_events topic)</p>
            <p className="pl-4 text-blue-500">↓ consumed by</p>
            <p>Analytics Consumer → PostgreSQL daily_metrics</p>
            <p className="pl-4 text-blue-500">↓ queried by</p>
            <p>React Analytics Page (Recharts)</p>
          </div>
        </Section>

        <div className="text-center text-xs text-gray-400 pb-6">
          Built by Ayesha Imtiaz · github.com/ayeshaimtiazzz · SupportSphere v1.0
        </div>
      </div>
    </div>
  );
}