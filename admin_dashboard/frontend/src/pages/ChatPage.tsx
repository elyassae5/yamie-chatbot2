import { useState, useRef, useEffect } from "react";
import Layout from "@/components/Layout";
import { Button } from "@/components/ui/button";
import { Send, Bot, User, FileText, Clock } from "lucide-react";
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

const SUGGESTED_QUESTIONS = [
  "Wat zijn de openingstijden van Yamie Amsterdam?",
  "Wat is de procedure bij ziekteverzuim?",
  "Welke allergenen zitten er in de pasta carbonara?",
  "Wat zijn de bezorgtijd normen voor Flamin'wok?",
];

export default function ChatPage() {
  const user = getCurrentUser();
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const hasMessages = messages.length > 0;

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const sendMessage = async (text?: string) => {
    const question = (text ?? input).trim();
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
      const res = await apiClient.post<ChatApiResponse>("/chat/", { question });

      setMessages((prev) => [
        ...prev,
        {
          id: (Date.now() + 1).toString(),
          role: "bot",
          text: res.data.answer,
          timestamp: new Date(),
          sources: res.data.sources,
          response_time: res.data.response_time_seconds,
        },
      ]);
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
      <div className="flex flex-col h-[calc(100vh-8rem)]">

        {/* Empty state — shown before first message */}
        {!hasMessages && (
          <div className="flex-1 flex flex-col items-center justify-center text-center px-4">
            {/* Avatar */}
            <div className="w-16 h-16 rounded-2xl bg-gray-900 flex items-center justify-center mb-4 shadow-lg">
              <Bot className="h-8 w-8 text-white" />
            </div>

            <h2 className="text-xl font-bold text-gray-900 mb-1">
              Hallo{user ? `, ${user.username}` : ""}
            </h2>
            <p className="text-gray-500 text-sm max-w-xs leading-relaxed mb-6">
              Ik ben YamieBot — de interne kennisassistent voor Yamie Pastabar,
              Flamin'wok en Smokey Joe's. Stel me een vraag over procedures,
              locaties, menu's, allergenen of franchisezaken.
            </p>

            {/* Suggested questions */}
            <div className="w-full max-w-sm space-y-2">
              <p className="text-xs text-gray-400 uppercase tracking-wide mb-3">
                Voorbeeldvragen
              </p>
              {SUGGESTED_QUESTIONS.map((q) => (
                <button
                  key={q}
                  type="button"
                  onClick={() => sendMessage(q)}
                  className="w-full text-left px-4 py-3 rounded-xl border border-gray-200 bg-white hover:border-gray-300 hover:bg-gray-50 transition-colors text-sm text-gray-700 shadow-sm"
                >
                  {q}
                </button>
              ))}
            </div>
          </div>
        )}

        {/* Message thread */}
        {hasMessages && (
          <div className="flex-1 overflow-y-auto min-h-0 space-y-6 px-1 py-2">
            {messages.map((msg) => (
              <div
                key={msg.id}
                className={`flex items-start gap-3 ${msg.role === "user" ? "flex-row-reverse" : ""}`}
              >
                {/* Avatar */}
                <div
                  className={`shrink-0 w-8 h-8 rounded-full flex items-center justify-center text-xs font-bold shadow-sm ${
                    msg.role === "user"
                      ? "bg-gray-900 text-white"
                      : "bg-white border border-gray-200 text-gray-700"
                  }`}
                >
                  {msg.role === "user" ? (
                    <User className="h-4 w-4" />
                  ) : (
                    <Bot className="h-4 w-4" />
                  )}
                </div>

                {/* Bubble */}
                <div className={`max-w-[80%] ${msg.role === "user" ? "items-end" : "items-start"} flex flex-col gap-1`}>
                  <div
                    className={`rounded-2xl px-4 py-3 text-sm leading-relaxed shadow-sm ${
                      msg.role === "user"
                        ? "bg-gray-900 text-white rounded-tr-sm"
                        : "bg-white border border-gray-100 text-gray-800 rounded-tl-sm"
                    }`}
                  >
                    <p className="whitespace-pre-wrap">{msg.text}</p>

                    {/* Sources */}
                    {msg.role === "bot" && msg.sources && msg.sources.length > 0 && (
                      <div className="mt-3 pt-3 border-t border-gray-100 space-y-1.5">
                        {[...new Set(msg.sources.map((s) => s.source))]
                          .slice(0, 3)
                          .map((src) => {
                            const parts = src.split("/");
                            const name = parts[parts.length - 1];
                            return (
                              <div key={src} className="flex items-center gap-1.5">
                                <FileText className="h-3 w-3 text-gray-300 shrink-0" />
                                <span className="text-xs text-gray-400 truncate">{name}</span>
                              </div>
                            );
                          })}
                      </div>
                    )}
                  </div>

                  {/* Meta row */}
                  <div className={`flex items-center gap-2 px-1 ${msg.role === "user" ? "flex-row-reverse" : ""}`}>
                    <span className="text-xs text-gray-300">
                      {msg.timestamp.toLocaleTimeString("nl-NL", {
                        hour: "2-digit",
                        minute: "2-digit",
                      })}
                    </span>
                    {msg.response_time !== undefined && (
                      <span className="flex items-center gap-0.5 text-xs text-gray-300">
                        <Clock className="h-3 w-3" />
                        {msg.response_time.toFixed(1)}s
                      </span>
                    )}
                  </div>
                </div>
              </div>
            ))}

            {/* Typing indicator */}
            {loading && (
              <div className="flex items-start gap-3">
                <div className="shrink-0 w-8 h-8 rounded-full bg-white border border-gray-200 flex items-center justify-center shadow-sm">
                  <Bot className="h-4 w-4 text-gray-700" />
                </div>
                <div className="bg-white border border-gray-100 rounded-2xl rounded-tl-sm px-4 py-3.5 shadow-sm">
                  <div className="flex space-x-1.5 items-center">
                    <div className="w-2 h-2 bg-gray-300 rounded-full animate-bounce [animation-delay:0ms]" />
                    <div className="w-2 h-2 bg-gray-300 rounded-full animate-bounce [animation-delay:150ms]" />
                    <div className="w-2 h-2 bg-gray-300 rounded-full animate-bounce [animation-delay:300ms]" />
                  </div>
                </div>
              </div>
            )}

            <div ref={bottomRef} />
          </div>
        )}

        {/* Input bar */}
        <div className={`${hasMessages ? "mt-3" : "mt-4"} flex gap-2 items-center bg-white border border-gray-200 rounded-2xl px-3 py-2 shadow-sm focus-within:border-gray-400 transition-colors`}>
          <input
            ref={inputRef}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Stel een vraag..."
            disabled={loading}
            autoFocus
            className="flex-1 bg-transparent text-sm text-gray-800 placeholder-gray-400 outline-none"
          />
          <Button
            onClick={() => sendMessage()}
            disabled={loading || !input.trim()}
            size="icon"
            className="h-8 w-8 rounded-xl shrink-0 bg-gray-900 hover:bg-gray-700 disabled:opacity-30"
          >
            <Send className="h-3.5 w-3.5" />
          </Button>
        </div>
      </div>
    </Layout>
  );
}
