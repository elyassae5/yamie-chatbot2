import { useState, useEffect } from "react";
import Layout from "@/components/Layout";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Alert, AlertDescription } from "@/components/ui/alert";
import {
  RefreshCw,
  CheckCircle,
  XCircle,
  Clock,
  AlertTriangle,
  Play,
} from "lucide-react";
import { apiClient } from "@/lib/api";

// ========== TYPES ==========

interface SourceStatus {
  name: string;
  namespace: string;
  last_sync: string | null;
}

interface SyncHistoryEntry {
  id: string;
  status: string;
  trigger: string;
  sources_checked: number;
  sources_with_changes: number;
  total_pages_changed: number;
  total_chunks_upserted: number;
  duration_seconds: number;
  started_at: string | null;
  completed_at: string | null;
  details: Record<string, unknown> | null;
}

interface SourceDetail {
  source_key: string;
  namespace: string;
  status: string;
  pages_checked: number;
  pages_changed: number;
  pages_synced: number;
  pages_failed: number;
  chunks_upserted: number;
  duration_seconds: number;
  error: string | null;
}

interface SyncRunResult {
  status: string;
  sources_checked: number;
  sources_with_changes: number;
  total_pages_changed: number;
  total_chunks_upserted: number;
  duration_seconds: number;
  source_details: SourceDetail[];
}

// ========== COMPONENT ==========

