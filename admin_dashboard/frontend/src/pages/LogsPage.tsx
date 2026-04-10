import { useState, useEffect } from "react";
import Layout from "@/components/Layout";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Alert, AlertDescription } from "@/components/ui/alert";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  Search,
  ChevronLeft,
  ChevronRight,
  ChevronDown,
  ChevronUp,
  Copy,
  Check,
  MessageSquare,
  Activity,
  Users,
  Filter,
  X,
} from "lucide-react";
import { apiClient } from "@/lib/api";
import { getWhitelist } from "@/api/whitelist";
import ReactMarkdown from "react-markdown";

interface DebugChunk {
  source: string;
  namespace: string;
  score: number;
  text: string;
  text_preview?: string; // backwards compat with old logs
  status: "passed" | "filtered";
}

interface DebugInfo {
  threshold: number;
  chunks_passed: number;
  chunks_filtered: number;
  passed: DebugChunk[];
  filtered: DebugChunk[];
}

interface LogEntry {
  id: string;
  created_at: string;
  user_id: string | null;
  question: string | null;
  transformed_question: string | null;
  answer: string | null;
  has_answer: boolean | null;
  response_time_seconds: number | null;
  sources: any;
  chunks_retrieved: number | null;
  model: string | null;
  total_tokens: number | null;
  error: string | null;
  system_prompt_version: string | null;
  debug_info: DebugInfo | null;
}

interface LogsResponse {
  logs: LogEntry[];
  total_count: number;
  page: number;
  page_size: number;
}

interface LogStats {
  total_queries: number;
  average_response_time: number;
  success_rate: number;
  total_users: number;
  successful_queries: number;
  failed_queries: number;
}

