import { useState, useRef, useEffect } from "react";
import Layout from "@/components/Layout";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Send } from "lucide-react";
import { apiClient } from "@/lib/api";
import { getCurrentUser } from "@/lib/auth";

interface Message {
  id: string;
  role: "user" | "bot";
  text: string;
  timestamp: Date;
  sources?: Source[];
  response_time?: number;
}

interface Source {
  source: string;
  category: string;
  similarity_score: number;
}

interface ChatApiResponse {
  question: string;
  answer: string;
  has_answer: boolean;
  response_time_seconds: number;
  sources: Source[];
}

export default function ChatPage() {
  const user = getCurrentUser();
  const [messages, setMessages] = useState<Message[]>([
    {
      id: "welcome",
      role: "bot",
      text: `Hallo${user ? ` ${user.username}` : ""}! Stel me een vraag over Yamie Pastabar, Flamin'wok of Smokey Joe's.`,
      timestamp: new Date(),
    },
  ]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  // Auto-scroll to bottom on new messages
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const sendMessage = async () => {
    const question = input.trim();
    if (!question || loading) return;

    const userMessage: Message = {
      id: Date.now().toString(),
      role: "user",
      text: question,
      timestamp: new Date(),
    };

    setMessages((prev) => [...prev, userMessage]);
    setInput("");
    setLoading(true);

    try {
      const res = await apiClient.post<ChatApiResponse>("/chat/", {
        question,
      });

      const botMessage: Message = {
        id: (Date.now() + 1).toString(),
        role: "bot",
        text: res.data.answer,
        timestamp: new Date(),
        sources: res.data.sources,
        response_time: res.data.response_time_seconds,
      };

      setMessages((prev) => [...prev, botMessage]);
    } catch {
      setMessages((prev) => [
        ...prev,
        {
          id: (Date.now() + 1).toString(),
          role: "bot",
          text: "Er is een fout opgetreden. Probeer het opnieuw.",
          timestamp: new Date(),
        },
      ]);
    } finally {
      setLoading(false);
      inputRef.current?.focus();
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  return (
    <Layout>
      <div className="flex flex-col" style={{ height: "calc(100vh - 10rem)" }}>
        <div className="mb-4">
          <h1 className="text-2xl font-bold text-gray-900">Chat</h1>
          <p className="text-sm text-gray-500">Stel vragen aan YamieBot</p>
        </div>

        {/* Messages */}
        <div className="flex-1 overflow-y-auto bg-white border border-gray-200 rounded-lg p-4 space-y-4 min-h-0">
          {messages.map((msg) => (
            <div
              key={msg.id}
              className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}
            >
              <div
                className={`max-w-[75%] rounded-2xl px-4 py-3 text-sm ${
                  msg.role === "user"
                    ? "bg-gray-900 text-white rounded-br-sm"
                    : "bg-gray-100 text-gray-900 rounded-bl-sm"
                }`}
              >
                <p className="whitespace-pre-wrap leading-relaxed">{msg.text}</p>

                {/* Sources — only show for bot messages with sources */}
                {msg.role === "bot" && msg.sources && msg.sources.length > 0 && (
                  <div className="mt-2 pt-2 border-t border-gray-200 space-y-1">
                    {[...new Set(msg.sources.map((s) => s.source))].slice(0, 3).map((src) => (
                      <p key={src} className="text-xs text-gray-400 truncate">
                        📄 {src}
                      </p>
                    ))}
                  </div>
                )}

                {/* Timestamp + response time */}
                <p className={`text-xs mt-1 ${msg.role === "user" ? "text-gray-400" : "text-gray-400"}`}>
                  {msg.timestamp.toLocaleTimeString("nl-NL", {
                    hour: "2-digit",
                    minute: "2-digit",
                  })}
                  {msg.response_time !== undefined && (
                    <span className="ml-2">{msg.response_time.toFixed(1)}s</span>
                  )}
                </p>
              </div>
            </div>
          ))}

          {/* Loading indicator */}
          {loading && (
            <div className="flex justify-start">
              <div className="bg-gray-100 rounded-2xl rounded-bl-sm px-4 py-3">
                <div className="flex space-x-1 items-center h-4">
                  <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: "0ms" }} />
                  <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: "150ms" }} />
                  <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: "300ms" }} />
                </div>
              </div>
            </div>
          )}

          <div ref={bottomRef} />
        </div>

        {/* Input bar */}
        <div className="mt-3 flex gap-2">
          <Input
            ref={inputRef}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Stel een vraag..."
            disabled={loading}
            className="flex-1"
            autoFocus
          />
          <Button onClick={sendMessage} disabled={loading || !input.trim()} size="icon">
            <Send className="h-4 w-4" />
          </Button>
        </div>
      </div>
    </Layout>
  );
}
