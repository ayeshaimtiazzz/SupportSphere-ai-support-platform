// src/services/api.ts
import axios from "axios";
import { MessageResponse } from "../types";

const API_KEY = "acme_test_key_abc123";

const api = axios.create({
  baseURL: "/api/v1",
  headers: { "X-API-Key": API_KEY, "Content-Type": "application/json" },
});

// ── Conversations ───────────────────────────────────────────
export async function sendMessage(
  message: string,
  conversationId?: string,
  channel: string = "web"
): Promise<MessageResponse> {
  const { data } = await api.post("/conversations/", {
    message,
    conversation_id: conversationId || null,
    channel,
  });
  return data;
}

export async function getHistory(conversationId: string) {
  const { data } = await api.get(`/conversations/${conversationId}/history`);
  return data.messages;
}

// ── Analytics ───────────────────────────────────────────────
export async function getDailyMetrics(days: number = 7) {
  // In production this hits the DB; for now return mock data
  // so the analytics page works before the Kafka consumer is wired
  const mockData = Array.from({ length: days }, (_, i) => {
    const date = new Date();
    date.setDate(date.getDate() - (days - 1 - i));
    return {
      date: date.toISOString().split("T")[0],
      total_conversations: Math.floor(Math.random() * 80 + 20),
      resolved_conversations: Math.floor(Math.random() * 60 + 15),
      escalated_conversations: Math.floor(Math.random() * 10 + 2),
      total_messages: Math.floor(Math.random() * 300 + 100),
      avg_resolution_time_sec: Math.floor(Math.random() * 180 + 60),
      avg_csat_score: +(Math.random() * 1.5 + 3.5).toFixed(1),
      intent_breakdown: {
        order_status: Math.floor(Math.random() * 30 + 10),
        refund_request: Math.floor(Math.random() * 20 + 5),
        technical_issue: Math.floor(Math.random() * 15 + 3),
        billing: Math.floor(Math.random() * 10 + 2),
        general_faq: Math.floor(Math.random() * 25 + 8),
      },
    };
  });
  return mockData;
}

// ── Health ──────────────────────────────────────────────────
export async function getHealth() {
  const { data } = await api.get("/health");
  return data;
}