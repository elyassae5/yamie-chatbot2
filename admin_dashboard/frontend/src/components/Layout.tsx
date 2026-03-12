import { Link, useLocation, useNavigate } from "react-router-dom";
import { logout, getCurrentUser } from "@/lib/auth";
import { Button } from "@/components/ui/button";
import {
  LayoutDashboard,
  Phone,
  FileText,
  Settings,
  LogOut,
} from "lucide-react";

interface LayoutProps {
  children: React.ReactNode;
}

export default function Layout({ children }: LayoutProps) {
  const location = useLocation();
  const navigate = useNavigate();
  const user = getCurrentUser();

  const handleLogout = () => {
    logout();
    navigate("/login");
  };

  const navItems = [
    { path: "/", icon: LayoutDashboard, label: "Dashboard" },
    { path: "/whitelist", icon: Phone, label: "Nummers" },
    { path: "/logs", icon: FileText, label: "Vragen" },
    { path: "/system", icon: Settings, label: "Systeem" },
  ];

  return (
    <div className="bg-gray-50">
      {/* Top Navigation Bar */}
      <nav className="bg-white border-b border-gray-200">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between h-16">
            <div className="flex">
              {/* Logo */}
              <div className="flex-shrink-0 flex items-center">
                <h1 className="text-xl font-bold text-gray-900">
                  YamieBot Admin
                </h1>
              </div>

              {/* Desktop Navigation Links */}
              <div className="hidden sm:ml-6 sm:flex sm:space-x-4">
                {navItems.map((item) => {
                  const Icon = item.icon;
                  const isActive = location.pathname === item.path;
                  return (
                    <Link
                      key={item.path}
                      to={item.path}
                      className={`inline-flex items-center px-3 py-2 text-sm font-medium rounded-md ${
                        isActive
                          ? "bg-gray-100 text-gray-900"
                          : "text-gray-600 hover:bg-gray-50 hover:text-gray-900"
                      }`}
                    >
                      <Icon className="h-4 w-4 mr-2" />
                      {item.label}
                    </Link>
                  );
                })}
              </div>
            </div>

            {/* User Menu - desktop only */}
            <div className="hidden sm:flex items-center space-x-4">
              <span className="text-sm text-gray-700">{user?.username}</span>
              <Button variant="outline" size="sm" onClick={handleLogout}>
                <LogOut className="h-4 w-4 mr-2" />
                Uitloggen
              </Button>
            </div>

            {/* Mobile: just show username */}
            <div className="flex sm:hidden items-center">
              <span className="text-sm text-gray-500">{user?.username}</span>
            </div>
          </div>
        </div>
      </nav>

      {/* Main Content - extra bottom padding on mobile for bottom nav */}
      <main className="max-w-7xl mx-auto py-6 px-4 sm:px-6 lg:px-8 pb-24 sm:pb-6 w-full">
        {children}
      </main>

      {/* Mobile Bottom Navigation */}
      <div className="fixed bottom-0 left-0 right-0 bg-white border-t border-gray-200 sm:hidden z-50">
        <div className="grid grid-cols-5 h-16">
          {navItems.map((item) => {
            const Icon = item.icon;
            const isActive = location.pathname === item.path;
            return (
              <Link
                key={item.path}
                to={item.path}
                className={`flex flex-col items-center justify-center space-y-1 text-xs font-medium ${
                  isActive ? "text-gray-900" : "text-gray-400"
                }`}
              >
                <Icon
                  className={`h-5 w-5 ${isActive ? "text-gray-900" : "text-gray-400"}`}
                />
                <span>{item.label}</span>
              </Link>
            );
          })}
          {/* Logout button in bottom nav */}
          <button
            onClick={handleLogout}
            className="flex flex-col items-center justify-center space-y-1 text-xs font-medium text-red-400"
          >
            <LogOut className="h-5 w-5" />
            <span>Uitloggen</span>
          </button>
        </div>
      </div>
    </div>
  );
}
