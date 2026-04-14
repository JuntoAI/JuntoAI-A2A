"use client";

import { useState, useRef, useEffect, useCallback } from "react";
import { Send, Linkedin, Loader2, Globe } from "lucide-react";
import type { BuilderChatMessage, HealthCheckFullReport } from "@/lib/builder/types";
import { streamBuilderChat } from "@/lib/builder/sse-client";
import type { BuilderSSECallbacks } from "@/lib/builder/sse-client";

// ---------------------------------------------------------------------------
// Content cleaning — strip LLM markers and thought signatures
// ---------------------------------------------------------------------------

const JSON_DELTA_RE = /<<JSON_DELTA:\w+:[\s\S]*?>>/g;
// Match thought_signature fields and surrounding JSON wrapper artifacts
const THOUGHT_SIGNATURE_RE = /,?\s*"thought_signature"\s*:\s*"[A-Za-z0-9+/=\s]*"/g;
// Match raw content block wrappers like {"type": "text", "text": "..."}
const CONTENT_BLOCK_RE = /\{"type"\s*:\s*"text"\s*,\s*"text"\s*:\s*"/g;

/** Remove <<JSON_DELTA:...>> markers and thought_signature fields from display text. */
function cleanDisplayContent(text: string): string {
  return text
    .replace(JSON_DELTA_RE, "")
    .replace(THOUGHT_SIGNATURE_RE, "")
    .replace(CONTENT_BLOCK_RE, "")
    .replace(/"\s*}\s*$/g, "")
    .replace(/\n{3,}/g, "\n\n")
    .trim();
}

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

export interface BuilderChatProps {
  sessionId: string;
  email: string;
  onJsonDelta: (section: string, data: Record<string, unknown>) => void;
  onHealthReport: (report: HealthCheckFullReport) => void;
  /** Optional initial template text to pre-fill the chat input (editable, not auto-sent). */
  initialTemplate?: string;
}

// ---------------------------------------------------------------------------
// LinkedIn URL detection
// ---------------------------------------------------------------------------

const LINKEDIN_REGEX = /https:\/\/www\.linkedin\.com\/in\/[^\s]+/g;

export function containsLinkedInUrl(text: string): boolean {
  return LINKEDIN_REGEX.test(text);
}

function renderMessageContent(content: string): React.ReactNode {
  // Reset regex lastIndex
  LINKEDIN_REGEX.lastIndex = 0;
  const parts: React.ReactNode[] = [];
  let lastIndex = 0;
  let match: RegExpExecArray | null;

  while ((match = LINKEDIN_REGEX.exec(content)) !== null) {
    if (match.index > lastIndex) {
      parts.push(content.slice(lastIndex, match.index));
    }
    parts.push(
      <span
        key={match.index}
        className="inline-flex items-center gap-1 rounded bg-blue-900/30 px-1 text-blue-400"
        data-testid="linkedin-indicator"
      >
        <Linkedin size={12} />
        {match[0]}
      </span>,
    );
    lastIndex = match.index + match[0].length;
  }

  if (lastIndex < content.length) {
    parts.push(content.slice(lastIndex));
  }

  return parts.length > 0 ? parts : content;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function BuilderChat({
  sessionId,
  email,
  onJsonDelta,
  onHealthReport,
  initialTemplate,
}: BuilderChatProps) {
  const [messages, setMessages] = useState<BuilderChatMessage[]>([]);
  const [input, setInput] = useState(initialTemplate ?? "");
  const [isWaiting, setIsWaiting] = useState(false);
  const [streamingContent, setStreamingContent] = useState("");
  const [hasReceivedToken, setHasReceivedToken] = useState(false);
  const [researchStatus, setResearchStatus] = useState<
    Map<string, "fetching" | "done" | "failed">
  >(new Map());
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const abortRef = useRef<AbortController | null>(null);

  // Auto-scroll to bottom on new messages
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, streamingContent]);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      abortRef.current?.abort();
    };
  }, []);

  const sendMessage = useCallback(() => {
    const trimmed = input.trim();
    if (!trimmed || isWaiting) return;

    // Add user message
    setMessages((prev) => [...prev, { role: "user", content: trimmed }]);
    setInput("");
    setIsWaiting(true);
    setStreamingContent("");
    setHasReceivedToken(false);
    setResearchStatus(new Map());

    const callbacks: BuilderSSECallbacks = {
      onToken: (token) => {
        setHasReceivedToken(true);
        setStreamingContent((prev) => prev + token);
      },
      onJsonDelta: (section, data) => {
        onJsonDelta(section, data);
      },
      onResearch: (url, status) => {
        setResearchStatus((prev) => {
          const next = new Map(prev);
          next.set(url, status);
          return next;
        });
      },
      onComplete: () => {
        setStreamingContent((prev) => {
          const cleaned = cleanDisplayContent(prev);
          if (cleaned) {
            setMessages((msgs) => [...msgs, { role: "assistant", content: cleaned }]);
          }
          return "";
        });
        setIsWaiting(false);
        setHasReceivedToken(false);
      },
      onError: (message) => {
        setMessages((prev) => [
          ...prev,
          { role: "assistant", content: `Error: ${message}` },
        ]);
        setStreamingContent("");
        setIsWaiting(false);
        setHasReceivedToken(false);
      },
      onHealthStart: () => {
        // Health check started — no UI action needed here
      },
      onHealthFinding: () => {
        // Individual findings handled by parent
      },
      onHealthComplete: (report) => {
        onHealthReport(report);
      },
    };

    abortRef.current = streamBuilderChat(email, sessionId, trimmed, callbacks);
  }, [input, isWaiting, email, sessionId, onJsonDelta, onHealthReport]);

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  // Auto-resize textarea to fit content
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  useEffect(() => {
    const el = textareaRef.current;
    if (el) {
      el.style.height = "auto";
      el.style.height = `${Math.min(el.scrollHeight, 160)}px`;
    }
  }, [input]);

  return (
    <div
      className="flex h-full flex-col bg-[#F4F4F6] rounded-lg"
      data-testid="builder-chat"
    >
      {/* Message list */}
      <div className="flex-1 overflow-y-auto p-4 space-y-3">
        {messages.map((msg, i) => (
          <div
            key={i}
            className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}
          >
            <div
              className={`max-w-[80%] rounded-2xl px-4 py-2 text-sm whitespace-pre-wrap ${
                msg.role === "user"
                  ? "bg-[#007BFF] text-white rounded-br-md"
                  : "bg-white text-[#1C1C1E] shadow-sm rounded-bl-md"
              }`}
              data-testid={`chat-message-${msg.role}`}
            >
              {renderMessageContent(msg.content)}
            </div>
          </div>
        ))}

        {/* Web research indicator */}
        {researchStatus.size > 0 && (
          <div className="flex justify-start" data-testid="research-indicator">
            <div className="rounded-2xl rounded-bl-md bg-white px-4 py-3 text-sm shadow-sm space-y-1">
              {Array.from(researchStatus.entries()).map(([url, status]) => (
                <div key={url} className="flex items-center gap-2 text-gray-500">
                  {status === "fetching" ? (
                    <Loader2 size={14} className="animate-spin text-[#007BFF]" />
                  ) : status === "done" ? (
                    <Globe size={14} className="text-[#00E676]" />
                  ) : (
                    <Globe size={14} className="text-red-400" />
                  )}
                  <span className="truncate max-w-[250px]">
                    {status === "fetching" ? "Researching " : status === "done" ? "Researched " : "Failed "}
                    <span className="text-[#007BFF]">{new URL(url).hostname}</span>
                  </span>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Thinking indicator — before first token arrives */}
        {isWaiting && !hasReceivedToken && !streamingContent && (
          <div className="flex justify-start" data-testid="thinking-indicator">
            <div className="flex items-center gap-2 rounded-2xl rounded-bl-md bg-white px-4 py-3 text-sm text-gray-400 shadow-sm">
              <Loader2 size={16} className="animate-spin text-[#007BFF]" />
              <span>Thinking...</span>
            </div>
          </div>
        )}

        {/* Streaming assistant message (typewriter effect) */}
        {streamingContent && (
          <div className="flex justify-start">
            <div
              className="max-w-[80%] rounded-2xl rounded-bl-md bg-white px-4 py-2 text-sm text-[#1C1C1E] shadow-sm whitespace-pre-wrap"
              data-testid="streaming-message"
            >
              {renderMessageContent(cleanDisplayContent(streamingContent))}
              <span className="inline-block w-1 h-4 ml-0.5 bg-[#007BFF] animate-pulse" />
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Input area */}
      <div className="border-t border-gray-200 p-3">
        <div className="flex items-end gap-2">
          <textarea
            ref={textareaRef}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            disabled={isWaiting}
            rows={1}
            placeholder={
              isWaiting ? "Waiting for response..." : "Describe your scenario..."
            }
            className="flex-1 resize-none rounded-lg border border-gray-300 bg-white px-4 py-2 text-sm text-[#1C1C1E] placeholder-gray-400 focus:border-[#007BFF] focus:outline-none focus:ring-2 focus:ring-[#007BFF]/20 disabled:opacity-50 disabled:cursor-not-allowed"
            data-testid="chat-input"
          />
          <button
            onClick={sendMessage}
            disabled={isWaiting || !input.trim()}
            className="rounded-lg bg-[#007BFF] p-2 text-white transition-colors hover:bg-blue-600 disabled:opacity-50 disabled:cursor-not-allowed"
            data-testid="send-button"
            aria-label="Send message"
          >
            <Send size={18} />
          </button>
        </div>
      </div>
    </div>
  );
}
