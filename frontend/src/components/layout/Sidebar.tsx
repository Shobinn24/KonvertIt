import { useState } from "react";
import { Link, NavLink } from "react-router-dom";
import {
  LayoutDashboard,
  Search,
  Sparkles,
  ArrowRightLeft,
  List,
  Settings,
  HelpCircle,
  LogOut,
  ChevronLeft,
  ChevronRight,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { useAuthContext } from "@/contexts/AuthContext";
import { useLogout } from "@/hooks/useAuth";
import { cn } from "@/lib/utils";

const navItems = [
  { to: "/dashboard", icon: LayoutDashboard, label: "Dashboard" },
  { to: "/discover", icon: Search, label: "Discover" },
  { to: "/auto-discover", icon: Sparkles, label: "Auto-Discover" },
  { to: "/convert", icon: ArrowRightLeft, label: "Convert" },
  { to: "/listings", icon: List, label: "Listings" },
  { to: "/settings", icon: Settings, label: "Settings" },
  { to: "/help", icon: HelpCircle, label: "Help" },
];

const tierColors: Record<string, string> = {
  free: "bg-darkBorder text-gray-300",
  pro: "bg-accentBlue/20 text-accentBlue",
  enterprise: "bg-accentPurple/20 text-accentPurple",
};

export function Sidebar() {
  const { user } = useAuthContext();
  const logout = useLogout();

  const [collapsed, setCollapsed] = useState(() => {
    try {
      return localStorage.getItem("sidebar_collapsed") === "true";
    } catch {
      return false;
    }
  });

  const toggle = () => {
    const next = !collapsed;
    setCollapsed(next);
    try {
      localStorage.setItem("sidebar_collapsed", String(next));
    } catch {
      // ignore
    }
  };

  return (
    <aside
      className={cn(
        "sidebar-glass flex h-screen flex-col transition-all duration-200",
        collapsed ? "w-16" : "w-64",
      )}
    >
      {/* Logo + collapse toggle */}
      <div className={cn("flex h-16 items-center", collapsed ? "justify-center px-0" : "justify-between px-5")}>
        {!collapsed && (
          <Link to="/">
            <img src="/logo.jpg" alt="KonvertIt" className="h-9 w-auto" />
          </Link>
        )}
        <button
          onClick={toggle}
          className={cn(
            "flex h-8 w-8 items-center justify-center rounded-md text-muted-foreground transition-colors hover:bg-darkBorder/50 hover:text-foreground",
            collapsed && "mx-auto",
          )}
          aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
        >
          {collapsed ? (
            <ChevronRight className="h-4 w-4" />
          ) : (
            <ChevronLeft className="h-4 w-4" />
          )}
        </button>
      </div>

      <div className="mx-4 h-px bg-darkBorder" />

      {/* Navigation */}
      <nav className={cn("flex-1 space-y-1 py-4", collapsed ? "px-2" : "px-3")}>
        {navItems.map(({ to, icon: Icon, label }) => (
          <NavLink
            key={to}
            to={to}
            end={to === "/dashboard"}
            title={collapsed ? label : undefined}
            className={({ isActive }) =>
              cn(
                "flex items-center rounded-lg py-2.5 text-sm font-medium transition-all",
                collapsed ? "justify-center px-0" : "gap-3 px-3",
                isActive
                  ? "bg-accentPurple/15 text-accentPurple"
                  : "text-muted-foreground hover:bg-darkBorder/50 hover:text-foreground",
              )
            }
          >
            <Icon className="h-4 w-4 shrink-0" />
            {!collapsed && label}
          </NavLink>
        ))}
      </nav>

      <div className="mx-4 h-px bg-darkBorder" />

      {/* User info */}
      <div className={cn("p-4", collapsed && "px-2")}>
        {user && (
          <div className="space-y-3">
            {!collapsed && (
              <div className="flex items-center gap-2">
                <div className="min-w-0 flex-1">
                  <p className="truncate text-sm font-medium text-foreground">
                    {user.email}
                  </p>
                </div>
                <Badge
                  variant="secondary"
                  className={cn("text-xs capitalize", tierColors[user.tier])}
                >
                  {user.tier}
                </Badge>
              </div>
            )}
            <Button
              variant="ghost"
              size="sm"
              title={collapsed ? "Log out" : undefined}
              className={cn(
                "text-muted-foreground hover:bg-darkBorder/50 hover:text-foreground",
                collapsed
                  ? "w-full justify-center px-0"
                  : "w-full justify-start gap-2",
              )}
              onClick={logout}
            >
              <LogOut className="h-4 w-4 shrink-0" />
              {!collapsed && "Log out"}
            </Button>
          </div>
        )}
      </div>
    </aside>
  );
}
