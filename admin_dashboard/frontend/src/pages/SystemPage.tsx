import { useState, useEffect } from "react";
import Layout from "@/components/Layout";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { RefreshCw, CheckCircle, XCircle, Database, Cpu } from "lucide-react";
import { apiClient } from "@/lib/api";

interface PineconeStats {
  status: string;
  index_name: string;
  total_vectors: number;
  namespaces: Record<string, number>;
  dimension: number | null;
}

interface RedisStats {
  status: string;
  connected: boolean;
  error: string | null;
}

interface SystemConfig {
  llm_model: string;
  embedding_model: string;
  chunk_size: number;
  chunk_overlap: number;
  query_top_k: number;
  temperature: number;
  max_tokens: number;
}

interface SystemStatus {
  status: string;
  pinecone: PineconeStats;
  redis: RedisStats;
  config: SystemConfig;
  admin_backend_version: string;
}

export default function SystemPage() {
  const [status, setStatus] = useState<SystemStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [refreshing, setRefreshing] = useState(false);

  useEffect(() => {
    loadStatus();
  }, []);

  const loadStatus = async () => {
    try {
      setRefreshing(true);
      const response = await apiClient.get<SystemStatus>("/system/status");
      setStatus(response.data);
      setError("");
    } catch (err) {
      setError("Kon systeemstatus niet laden");
      console.error(err);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  const getStatusBadge = (s: string) => {
    if (s === "healthy")
      return (
        <Badge className="bg-green-100 text-green-800 hover:bg-green-100">
          <CheckCircle className="h-3 w-3 mr-1" /> Gezond
        </Badge>
      );
    if (s === "degraded")
      return (
        <Badge className="bg-yellow-100 text-yellow-800 hover:bg-yellow-100">
          Gedegradeerd
        </Badge>
      );
    if (s === "error")
      return (
        <Badge variant="destructive">
          <XCircle className="h-3 w-3 mr-1" /> Fout
        </Badge>
      );
    return <Badge variant="secondary">Onbekend</Badge>;
  };

  return (
    <Layout>
      <div>
        {/* Header */}
        <div className="flex flex-col sm:flex-row sm:justify-between sm:items-center gap-4 mb-6">
          <div>
            <h1 className="text-2xl sm:text-3xl font-bold text-gray-900">
              Systeem Status
            </h1>
            <p className="mt-1 text-sm text-gray-600">
              Pinecone, Redis en configuratie overzicht
            </p>
          </div>
          <Button
            variant="outline"
            onClick={loadStatus}
            disabled={refreshing}
            size="sm"
          >
            <RefreshCw
              className={`h-4 w-4 mr-2 ${refreshing ? "animate-spin" : ""}`}
            />
            Vernieuwen
          </Button>
        </div>

        {error && (
          <Alert variant="destructive" className="mb-4">
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        )}

        {loading ? (
          <div className="text-center py-12 text-gray-500">
            Bezig met laden...
          </div>
        ) : (
          status && (
            <div className="space-y-4 sm:space-y-6">
              {/* Overall status */}
              <div className="bg-white shadow rounded-lg p-4 sm:p-6">
                <div className="flex items-center justify-between">
                  <div>
                    <h2 className="text-base sm:text-lg font-semibold text-gray-900">
                      Algehele Status
                    </h2>
                    <p className="text-xs text-gray-400 mt-0.5">
                      Admin backend v{status.admin_backend_version}
                    </p>
                  </div>
                  {getStatusBadge(status.status)}
                </div>
              </div>

              {/* Pinecone */}
              <div className="bg-white shadow rounded-lg p-4 sm:p-6">
                {/* Pinecone header */}
                <div className="flex items-center justify-between mb-4">
                  <div className="flex items-center gap-2 min-w-0">
                    <Database className="h-5 w-5 text-gray-400 flex-shrink-0" />
                    <h2 className="text-base sm:text-lg font-semibold text-gray-900 truncate">
                      Pinecone
                    </h2>
                  </div>
                  {getStatusBadge(status.pinecone.status)}
                </div>

                {/* Pinecone stats */}
                <div className="grid grid-cols-3 gap-3 mb-4">
                  <div className="bg-gray-50 rounded-lg p-3">
                    <p className="text-xs text-gray-400">Index</p>
                    <p className="font-mono text-xs sm:text-sm font-medium mt-0.5 truncate">
                      {status.pinecone.index_name}
                    </p>
                  </div>
                  <div className="bg-gray-50 rounded-lg p-3">
                    <p className="text-xs text-gray-400">Vectors</p>
                    <p className="text-lg sm:text-xl font-bold text-gray-900 mt-0.5">
                      {status.pinecone.total_vectors.toLocaleString()}
                    </p>
                  </div>
                  <div className="bg-gray-50 rounded-lg p-3">
                    <p className="text-xs text-gray-400">Dimensies</p>
                    <p className="font-medium mt-0.5">
                      {status.pinecone.dimension ?? "—"}
                    </p>
                  </div>
                </div>

                {/* Namespaces */}
                <div>
                  <p className="text-xs font-medium text-gray-400 mb-2">
                    Namespaces
                  </p>
                  <div className="space-y-1.5">
                    {Object.entries(status.pinecone.namespaces).map(
                      ([ns, count]) => (
                        <div
                          key={ns}
                          className="flex items-center justify-between bg-gray-50 rounded-lg px-3 py-2"
                        >
                          <span className="font-mono text-xs sm:text-sm truncate mr-2">
                            {ns}
                          </span>
                          <span className="text-xs sm:text-sm font-medium text-gray-700 whitespace-nowrap">
                            {count.toLocaleString()}
                          </span>
                        </div>
                      ),
                    )}
                  </div>
                </div>
              </div>

              {/* Redis */}
              <div className="bg-white shadow rounded-lg p-4 sm:p-6">
                <div className="flex items-center justify-between mb-2">
                  <div className="flex items-center gap-2">
                    <Cpu className="h-5 w-5 text-gray-400 flex-shrink-0" />
                    <h2 className="text-base sm:text-lg font-semibold text-gray-900">
                      Redis
                    </h2>
                  </div>
                  {getStatusBadge(status.redis.status)}
                </div>
                <p className="text-sm text-gray-600">
                  {status.redis.connected
                    ? "Verbonden — gespreksgeheugen actief (30 min TTL)"
                    : `Niet verbonden: ${status.redis.error ?? "onbekende fout"}`}
                </p>
              </div>

              {/* Config */}
              <div className="bg-white shadow rounded-lg p-4 sm:p-6">
                <h2 className="text-base sm:text-lg font-semibold text-gray-900 mb-3">
                  Configuratie
                </h2>
                <div className="space-y-1.5">
                  {[
                    { label: "LLM Model", value: status.config.llm_model },
                    {
                      label: "Embedding",
                      value: status.config.embedding_model,
                    },
                    {
                      label: "Chunk Size",
                      value: status.config.chunk_size.toString(),
                    },
                    {
                      label: "Chunk Overlap",
                      value: status.config.chunk_overlap.toString(),
                    },
                    {
                      label: "Top-K",
                      value: status.config.query_top_k.toString(),
                    },
                    {
                      label: "Temperature",
                      value: status.config.temperature.toString(),
                    },
                    {
                      label: "Max Tokens",
                      value: status.config.max_tokens.toString(),
                    },
                  ].map(({ label, value }) => (
                    <div
                      key={label}
                      className="flex items-center justify-between bg-gray-50 rounded-lg px-3 py-2.5"
                    >
                      <span className="text-sm text-gray-500">{label}</span>
                      <span className="font-mono text-xs sm:text-sm font-medium text-gray-900 truncate ml-3 max-w-[55%] text-right">
                        {value}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )
        )}
      </div>
    </Layout>
  );
}