export default function LogsPage() {
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [stats, setStats] = useState<LogStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [search, setSearch] = useState("");
  const [searchInput, setSearchInput] = useState("");
  const [selectedUser, setSelectedUser] = useState("");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [page, setPage] = useState(1);
  const [totalCount, setTotalCount] = useState(0);
  const [selectedLog, setSelectedLog] = useState<LogEntry | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [phoneToName, setPhoneToName] = useState<Record<string, string>>({});
  const [copiedField, setCopiedField] = useState<string | null>(null);
  const [showDebug, setShowDebug] = useState(false);
  const [expandedChunks, setExpandedChunks] = useState<Set<string>>(new Set());
  const pageSize = 20;

  useEffect(() => {
    loadStats();
    loadWhitelistNames();
  }, []);
  useEffect(() => {
    loadLogs();
  }, [page, search, selectedUser, dateFrom, dateTo]);

  const loadWhitelistNames = async () => {
    try {
      const entries = await getWhitelist();
      const map: Record<string, string> = {};
      entries.forEach((e) => {
        // Store by both formats: "whatsapp:+316..." and "+316..."
        map[e.phone_number] = e.name;
        map[e.phone_number.replace("whatsapp:", "")] = e.name;
      });
      setPhoneToName(map);
    } catch {
      // Silently fail - fallback to phone number
    }
  };

  const formatUserDisplay = (userId: string | null) => {
    if (!userId) return "—";
    const clean = userId.replace("whatsapp:", "");
    return phoneToName[userId] || phoneToName[clean] || clean;
  };

  const copyToClipboard = async (text: string, field: string) => {
    try {
      await navigator.clipboard.writeText(text);
      setCopiedField(field);
      setTimeout(() => setCopiedField(null), 2000);
    } catch {
      // fallback silently
    }
  };

  const loadStats = async () => {
    try {
      const response = await apiClient.get<LogStats>("/logs/stats/summary");
      setStats(response.data);
    } catch (err) {
      console.error("Failed to load stats:", err);
    }
  };

  const loadLogs = async () => {
    try {
      setLoading(true);
      const params: any = { page, page_size: pageSize };
      if (search) params.search = search;
      if (selectedUser) params.user_id = selectedUser;
      if (dateFrom) params.date_from = dateFrom;
      if (dateTo) params.date_to = dateTo;
      const response = await apiClient.get<LogsResponse>("/logs/", { params });
      setLogs(response.data.logs);
      setTotalCount(response.data.total_count);
      setError("");
    } catch (err) {
      setError("Kon vragen niet laden");
    } finally {
      setLoading(false);
    }
  };

  const openLogDetail = async (log: LogEntry) => {
    // Show modal immediately with list data, then fetch full detail (debug_info)
    setSelectedLog(log);
    setDetailLoading(true);
    try {
      const response = await apiClient.get<LogEntry>(`/logs/${log.id}`);
      setSelectedLog(response.data);
    } catch (err) {
      console.error("Failed to fetch log detail:", err);
    } finally {
      setDetailLoading(false);
    }
  };

  const handleSearch = () => {
    setSearch(searchInput);
    setPage(1);
  };
  const handleClearSearch = () => {
    setSearchInput("");
    setSearch("");
    setSelectedUser("");
    setDateFrom("");
    setDateTo("");
    setPage(1);
  };
  const totalPages = Math.ceil(totalCount / pageSize);

  const formatDate = (dateStr: string) => {
    const d = new Date(dateStr);
    return (
      d.toLocaleDateString("nl-NL") +
      " " +
      d.toLocaleTimeString("nl-NL", { hour: "2-digit", minute: "2-digit" })
    );
  };

  const formatDateShort = (dateStr: string) => {
    const d = new Date(dateStr);
    return (
      d.toLocaleDateString("nl-NL", { day: "2-digit", month: "2-digit" }) +
      " " +
      d.toLocaleTimeString("nl-NL", { hour: "2-digit", minute: "2-digit" })
    );
  };

  const truncate = (text: string | null, maxLen: number) => {
    if (!text) return "—";
    return text.length > maxLen ? text.slice(0, maxLen) + "…" : text;
  };

  const [showFilters, setShowFilters] = useState(false);
  const hasActiveFilters = !!(search || selectedUser || dateFrom || dateTo);

  const statCards = stats
    ? [
        {
          label: "Totale Vragen",
          value: stats.total_queries.toLocaleString(),
          icon: MessageSquare,
          color: "text-blue-600",
          bg: "bg-blue-50",
        },
        {
          label: "Vandaag",
          value: ((stats as any).queries_today ?? 0).toString(),
          icon: Activity,
          color: "text-orange-600",
          bg: "bg-orange-50",
        },
        {
          label: "Gebruikers",
          value: stats.total_users.toString(),
          icon: Users,
          color: "text-purple-600",
          bg: "bg-purple-50",
        },
      ]
    : [];

  return (
    <Layout>
      <div>
        {/* Header */}
        <div className="mb-6">
          <h1 className="text-2xl sm:text-3xl font-bold text-gray-900">
            Vragen Overzicht
          </h1>
          <p className="mt-1 text-sm text-gray-600">
            Bekijk alle chatbot vragen en antwoorden
          </p>
        </div>

        {/* Stats cards */}
        <div className="grid grid-cols-3 gap-3 mb-6">
          {loading && !stats
            ? Array.from({ length: 3 }).map((_, i) => (
                <div key={i} className="bg-white shadow rounded-lg p-3 animate-pulse">
                  <div className="h-3 bg-gray-200 rounded w-10 mb-2 mx-auto" />
                  <div className="h-6 bg-gray-200 rounded w-8 mx-auto" />
                </div>
              ))
            : statCards.map(({ label, value, icon: Icon, color, bg }) => (
                <div key={label} className="bg-white shadow rounded-lg p-3 flex flex-col items-center text-center">
                  <div className={`${bg} rounded-md p-2 mb-1.5`}>
                    <Icon className={`h-4 w-4 ${color}`} />
                  </div>
                  <p className={`text-lg font-bold leading-none ${color}`}>{value}</p>
                  <p className="text-xs text-gray-400 mt-1 leading-tight">{label}</p>
                </div>
              ))}
        </div>

        {/* Search + Filter toggle */}
        <div className="flex items-center gap-2 mb-3">
          <div className="relative flex-1">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400" />
            <Input
              className="pl-9"
              placeholder="Zoeken in vragen en antwoorden..."
              value={searchInput}
              onChange={(e) => setSearchInput(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && handleSearch()}
            />
          </div>
          <button
            onClick={() => setShowFilters(!showFilters)}
            className={`flex items-center gap-1.5 px-3 py-2 rounded-md border text-sm transition-colors ${
              hasActiveFilters
                ? "border-blue-200 bg-blue-50 text-blue-700"
                : "border-gray-200 bg-white text-gray-600 hover:bg-gray-50"
            }`}
          >
            <Filter className="h-4 w-4" />
            <span className="hidden sm:inline">Filters</span>
            {hasActiveFilters && (
              <span className="w-1.5 h-1.5 rounded-full bg-blue-600" />
            )}
          </button>
        </div>

        {/* Collapsible filters */}
        {showFilters && (
          <div className="bg-white shadow rounded-lg p-4 mb-4">
            <div className="flex flex-col gap-3 sm:flex-row sm:items-end">
              <div className="flex-1 min-w-0">
                <label className="text-xs font-medium text-gray-500 mb-1 block">Gebruiker</label>
                <select
                  title="Gebruiker filter"
                  className="w-full border border-gray-200 rounded-md px-3 py-2 text-sm bg-white text-gray-700 h-9"
                  value={selectedUser}
                  onChange={(e) => { setSelectedUser(e.target.value); setPage(1); }}
                >
                  <option value="">Alle gebruikers</option>
                  {Object.entries(phoneToName)
                    .filter(([key]) => key.startsWith("whatsapp:"))
                    .map(([phone, name]) => (
                      <option key={phone} value={phone}>{name}</option>
                    ))}
                </select>
              </div>
              <div className="sm:w-40">
                <label className="text-xs font-medium text-gray-500 mb-1 block">Van</label>
                <input
                  type="date"
                  title="Datum van"
                  className="w-full border border-gray-200 rounded-md px-3 py-2 text-sm bg-white text-gray-700 h-9"
                  value={dateFrom}
                  onChange={(e) => { setDateFrom(e.target.value); setPage(1); }}
                />
              </div>
              <div className="sm:w-40">
                <label className="text-xs font-medium text-gray-500 mb-1 block">Tot</label>
                <input
                  type="date"
                  title="Datum tot"
                  className="w-full border border-gray-200 rounded-md px-3 py-2 text-sm bg-white text-gray-700 h-9"
                  value={dateTo}
                  onChange={(e) => { setDateTo(e.target.value); setPage(1); }}
                />
              </div>
              <div className="flex gap-2">
                <Button onClick={handleSearch} size="sm" className="bg-gray-900 hover:bg-gray-700 text-white">
                  Toepassen
                </Button>
                {hasActiveFilters && (
                  <Button variant="outline" size="sm" onClick={handleClearSearch} className="gap-1">
                    <X className="h-3.5 w-3.5" /> Wissen
                  </Button>
                )}
              </div>
            </div>
          </div>
        )}

        {/* Active filter badges */}
        {hasActiveFilters && !showFilters && (
          <div className="flex items-center gap-2 mb-3 flex-wrap">
            <span className="text-xs text-gray-400">Actieve filters:</span>
            {search && (
              <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-blue-50 text-blue-700 text-xs">
                "{search}"
                <button title="Zoekfilter wissen" onClick={() => { setSearch(""); setSearchInput(""); setPage(1); }}>
                  <X className="h-3 w-3" />
                </button>
              </span>
            )}
            {selectedUser && (
              <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-purple-50 text-purple-700 text-xs">
                {phoneToName[selectedUser] || selectedUser.replace("whatsapp:", "")}
                <button title="Gebruikerfilter wissen" onClick={() => { setSelectedUser(""); setPage(1); }}>
                  <X className="h-3 w-3" />
                </button>
              </span>
            )}
            {(dateFrom || dateTo) && (
              <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-orange-50 text-orange-700 text-xs">
                {dateFrom || "..."} — {dateTo || "..."}
                <button title="Datumfilter wissen" onClick={() => { setDateFrom(""); setDateTo(""); setPage(1); }}>
                  <X className="h-3 w-3" />
                </button>
              </span>
            )}
          </div>
        )}

        {error && (
          <Alert variant="destructive" className="mb-4">
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        )}

        {/* Loading state */}
        {loading && logs.length === 0 ? (
          <div className="bg-white shadow rounded-lg overflow-hidden">
            <div className="p-4 space-y-3">
              {Array.from({ length: 6 }).map((_, i) => (
                <div key={i} className="animate-pulse flex items-start gap-3 py-2">
                  <div className="w-2 h-2 bg-gray-200 rounded-full mt-1.5 flex-shrink-0" />
                  <div className="flex-1">
                    <div className="h-4 bg-gray-200 rounded w-3/4 mb-2" />
                    <div className="h-3 bg-gray-200 rounded w-1/2" />
                  </div>
                </div>
              ))}
            </div>
          </div>
        ) : (
          <div className={loading ? "opacity-50 pointer-events-none" : ""}>
            {/* Mobile: Card list */}
            <div className="sm:hidden space-y-2">
              {logs.length === 0 ? (
                <div className="bg-white shadow rounded-lg p-8 text-center text-gray-400 text-sm">
                  {search ? "Geen resultaten gevonden" : "Nog geen vragen gesteld"}
                </div>
              ) : (
                logs.map((log) => (
                  <div
                    key={log.id}
                    className="bg-white shadow rounded-lg px-4 py-3.5 cursor-pointer active:bg-gray-50 transition-colors"
                    onClick={() => openLogDetail(log)}
                  >
                    <div className="flex items-start gap-3">
                      <div className="mt-1.5 shrink-0 w-1.5 h-1.5 rounded-full bg-gray-300" />
                      <div className="flex-1 min-w-0">
                        <p className="text-sm font-medium text-gray-900 leading-snug">
                          {truncate(log.question, 90)}
                        </p>
                        <p className="text-xs text-gray-400 mt-1.5 line-clamp-1">
                          {truncate(log.answer, 70)}
                        </p>
                        <div className="flex items-center gap-2 mt-1.5">
                          <span className="text-xs text-gray-300">
                            {log.created_at ? formatDateShort(log.created_at) : "—"}
                          </span>
                          <span className="text-xs text-gray-300">·</span>
                          <span className="text-xs text-gray-400 font-medium">
                            {formatUserDisplay(log.user_id)}
                          </span>
                        </div>
                      </div>
                    </div>
                  </div>
                ))
              )}
            </div>

            {/* Desktop: Table */}
            <div className="hidden sm:block bg-white shadow rounded-lg overflow-hidden">
              <Table>
                <TableHeader>
                  <TableRow className="bg-gray-50/50">
                    <TableHead className="w-8 pl-4"></TableHead>
                    <TableHead className="w-36">Tijdstip</TableHead>
                    <TableHead className="w-32">Gebruiker</TableHead>
                    <TableHead>Vraag</TableHead>
                    <TableHead className="w-1/3">Antwoord</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {logs.length === 0 ? (
                    <TableRow>
                      <TableCell colSpan={5} className="text-center text-gray-400 py-12">
                        {search ? "Geen resultaten gevonden" : "Nog geen vragen gesteld"}
                      </TableCell>
                    </TableRow>
                  ) : (
                    logs.map((log) => (
                      <TableRow
                        key={log.id}
                        className="cursor-pointer hover:bg-gray-50/70 transition-colors"
                        onClick={() => openLogDetail(log)}
                      >
                        <TableCell className="pl-4 pr-0">
                          <div className="w-1.5 h-1.5 rounded-full bg-gray-300" />
                        </TableCell>
                        <TableCell className="text-xs text-gray-400 whitespace-nowrap">
                          {log.created_at ? formatDate(log.created_at) : "—"}
                        </TableCell>
                        <TableCell className="text-sm text-gray-600 font-medium">
                          {formatUserDisplay(log.user_id)}
                        </TableCell>
                        <TableCell className="text-sm text-gray-900">
                          {truncate(log.question, 80)}
                        </TableCell>
                        <TableCell className="text-sm text-gray-400">
                          {truncate(log.answer, 70)}
                        </TableCell>
                      </TableRow>
                    ))
                  )}
                </TableBody>
              </Table>
            </div>

            {/* Pagination */}
            {totalPages > 1 && (
              <div className="flex items-center justify-between mt-4 flex-wrap gap-2">
                <p className="text-xs text-gray-400">
                  {totalCount} resultaten — pagina {page} van {totalPages}
                </p>
                <div className="flex items-center gap-1">
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => setPage((p) => p - 1)}
                    disabled={page === 1}
                    className="h-8 w-8 p-0"
                  >
                    <ChevronLeft className="h-4 w-4" />
                  </Button>
                  {Array.from({ length: totalPages }, (_, i) => i + 1)
                    .filter(
                      (p) =>
                        p === 1 || p === totalPages || Math.abs(p - page) <= 2,
                    )
                    .reduce<(number | string)[]>((acc, p, idx, arr) => {
                      if (
                        idx > 0 &&
                        (p as number) - (arr[idx - 1] as number) > 1
                      )
                        acc.push("...");
                      acc.push(p);
                      return acc;
                    }, [])
                    .map((p, idx) =>
                      p === "..." ? (
                        <span
                          key={`ellipsis-${idx}`}
                          className="px-1.5 text-xs text-gray-300"
                        >
                          ...
                        </span>
                      ) : (
                        <Button
                          key={p}
                          variant={p === page ? "default" : "outline"}
                          size="sm"
                          onClick={() => setPage(p as number)}
                          className={`h-8 w-8 p-0 text-xs ${p === page ? "bg-gray-900 text-white" : ""}`}
                        >
                          {p}
                        </Button>
                      ),
                    )}
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => setPage((p) => p + 1)}
                    disabled={page === totalPages}
                    className="h-8 w-8 p-0"
                  >
                    <ChevronRight className="h-4 w-4" />
                  </Button>
                </div>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Detail modal */}
      <Dialog
        open={!!selectedLog}
        onOpenChange={() => {
          setSelectedLog(null);
          setShowDebug(false);
          setExpandedChunks(new Set());
        }}
      >
        <DialogContent className="w-[95vw] max-w-2xl max-h-[85vh] overflow-y-auto overflow-x-hidden">
          <DialogHeader>
            <DialogTitle>Vraag Detail</DialogTitle>
          </DialogHeader>
          {selectedLog && (
            <div
              className="space-y-4 text-sm overflow-hidden"
              style={{ wordBreak: "break-word" }}
            >
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <p className="font-medium text-gray-500">Tijdstip</p>
                  <p className="text-xs">
                    {selectedLog.created_at
                      ? formatDate(selectedLog.created_at)
                      : "—"}
                  </p>
                </div>
                <div>
                  <p className="font-medium text-gray-500">Gebruiker</p>
                  <p className="text-xs font-medium">
                    {formatUserDisplay(selectedLog.user_id)}
                  </p>
                </div>
              </div>
              <div>
                <div className="flex justify-between items-center mb-1">
                  <p className="font-medium text-gray-500">Vraag</p>
                  <button
                    onClick={() =>
                      copyToClipboard(selectedLog.question ?? "", "question")
                    }
                    className="flex items-center gap-1 text-xs text-gray-400 hover:text-gray-600"
                  >
                    {copiedField === "question" ? (
                      <>
                        <Check className="h-3 w-3 text-green-500" /> Gekopieerd
                      </>
                    ) : (
                      <>
                        <Copy className="h-3 w-3" /> Kopieer
                      </>
                    )}
                  </button>
                </div>
                <div className="bg-gray-50 rounded p-3">
                  {selectedLog.question ?? "—"}
                </div>
              </div>
              {selectedLog.transformed_question &&
                selectedLog.transformed_question !== selectedLog.question && (
                  <div>
                    <p className="font-medium text-gray-500 mb-1">
                      Getransformeerde vraag
                    </p>
                    <div className="bg-gray-50 rounded p-3 italic text-gray-600">
                      {selectedLog.transformed_question}
                    </div>
                  </div>
                )}
              <div>
                <div className="flex justify-between items-center mb-1">
                  <p className="font-medium text-gray-500">Antwoord</p>
                  <button
                    onClick={() =>
                      copyToClipboard(selectedLog.answer ?? "", "answer")
                    }
                    className="flex items-center gap-1 text-xs text-gray-400 hover:text-gray-600"
                  >
                    {copiedField === "answer" ? (
                      <>
                        <Check className="h-3 w-3 text-green-500" /> Gekopieerd
                      </>
                    ) : (
                      <>
                        <Copy className="h-3 w-3" /> Kopieer
                      </>
                    )}
                  </button>
                </div>
                <div className="bg-gray-50 rounded p-3 prose prose-sm max-w-none">
                  <ReactMarkdown>{selectedLog.answer ?? "—"}</ReactMarkdown>
                </div>
              </div>
              {selectedLog.error && (
                <div>
                  <p className="font-medium text-red-500 mb-1">Fout</p>
                  <div className="bg-red-50 rounded p-3 text-red-700">
                    {selectedLog.error}
                  </div>
                </div>
              )}

              {/* Bronnen & Context Panel */}
              {detailLoading && !selectedLog.debug_info && (
                <div className="border rounded-lg p-3 bg-gray-50">
                  <div className="animate-pulse flex items-center gap-2">
                    <div className="h-4 bg-gray-200 rounded w-32" />
                    <div className="h-3 bg-gray-200 rounded w-20" />
                  </div>
                </div>
              )}
              {selectedLog.debug_info && (
                <div className="border rounded-lg overflow-hidden min-w-0">
                  <button
                    onClick={() => setShowDebug(!showDebug)}
                    className="w-full flex items-center justify-between p-3 bg-gray-50 hover:bg-gray-100 transition-colors min-w-0"
                  >
                    <div className="flex items-center gap-2 flex-wrap min-w-0">
                      <span className="font-medium text-gray-700 text-sm">
                        Bronnen & context
                      </span>
                      <span className="text-xs text-gray-500 break-words">
                        {selectedLog.debug_info.chunks_passed} gebruikt ·{" "}
                        {selectedLog.debug_info.chunks_filtered} genegeerd
                      </span>
                    </div>
                    {showDebug ? (
                      <ChevronUp className="h-4 w-4 text-gray-500" />
                    ) : (
                      <ChevronDown className="h-4 w-4 text-gray-500" />
                    )}
                  </button>

                  {showDebug && (
                    <div className="p-3 space-y-3 max-h-[500px] overflow-y-auto overflow-x-hidden min-w-0">
                      {/* Used chunks */}
                      {selectedLog.debug_info.passed.length > 0 && (
                        <div>
                          <p className="text-xs font-medium text-green-700 mb-2">
                            ✅ Gebruikt voor antwoord (
                            {selectedLog.debug_info.passed.length})
                          </p>
                          <div className="space-y-2">
                            {selectedLog.debug_info.passed.map((chunk, i) => {
                              const chunkKey = `passed-${i}`;
                              const isExpanded = expandedChunks.has(chunkKey);
                              const sourceParts = chunk.source.split("/");
                              const sourceName =
                                sourceParts.length > 1
                                  ? sourceParts[sourceParts.length - 1]
                                  : chunk.source;
                              const sourceFolder =
                                sourceParts.length > 1
                                  ? sourceParts.slice(0, -1).join(" › ")
                                  : "";
                              const fullText =
                                chunk.text || chunk.text_preview || "";
                              return (
                                <div
                                  key={chunkKey}
                                  className="border-l-2 border-green-400 pl-3 py-1 min-w-0"
                                >
                                  <div className="flex items-start gap-2 flex-wrap min-w-0">
                                    <span className="text-xs font-mono font-bold text-green-700 shrink-0">
                                      {chunk.score.toFixed(3)}
                                    </span>
                                    <span className="text-xs font-medium text-gray-800 break-words min-w-0">
                                      {sourceName}
                                    </span>
                                  </div>
                                  {sourceFolder && (
                                    <p className="text-xs text-gray-400 mt-0.5 break-words">
                                      {sourceFolder}
                                    </p>
                                  )}
                                  <div className="mt-1">
                                    <p className="text-xs text-gray-600 whitespace-pre-line">
                                      {isExpanded
                                        ? fullText
                                        : fullText.length > 150
                                          ? fullText.slice(0, 150) + "…"
                                          : fullText}
                                    </p>
                                    {fullText.length > 150 && (
                                      <button
                                        onClick={() => {
                                          const next = new Set(expandedChunks);
                                          isExpanded
                                            ? next.delete(chunkKey)
                                            : next.add(chunkKey);
                                          setExpandedChunks(next);
                                        }}
                                        className="text-xs text-blue-600 hover:text-blue-800 mt-1"
                                      >
                                        {isExpanded
                                          ? "Minder tonen"
                                          : "Meer tonen"}
                                      </button>
                                    )}
                                  </div>
                                </div>
                              );
                            })}
                          </div>
                        </div>
                      )}

                      {/* Filtered chunks */}
                      {selectedLog.debug_info.filtered.length > 0 && (
                        <div>
                          <p className="text-xs font-medium text-red-600 mb-2">
                            ❌ Genegeerd — score te laag (
                            {selectedLog.debug_info.filtered.length})
                          </p>
                          <div className="space-y-2">
                            {selectedLog.debug_info.filtered.map((chunk, i) => {
                              const chunkKey = `filtered-${i}`;
                              const isExpanded = expandedChunks.has(chunkKey);
                              const sourceParts = chunk.source.split("/");
                              const sourceName =
                                sourceParts.length > 1
                                  ? sourceParts[sourceParts.length - 1]
                                  : chunk.source;
                              const sourceFolder =
                                sourceParts.length > 1
                                  ? sourceParts.slice(0, -1).join(" › ")
                                  : "";
                              const fullText =
                                chunk.text || chunk.text_preview || "";
                              return (
                                <div
                                  key={chunkKey}
                                  className="border-l-2 border-red-300 pl-3 py-1 opacity-70 min-w-0"
                                >
                                  <div className="flex items-start gap-2 flex-wrap min-w-0">
                                    <span className="text-xs font-mono font-bold text-red-600 shrink-0">
                                      {chunk.score.toFixed(3)}
                                    </span>
                                    <span className="text-xs font-medium text-gray-700 break-words min-w-0">
                                      {sourceName}
                                    </span>
                                  </div>
                                  {sourceFolder && (
                                    <p className="text-xs text-gray-400 mt-0.5 break-words">
                                      {sourceFolder}
                                    </p>
                                  )}
                                  <div className="mt-1">
                                    <p className="text-xs text-gray-500 whitespace-pre-line">
                                      {isExpanded
                                        ? fullText
                                        : fullText.length > 150
                                          ? fullText.slice(0, 150) + "…"
                                          : fullText}
                                    </p>
                                    {fullText.length > 150 && (
                                      <button
                                        onClick={() => {
                                          const next = new Set(expandedChunks);
                                          isExpanded
                                            ? next.delete(chunkKey)
                                            : next.add(chunkKey);
                                          setExpandedChunks(next);
                                        }}
                                        className="text-xs text-blue-600 hover:text-blue-800 mt-1"
                                      >
                                        {isExpanded
                                          ? "Minder tonen"
                                          : "Meer tonen"}
                                      </button>
                                    )}
                                  </div>
                                </div>
                              );
                            })}
                          </div>
                        </div>
                      )}

                      {selectedLog.debug_info.passed.length === 0 &&
                        selectedLog.debug_info.filtered.length === 0 && (
                          <p className="text-xs text-gray-500 italic">
                            Geen documenten gevonden voor deze vraag
                          </p>
                        )}
                    </div>
                  )}
                </div>
              )}
            </div>
          )}
        </DialogContent>
      </Dialog>
    </Layout>
  );
}
