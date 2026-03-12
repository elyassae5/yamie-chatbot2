import { useState, useEffect } from "react";
import Layout from "@/components/Layout";
import { MessageSquare, Phone, Activity } from "lucide-react";
import { apiClient } from "@/lib/api";

interface DashboardStats {
  totalQueries: number;
  whitelistedNumbers: number;
  queriesToday: number;
}

export default function DashboardPage() {
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadStats();
  }, []);

  const loadStats = async () => {
    try {
      const [logsRes, whitelistRes] = await Promise.all([
        apiClient.get("/logs/stats/summary"),
        apiClient.get("/whitelist/"),
      ]);
      setStats({
        totalQueries: logsRes.data.total_queries,
        whitelistedNumbers: whitelistRes.data.length,
        queriesToday: logsRes.data.queries_today,
      });
    } catch (err) {
      console.error("Failed to load dashboard stats:", err);
    } finally {
      setLoading(false);
    }
  };

  const cards = stats
    ? [
        {
          label: "Totale Vragen",
          value: stats.totalQueries.toLocaleString(),
          icon: MessageSquare,
          color: "text-blue-600",
          bg: "bg-blue-50",
        },
        {
          label: "Whitelisted Nummers",
          value: stats.whitelistedNumbers.toString(),
          icon: Phone,
          color: "text-purple-600",
          bg: "bg-purple-50",
        },
        {
          label: "Vragen Vandaag",
          value: stats.queriesToday.toString(),
          icon: Activity,
          color: "text-orange-600",
          bg: "bg-orange-50",
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

        <div className="mt-6 grid grid-cols-1 gap-4 sm:grid-cols-3">
          {loading
            ? Array.from({ length: 3 }).map((_, i) => (
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
            : cards.map(({ label, value, icon: Icon, color, bg }) => (
                <div
                  key={label}
                  className="bg-white overflow-hidden shadow rounded-lg"
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
      </div>
    </Layout>
  );
}
