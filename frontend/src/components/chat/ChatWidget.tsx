// src/components/chat/ChatWidget.tsx
import { useState, useRef, useEffect } from "react";
import { MessageCircle, X, Send, Mic, MicOff, RotateCcw } from "lucide-react";
import { useChat } from "../../hooks/useChat";
import { Message } from "../../types";

// ── Single message bubble ───────────────────────────────────
function MessageBubble({ message }: { message: Message }) {
  const isUser = message.role === "user";

  if (message.isTyping) {
    return (
      <div className="flex justify-start mb-3">
        <div className="bg-white border border-gray-200 rounded-2xl rounded-tl-sm px-4 py-3 shadow-sm">
          <div className="flex gap-1 items-center h-4">
            <span className="w-2 h-2 bg-gray-400 rounded-full animate-bounce [animation-delay:0ms]" />
            <span className="w-2 h-2 bg-gray-400 rounded-full animate-bounce [animation-delay:150ms]" />
            <span className="w-2 h-2 bg-gray-400 rounded-full animate-bounce [animation-delay:300ms]" />
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className={`flex mb-3 ${isUser ? "justify-end" : "justify-start"}`}>
      {!isUser && (
        <div className="w-7 h-7 rounded-full bg-blue-600 flex items-center justify-center text-white text-xs font-bold mr-2 flex-shrink-0 mt-1">
          AI
        </div>
      )}
      <div
        className={`max-w-[78%] px-4 py-2.5 rounded-2xl text-sm leading-relaxed shadow-sm ${
          isUser
            ? "bg-blue-600 text-white rounded-tr-sm"
            : "bg-white border border-gray-200 text-gray-800 rounded-tl-sm"
        }`}
      >
        {message.content}
        {message.intent && !isUser && (
          <span className="block mt-1 text-xs opacity-60">
            Intent: {message.intent}
            {message.confidence && ` (${Math.round(message.confidence * 100)}%)`}
          </span>
        )}
      </div>
    </div>
  );
}

// ── Main chat widget ────────────────────────────────────────
export default function ChatWidget() {
  const [isOpen, setIsOpen] = useState(false);
  const [input, setInput] = useState("");
  const [isRecording, setIsRecording] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const audioChunksRef = useRef<Blob[]>([]);

  const { messages, isLoading, suggestedReplies, send, reset } = useChat();

  // Auto-scroll to bottom on new messages
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  // Focus input when chat opens
  useEffect(() => {
    if (isOpen) setTimeout(() => inputRef.current?.focus(), 100);
  }, [isOpen]);

  const handleSend = () => {
    if (!input.trim()) return;
    send(input.trim());
    setInput("");
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  // Voice recording using MediaRecorder API
  const toggleRecording = async () => {
    if (isRecording) {
      mediaRecorderRef.current?.stop();
      setIsRecording(false);
      return;
    }

    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const mediaRecorder = new MediaRecorder(stream);
      mediaRecorderRef.current = mediaRecorder;
      audioChunksRef.current = [];

      mediaRecorder.ondataavailable = (e) => {
        if (e.data.size > 0) audioChunksRef.current.push(e.data);
      };

      mediaRecorder.onstop = async () => {
        stream.getTracks().forEach((t) => t.stop());
        const blob = new Blob(audioChunksRef.current, { type: "audio/webm" });

        // Send to transcription endpoint
        const formData = new FormData();
        formData.append("audio", blob, "recording.webm");
        formData.append("voice_response", "false");

        try {
          const res = await fetch("/api/v1/voice/transcribe", {
            method: "POST",
            headers: { "X-API-Key": "acme_test_key_abc123" },
            body: formData,
          });
          const data = await res.json();
          if (data.transcript) {
            setInput(data.transcript);
            inputRef.current?.focus();
          }
        } catch (err) {
          console.error("Transcription failed:", err);
        }
      };

      mediaRecorder.start();
      setIsRecording(true);
    } catch (err) {
      alert("Microphone access denied. Please allow microphone access.");
    }
  };

  return (
    <>
      {/* Chat window */}
      {isOpen && (
        <div className="fixed bottom-24 right-6 w-96 h-[560px] bg-gray-50 rounded-2xl shadow-2xl border border-gray-200 flex flex-col z-50 overflow-hidden">
          {/* Header */}
          <div className="bg-blue-600 px-4 py-3 flex items-center justify-between flex-shrink-0">
            <div className="flex items-center gap-3">
              <div className="w-9 h-9 rounded-full bg-white/20 flex items-center justify-center text-white font-bold text-sm">
                AI
              </div>
              <div>
                <p className="text-white font-semibold text-sm">SupportSphere</p>
                <div className="flex items-center gap-1.5">
                  <span className="w-2 h-2 rounded-full bg-green-400 animate-pulse" />
                  <span className="text-blue-100 text-xs">Online</span>
                </div>
              </div>
            </div>
            <div className="flex items-center gap-2">
              <button
                onClick={reset}
                className="text-white/70 hover:text-white transition-colors p-1"
                title="New conversation"
              >
                <RotateCcw size={16} />
              </button>
              <button
                onClick={() => setIsOpen(false)}
                className="text-white/70 hover:text-white transition-colors p-1"
              >
                <X size={18} />
              </button>
            </div>
          </div>

          {/* Messages */}
          <div className="flex-1 overflow-y-auto px-4 py-3 space-y-1">
            {messages.length === 0 && (
              <div className="text-center py-8">
                <div className="w-14 h-14 rounded-full bg-blue-100 flex items-center justify-center mx-auto mb-3">
                  <MessageCircle className="text-blue-600" size={24} />
                </div>
                <p className="text-gray-600 text-sm font-medium">
                  Hi! How can I help you today?
                </p>
                <p className="text-gray-400 text-xs mt-1">
                  Ask me about orders, refunds, or technical issues
                </p>
                {/* Quick action chips */}
                <div className="flex flex-wrap gap-2 justify-center mt-4">
                  {["Track my order", "Request refund", "Technical help"].map(
                    (q) => (
                      <button
                        key={q}
                        onClick={() => send(q)}
                        className="text-xs bg-blue-50 text-blue-600 border border-blue-200 rounded-full px-3 py-1.5 hover:bg-blue-100 transition-colors"
                      >
                        {q}
                      </button>
                    )
                  )}
                </div>
              </div>
            )}
            {messages.map((m) => (
              <MessageBubble key={m.id} message={m} />
            ))}
            <div ref={messagesEndRef} />
          </div>

          {/* Suggested replies */}
          {suggestedReplies.length > 0 && (
            <div className="px-4 pb-2 flex gap-2 overflow-x-auto flex-shrink-0">
              {suggestedReplies.map((r, i) => (
                <button
                  key={i}
                  onClick={() => send(r)}
                  className="text-xs bg-white border border-gray-200 rounded-full px-3 py-1.5 whitespace-nowrap text-gray-600 hover:border-blue-400 hover:text-blue-600 transition-colors flex-shrink-0"
                >
                  {r.length > 40 ? r.slice(0, 40) + "…" : r}
                </button>
              ))}
            </div>
          )}

          {/* Input */}
          <div className="px-3 pb-3 flex-shrink-0">
            <div className="flex items-center gap-2 bg-white border border-gray-200 rounded-xl px-3 py-2 focus-within:border-blue-400 transition-colors">
              <input
                ref={inputRef}
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder="Type a message..."
                disabled={isLoading}
                className="flex-1 text-sm outline-none bg-transparent text-gray-800 placeholder-gray-400"
              />
              <button
                onClick={toggleRecording}
                className={`p-1.5 rounded-lg transition-colors ${
                  isRecording
                    ? "bg-red-100 text-red-500"
                    : "text-gray-400 hover:text-gray-600"
                }`}
                title="Voice input"
              >
                {isRecording ? <MicOff size={16} /> : <Mic size={16} />}
              </button>
              <button
                onClick={handleSend}
                disabled={!input.trim() || isLoading}
                className="p-1.5 rounded-lg bg-blue-600 text-white hover:bg-blue-700 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
              >
                <Send size={14} />
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Floating button */}
      <button
        onClick={() => setIsOpen((o) => !o)}
        className="fixed bottom-6 right-6 w-14 h-14 bg-blue-600 hover:bg-blue-700 text-white rounded-full shadow-lg flex items-center justify-center transition-all hover:scale-105 z-50"
      >
        {isOpen ? <X size={22} /> : <MessageCircle size={22} />}
        {/* Unread dot */}
        {!isOpen && messages.length === 0 && (
          <span className="absolute -top-1 -right-1 w-4 h-4 bg-green-500 rounded-full border-2 border-white" />
        )}
      </button>
    </>
  );
}