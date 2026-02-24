import { Link, NavLink } from "react-router-dom";
import {
  LayoutDashboard,
  Search,
  ArrowRightLeft,
  List,
  Settings,
  HelpCircle,
  LogOut,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { useAuthContext } from "@/contexts/AuthContext";
import { useLogout } from "@/hooks/useAuth";
import { cn } from "@/lib/utils";

const navItems = [
  { to: "/dashboard", icon: LayoutDashboard, label: "Dashboard" },
  { to: "/discover", icon: Search, label: "Discover" },
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

  return (
    <aside className="sidebar-glass flex h-screen w-64 flex-col">
      {/* Logo */}
      <div className="flex h-16 items-center px-5">
        <Link to="/">
          <img src="/logo.jpg" alt="KonvertIt" className="h-9 w-auto" />
        </Link>
      </div>

      <div className="mx-4 h-px bg-darkBorder" />

      {/* Navigation */}
      <nav className="flex-1 space-y-1 px-3 py-4">
        {navItems.map(({ to, icon: Icon, label }) => (
          <NavLink
            key={to}
            to={to}
            end={to === "/dashboard"}
            className={({ isActive }) =>
              cn(
                "flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-all",
                isActive
                  ? "bg-accentPurple/15 text-accentPurple"
                  : "text-muted-foreground hover:bg-darkBorder/50 hover:text-foreground",
              )
            }
          >
            <Icon className="h-4 w-4" />
            {label}
          </NavLink>
        ))}
      </nav>

      <div className="mx-4 h-px bg-darkBorder" />

      {/* User info */}
      <div className="p-4">
        {user && (
          <div className="space-y-3">
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
            <Button
              variant="ghost"
              size="sm"
              className="w-full justify-start gap-2 text-muted-foreground hover:bg-darkBorder/50 hover:text-foreground"
              onClick={logout}
            >
              <LogOut className="h-4 w-4" />
              Log out
            </Button>
          </div>
        )}
      </div>
    </aside>
  );
}
