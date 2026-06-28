// src/types/index.ts
// Shared TypeScript interfaces across the app

export interface Message {
  id: string;
  role: "user" | "assistant" | "system";
  content: string;
  timestamp: Date;
  intent?: string;
  confidence?: number;
  isTyping?: boolean;
}

export interface Conversation {
  id: string;
  customer_name: string;
  customer_email?: string;
  status: "open" | "in_progress" | "escalated" | "resolved";
  channel: "web" | "whatsapp" | "voice";
  intent?: string;
  language: string;
  created_at: string;
  updated_at: string;
  csat_score?: number;
  last_message?: string;
}

export interface MessageResponse {
  conversation_id: string;
  response: string;
  intent: string | null;
  confidence: number;
  language: string;
  latency_ms: number;
  model_used: string;
  should_escalate: boolean;
  suggested_replies: string[];
}

export interface DailyMetric {
  date: string;
  total_conversations: number;
  resolved_conversations: number;
  escalated_conversations: number;
  total_messages: number;
  avg_resolution_time_sec: number;
  avg_csat_score: number;
  intent_breakdown: Record<string, number>;
}

export interface Tenant {
  id: string;
  name: string;
  plan: string;
  api_key: string;
}

export interface CopilotSuggestion {
  text: string;
  confidence: number;
}