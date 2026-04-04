import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import Layout from "@/components/Layout";
import {
  MessageSquare,
  Phone,
  Activity,
  CircleCheck,
  CircleAlert,
  CircleX,
  Clock,
  ArrowRight,
  Users,
  FileText,
  RefreshCw,
  Settings,
} from "lucide-react";
import { apiClient } from "@/lib/api";

interface DashboardStats {
  totalQueries: number;
  whitelistedNumbers: number;
  queriesToday: number;
  botStatus: "healthy" | "degraded" | "unhealthy" | "loading";
}

interface RecentQuestion {
  id: string;
  question: string;
  user_id: string | null;
  created_at: string;
  has_answer: boolean;
}

export default function DashboardPage() {
  const navigate = useNavigate();
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [recentQuestions, setRecentQuestions] = useState<RecentQuestion[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadStats();
  }, []);

  const loadStats = async () => {
    try {
      const [logsRes, whitelistRes, systemRes, recentRes] = await Promise.all([
        apiClient.get("/logs/stats/summary"),
        apiClient.get("/whitelist/"),
        apiClient.get("/system/status").catch(() => ({ data: { status: "unhealthy" } })),
        apiClient.get("/logs/", { params: { page: 1, page_size: 5 } }),
      ]);
      setStats({
        totalQueries: logsRes.data.total_queries,
        whitelistedNumbers: whitelistRes.data.length,
        queriesToday: logsRes.data.queries_today,
        botStatus: systemRes.data.status,
      });
      setRecentQuestions(recentRes.data.logs || []);
    } catch (err) {
      console.error("Failed to load dashboard stats:", err);
    } finally {
      setLoading(false);
    }
  };

  const formatTimeAgo = (dateStr: string) => {
    const now = new Date();
    const date = new Date(dateStr);
    const diffMs = now.getTime() - date.getTime();
    const diffMins = Math.floor(diffMs / 60000);
    const diffHours = Math.floor(diffMins / 60);
    const diffDays = Math.floor(diffHours / 24);

    if (diffMins < 1) return "Zojuist";
    if (diffMins < 60) return `${diffMins} min geleden`;
    if (diffHours < 24) return `${diffHours} uur geleden`;
    if (diffDays === 1) return "Gisteren";
    if (diffDays < 7) return `${diffDays} dagen geleden`;
    return date.toLocaleDateString("nl-NL");
  };

  const cards = stats
    ? [
        {
          label: "Totale Vragen",
          value: stats.totalQueries.toLocaleString(),
          icon: MessageSquare,
          color: "text-blue-600",
          bg: "bg-blue-50",
          link: "/logs",
        },
        {
          label: "Whitelisted Nummers",
          value: stats.whitelistedNumbers.toString(),
          icon: Phone,
          color: "text-purple-600",
          bg: "bg-purple-50",
          link: "/whitelist",
        },
        {
          label: "Vragen Vandaag",
          value: stats.queriesToday.toString(),
          icon: Activity,
          color: "text-orange-600",
          bg: "bg-orange-50",
          link: "/logs",
        },
        {
          label: "Bot Status",
          value: stats.botStatus === "healthy" ? "Actief" : stats.botStatus === "degraded" ? "Beperkt" : "Offline",
          icon: stats.botStatus === "healthy" ? CircleCheck : stats.botStatus === "degraded" ? CircleAlert : CircleX,
          color: stats.botStatus === "healthy" ? "text-green-600" : stats.botStatus === "degraded" ? "text-yellow-600" : "text-red-600",
          bg: stats.botStatus === "healthy" ? "bg-green-50" : stats.botStatus === "degraded" ? "bg-yellow-50" : "bg-red-50",
          link: "/system",
        },
      ]
    : [];

  return (
    <Layout>
      <div>
        <h1 className="text-2xl sm:text-3xl font-bold text-gray-900">
          Dashboard
        </h1>
        <p className="mt-1 text-sm text-gray-600">
          Welkom bij het YamieBot admin dashboard
        </p>

        {/* Stat Cards */}
        <div className="mt-6 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {loading
            ? Array.from({ length: 4 }).map((_, i) => (
                <div
                  key={i}
                  className="bg-white shadow rounded-lg p-5 animate-pulse"
                >
                  <div className="flex items-center gap-4">
                    <div className="w-12 h-12 bg-gray-200 rounded-md flex-shrink-0" />
                    <div className="flex-1">
                      <div className="h-3 bg-gray-200 rounded w-24 mb-3" />
                      <div className="h-7 bg-gray-200 rounded w-16" />
                    </div>
                  </div>
                </div>
              ))
            : cards.map(({ label, value, icon: Icon, color, bg, link }) => (
                <div
                  key={label}
                  onClick={() => navigate(link)}
                  className="bg-white overflow-hidden shadow rounded-lg cursor-pointer transition-shadow hover:shadow-md"
                >
                  <div className="p-5">
                    <div className="flex items-center">
                      <div className={`flex-shrink-0 ${bg} rounded-md p-3`}>
                        <Icon className={`h-6 w-6 ${color}`} />
                      </div>
                      <div className="ml-5 w-0 flex-1">
                        <dl>
                          <dt className="text-sm font-medium text-gray-500 truncate">
                            {label}
                          </dt>
                          <dd className={`text-2xl font-bold ${color}`}>
                            {value}
                          </dd>
                        </dl>
                      </div>
                    </div>
                  </div>
                </div>
              ))}
        </div>

        {/* Two-column layout: Recent Questions + Quick Guide */}
        <div className="mt-8 grid grid-cols-1 gap-6 lg:grid-cols-3">
          {/* Laatste Vragen — takes 2/3 */}
          <div className="lg:col-span-2 bg-white shadow rounded-lg overflow-hidden">
            <div className="flex items-center justify-between px-5 py-4 border-b border-gray-100">
              <h2 className="text-base font-semibold text-gray-900">Laatste Vragen</h2>
              <button
                onClick={() => navigate("/logs")}
                className="text-sm text-blue-600 hover:text-blue-800 flex items-center gap-1 transition-colors"
              >
                Alles bekijken <ArrowRight className="h-3.5 w-3.5" />
              </button>
            </div>
            {loading ? (
              <div className="p-5 space-y-4">
                {Array.from({ length: 5 }).map((_, i) => (
                  <div key={i} className="animate-pulse flex items-start gap-3">
                    <div className="w-8 h-8 bg-gray-200 rounded-full flex-shrink-0" />
                    <div className="flex-1">
                      <div className="h-4 bg-gray-200 rounded w-3/4 mb-2" />
                      <div className="h-3 bg-gray-200 rounded w-1/4" />
                    </div>
                  </div>
                ))}
              </div>
            ) : recentQuestions.length === 0 ? (
              <div className="p-8 text-center text-gray-400 text-sm">
                Nog geen vragen gesteld
              </div>
            ) : (
              <ul className="divide-y divide-gray-50">
                {recentQuestions.map((q) => (
                  <li
                    key={q.id}
                    onClick={() => navigate("/logs")}
                    className="px-5 py-3.5 hover:bg-gray-50 cursor-pointer transition-colors"
                  >
                    <div className="flex items-start gap-3">
                      <div className={`mt-0.5 flex-shrink-0 w-2 h-2 rounded-full ${q.has_answer ? "bg-green-400" : "bg-red-400"}`} />
                      <div className="flex-1 min-w-0">
                        <p className="text-sm text-gray-900 truncate">
                          {q.question}
                        </p>
                        <div className="flex items-center gap-2 mt-1">
                          <Clock className="h-3 w-3 text-gray-300" />
                          <span className="text-xs text-gray-400">
                            {formatTimeAgo(q.created_at)}
                          </span>
                          {q.user_id && (
                            <span className="text-xs text-gray-300">
                              · {q.user_id.replace("whatsapp:", "")}
                            </span>
                          )}
                        </div>
                      </div>
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </div>

          {/* Snelgids — takes 1/3 */}
          <div className="bg-white shadow rounded-lg overflow-hidden">
            <div className="px-5 py-4 border-b border-gray-100">
              <h2 className="text-base font-semibold text-gray-900">Snelgids</h2>
            </div>
            <nav className="p-3">
              {[
                {
                  icon: Users,
                  label: "Nummers",
                  description: "Beheer wie de bot mag gebruiken",
                  link: "/whitelist",
                  color: "text-purple-600",
                  bg: "bg-purple-50",
                },
                {
                  icon: FileText,
                  label: "Vragen",
                  description: "Bekijk alle gestelde vragen en antwoorden",
                  link: "/logs",
                  color: "text-blue-600",
                  bg: "bg-blue-50",
                },
                {
                  icon: RefreshCw,
                  label: "Sync",
                  description: "Synchroniseer Notion content met de bot",
                  link: "/sync",
                  color: "text-orange-600",
                  bg: "bg-orange-50",
                },
                {
                  icon: Settings,
                  label: "Systeem",
                  description: "Bekijk de status van alle systemen",
                  link: "/system",
                  color: "text-gray-600",
                  bg: "bg-gray-100",
                },
              ].map((item) => (
                <button
                  key={item.label}
                  onClick={() => navigate(item.link)}
                  className="w-full flex items-center gap-3 px-3 py-3 rounded-lg hover:bg-gray-50 transition-colors text-left"
                >
                  <div className={`flex-shrink-0 ${item.bg} rounded-md p-2`}>
                    <item.icon className={`h-4 w-4 ${item.color}`} />
                  </div>
                  <div className="min-w-0">
                    <p className="text-sm font-medium text-gray-900">{item.label}</p>
                    <p className="text-xs text-gray-400">{item.description}</p>
                  </div>
                </button>
              ))}
            </nav>
          </div>
        </div>
      </div>
    </Layout>
  );
}