export default function SyncPage() {
  const [sourceStatus, setSourceStatus] = useState<
    Record<string, SourceStatus>
  >({});
  const [history, setHistory] = useState<SyncHistoryEntry[]>([]);
  const [historyTotal, setHistoryTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [syncing, setSyncing] = useState(false);
  const [syncResult, setSyncResult] = useState<SyncRunResult | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    try {
      setLoading(true);
      setError("");

      const [statusRes, historyRes] = await Promise.all([
        apiClient.get("/sync/status"),
        apiClient.get("/sync/history", { params: { page: 1, page_size: 10 } }),
      ]);

      // Filter out internal keys that start with _
      const sources: Record<string, SourceStatus> = {};
      for (const [key, value] of Object.entries(statusRes.data.sources)) {
        if (!key.startsWith("_")) {
          sources[key] = value as SourceStatus;
        }
      }
      setSourceStatus(sources);
      setHistory(historyRes.data.logs);
      setHistoryTotal(historyRes.data.total);
    } catch (err) {
      setError("Kon sync status niet laden");
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const runSync = async (forceFull: boolean = false) => {
    try {
      setSyncing(true);
      setSyncResult(null);
      setError("");

      const response = await apiClient.post<SyncRunResult>("/sync/run", {
        force_full: forceFull,
      });

      setSyncResult(response.data);

      // Refresh data after sync
      await loadData();
    } catch (err: unknown) {
      if (
        typeof err === "object" &&
        err !== null &&
        "response" in err &&
        typeof (err as { response?: { status?: number } }).response === "object"
      ) {
        const axiosErr = err as {
          response?: { status?: number; data?: { detail?: string } };
        };
        if (axiosErr.response?.status === 409) {
          setError("Er loopt al een sync. Even geduld.");
        } else {
          setError("Sync mislukt. Controleer de server logs.");
        }
      } else {
        setError("Sync mislukt. Controleer de server logs.");
      }
      console.error(err);
    } finally {
      setSyncing(false);
    }
  };

  const formatDate = (dateStr: string | null) => {
    if (!dateStr) return "Nooit";
    try {
      const date = new Date(dateStr);
      return date.toLocaleString("nl-NL", {
        day: "2-digit",
        month: "2-digit",
        year: "numeric",
        hour: "2-digit",
        minute: "2-digit",
      });
    } catch {
      return dateStr;
    }
  };

  const getStatusBadge = (status: string) => {
    switch (status) {
      case "success":
        return (
          <Badge className="bg-green-100 text-green-800 hover:bg-green-100">
            <CheckCircle className="h-3 w-3 mr-1" /> Gelukt
          </Badge>
        );
      case "no_changes":
        return (
          <Badge className="bg-blue-100 text-blue-800 hover:bg-blue-100">
            <Clock className="h-3 w-3 mr-1" /> Geen wijzigingen
          </Badge>
        );
      case "partial":
        return (
          <Badge className="bg-yellow-100 text-yellow-800 hover:bg-yellow-100">
            <AlertTriangle className="h-3 w-3 mr-1" /> Gedeeltelijk
          </Badge>
        );
      case "failed":
        return (
          <Badge variant="destructive">
            <XCircle className="h-3 w-3 mr-1" /> Mislukt
          </Badge>
        );
      default:
        return <Badge variant="secondary">{status}</Badge>;
    }
  };

  return (
    <Layout>
      <div className="px-4 sm:px-0">
        {/* Header */}
        <div className="flex flex-col sm:flex-row sm:justify-between sm:items-center gap-4 mb-6">
          <div>
            <h1 className="text-3xl font-bold text-gray-900">Content Sync</h1>
            <p className="mt-2 text-gray-600">
              Synchroniseer Notion inhoud naar de kennisbank
            </p>
          </div>
          <div className="flex gap-2">
            <Button
              variant="outline"
              onClick={loadData}
              disabled={loading || syncing}
            >
              <RefreshCw
                className={`h-4 w-4 mr-2 ${loading ? "animate-spin" : ""}`}
              />
              Vernieuwen
            </Button>
            <Button
              onClick={() => runSync(false)}
              disabled={syncing}
              className="bg-gray-900 hover:bg-gray-700 text-white"
            >
              {syncing ? (
                <>
                  <RefreshCw className="h-4 w-4 mr-2 animate-spin" />
                  Bezig met sync...
                </>
              ) : (
                <>
                  <Play className="h-4 w-4 mr-2" />
                  Sync Nu
                </>
              )}
            </Button>
          </div>
        </div>

        {error && (
          <Alert variant="destructive" className="mb-4">
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        )}

        {/* Sync Result Banner */}
        {syncResult && (
          <div
            className={`mb-6 rounded-lg p-4 ${
              syncResult.status === "success"
                ? "bg-green-50 border border-green-200"
                : syncResult.status === "no_changes"
                  ? "bg-blue-50 border border-blue-200"
                  : "bg-yellow-50 border border-yellow-200"
            }`}
          >
            <div className="flex items-center justify-between mb-2">
              <span className="font-semibold text-gray-900">Sync afgerond</span>
              {getStatusBadge(syncResult.status)}
            </div>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-sm">
              <div>
                <span className="text-gray-500">Bronnen gecontroleerd</span>
                <p className="font-medium">{syncResult.sources_checked}</p>
              </div>
              <div>
                <span className="text-gray-500">Pagina's gewijzigd</span>
                <p className="font-medium">{syncResult.total_pages_changed}</p>
              </div>
              <div>
                <span className="text-gray-500">Chunks bijgewerkt</span>
                <p className="font-medium">
                  {syncResult.total_chunks_upserted}
                </p>
              </div>
              <div>
                <span className="text-gray-500">Duur</span>
                <p className="font-medium">{syncResult.duration_seconds}s</p>
              </div>
            </div>

            {/* Per-source details */}
            {syncResult.source_details.length > 0 && (
              <div className="mt-3 space-y-1">
                {syncResult.source_details.map((sd) => (
                  <div
                    key={sd.source_key}
                    className="flex items-center justify-between text-sm bg-white/60 rounded px-3 py-1.5"
                  >
                    <span className="font-mono text-xs">{sd.source_key}</span>
                    <span className="text-gray-600">
                      {sd.pages_changed} pagina's → {sd.chunks_upserted} chunks
                    </span>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {loading ? (
          <div className="text-center py-12 text-gray-500">
            Bezig met laden...
          </div>
        ) : (
          <div className="space-y-6">
            {/* Source Status Cards */}
            <div className="bg-white shadow rounded-lg p-6">
              <h2 className="text-lg font-semibold text-gray-900 mb-4">
                Bronnen
              </h2>
              <div className="space-y-3">
                {Object.entries(sourceStatus).map(([key, source]) => (
                  <div
                    key={key}
                    className="flex items-center justify-between bg-gray-50 rounded-lg px-4 py-3"
                  >
                    <div>
                      <p className="font-medium text-gray-900">{source.name}</p>
                      <p className="text-xs text-gray-500 font-mono">
                        {source.namespace}
                      </p>
                    </div>
                    <div className="text-right">
                      <p className="text-sm text-gray-600">Laatste sync</p>
                      <p className="text-sm font-medium">
                        {formatDate(source.last_sync)}
                      </p>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* Sync History */}
            <div className="bg-white shadow rounded-lg p-6">
              <h2 className="text-lg font-semibold text-gray-900 mb-4">
                Sync Geschiedenis ({historyTotal})
              </h2>

              {history.length === 0 ? (
                <p className="text-gray-500 text-sm py-4">
                  Nog geen syncs uitgevoerd. Klik op "Sync Nu" om te beginnen.
                </p>
              ) : (
                <div className="space-y-3">
                  {history.map((entry) => (
                    <div
                      key={entry.id}
                      className="border border-gray-100 rounded-lg px-4 py-3"
                    >
                      <div className="flex items-center justify-between mb-2">
                        <div className="flex items-center gap-2">
                          {getStatusBadge(entry.status)}
                          <span className="text-xs text-gray-500">
                            {entry.trigger === "manual"
                              ? "Handmatig"
                              : "Automatisch"}
                          </span>
                        </div>
                        <span className="text-sm text-gray-500">
                          {formatDate(entry.completed_at)}
                        </span>
                      </div>
                      <div className="grid grid-cols-3 gap-2 text-xs text-gray-600">
                        <span>
                          {entry.total_pages_changed} pagina's gewijzigd
                        </span>
                        <span>{entry.total_chunks_upserted} chunks</span>
                        <span>{entry.duration_seconds}s</span>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </Layout>
  );
}
