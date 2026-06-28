// src/hooks/useChat.ts
import { useState, useCallback, useRef } from "react";
import { Message, MessageResponse } from "../types";
import { sendMessage } from "../services/api";

export function useChat() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [conversationId, setConversationId] = useState<string | undefined>();
  const [lastIntent, setLastIntent] = useState<string | null>(null);
  const [suggestedReplies, setSuggestedReplies] = useState<string[]>([]);

  const addMessage = useCallback((msg: Omit<Message, "id" | "timestamp">) => {
    const newMsg: Message = {
      ...msg,
      id: crypto.randomUUID(),
      timestamp: new Date(),
    };
    setMessages((prev) => [...prev, newMsg]);
    return newMsg;
  }, []);

  const send = useCallback(
    async (text: string) => {
      if (!text.trim() || isLoading) return;

      // Add user message immediately
      addMessage({ role: "user", content: text });

      // Add typing indicator
      const typingId = crypto.randomUUID();
      setMessages((prev) => [
        ...prev,
        {
          id: typingId,
          role: "assistant",
          content: "",
          timestamp: new Date(),
          isTyping: true,
        },
      ]);
      setIsLoading(true);

      try {
        const result: MessageResponse = await sendMessage(
          text,
          conversationId,
          "web"
        );

        // Update conversation ID for continuity
        if (!conversationId) setConversationId(result.conversation_id);
        setLastIntent(result.intent);
        setSuggestedReplies(result.suggested_replies || []);

        // Replace typing indicator with actual response
        setMessages((prev) =>
          prev.map((m) =>
            m.id === typingId
              ? {
                  ...m,
                  content: result.response,
                  isTyping: false,
                  intent: result.intent || undefined,
                  confidence: result.confidence,
                }
              : m
          )
        );
      } catch (err) {
        setMessages((prev) =>
          prev.map((m) =>
            m.id === typingId
              ? {
                  ...m,
                  content: "Sorry, something went wrong. Please try again.",
                  isTyping: false,
                }
              : m
          )
        );
      } finally {
        setIsLoading(false);
      }
    },
    [conversationId, isLoading, addMessage]
  );

  const reset = useCallback(() => {
    setMessages([]);
    setConversationId(undefined);
    setLastIntent(null);
    setSuggestedReplies([]);
  }, []);

  return {
    messages,
    isLoading,
    conversationId,
    lastIntent,
    suggestedReplies,
    send,
    reset,
  };
}