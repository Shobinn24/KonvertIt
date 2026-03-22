import { useState, useEffect } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  Users,
  AlertTriangle,
  ArrowRightLeft,
  List,
  ShieldCheck,
  UserPlus,
  ChevronLeft,
  ChevronRight,
  Search,
  X,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import {
  Table,
  TableHeader,
  TableBody,
  TableRow,
  TableHead,
  TableCell,
} from "@/components/ui/table";
import { LoadingSpinner } from "@/components/shared/LoadingSpinner";
import {
  getAdminKey,
  setAdminKey,
  validateAdminKey,
  getAdminStats,
  getAdminUsers,
  getAdminErrors,
  getAdminUserDetail,
} from "@/services/adminService";

// ─── Admin Login Gate ───────────────────────────────────────

function AdminLoginGate({ onAuth }: { onAuth: () => void }) {
  const [key, setKey] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError("");
    const valid = await validateAdminKey(key);
    if (valid) {
      setAdminKey(key);
      onAuth();
    } else {
      setError("Invalid admin key");
    }
    setLoading(false);
  };

  return (
    <div className="flex min-h-screen items-center justify-center bg-background p-4">
      <form
        onSubmit={handleSubmit}
        className="w-full max-w-sm space-y-4 rounded-xl border bg-card p-8 shadow-lg"
      >
        <h1 className="text-xl font-bold">Admin Access</h1>
        <p className="text-sm text-muted-foreground">Enter your admin key to continue.</p>
        <Input
          type="password"
          placeholder="Admin key"
          value={key}
          onChange={(e) => setKey(e.target.value)}
          autoFocus
        />
        {error && <p className="text-sm text-destructive">{error}</p>}
        <Button type="submit" className="w-full" disabled={loading || !key}>
          {loading ? <LoadingSpinner size={16} className="mr-2" /> : null}
          Authenticate
        </Button>
      </form>
    </div>
  );
}

// ─── Stat Card ──────────────────────────────────────────────

function StatCard({
  title,
  value,
  icon: Icon,
  description,
}: {
  title: string;
  value: number | string;
  icon: React.ElementType;
  description?: string;
}) {
  return (
    <div className="rounded-xl border bg-card p-5">
      <div className="flex items-center justify-between">
        <p className="text-sm text-muted-foreground">{title}</p>
        <Icon className="h-4 w-4 text-muted-foreground" />
      </div>
      <p className="mt-2 text-2xl font-bold">{value}</p>
      {description && (
        <p className="mt-1 text-xs text-muted-foreground">{description}</p>
      )}
    </div>
  );
}

// ─── Users Tab ──────────────────────────────────────────────

function UsersTab({ onSelectUser }: { onSelectUser: (id: string) => void }) {
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");
  const [searchInput, setSearchInput] = useState("");
  const [tierFilter, setTierFilter] = useState("");

  const { data, isLoading } = useQuery({
    queryKey: ["admin-users", page, search, tierFilter],
    queryFn: () =>
      getAdminUsers({ page, page_size: 25, search, tier: tierFilter }),
    staleTime: 10_000,
  });

  const totalPages = data ? Math.ceil(data.total / data.page_size) : 1;

  const tierBadge = (tier: string) => {
    const colors: Record<string, string> = {
      free: "bg-zinc-700 text-zinc-300",
      pro: "bg-blue-900/50 text-blue-400",
      enterprise: "bg-purple-900/50 text-purple-400",
    };
    return (
      <Badge className={`text-xs capitalize ${colors[tier] ?? ""}`}>{tier}</Badge>
    );
  };

  return (
    <div className="space-y-4">
      {/* Search & filter bar */}
      <div className="flex items-center gap-3">
        <form
          className="relative flex-1"
          onSubmit={(e) => {
            e.preventDefault();
            setSearch(searchInput);
            setPage(1);
          }}
        >
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            placeholder="Search by email or name..."
            className="pl-9"
            value={searchInput}
            onChange={(e) => setSearchInput(e.target.value)}
          />
          {search && (
            <button
              type="button"
              className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
              onClick={() => {
                setSearch("");
                setSearchInput("");
                setPage(1);
              }}
            >
              <X className="h-4 w-4" />
            </button>
          )}
        </form>
        <select
          className="rounded-lg border bg-card px-3 py-2 text-sm"
          value={tierFilter}
          onChange={(e) => {
            setTierFilter(e.target.value);
            setPage(1);
          }}
        >
          <option value="">All tiers</option>
          <option value="free">Free</option>
          <option value="pro">Pro</option>
          <option value="enterprise">Enterprise</option>
        </select>
      </div>

      {isLoading ? (
        <div className="flex justify-center py-12">
          <LoadingSpinner size={24} />
        </div>
      ) : (
        <>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>User</TableHead>
                <TableHead>Tier</TableHead>
                <TableHead>Verified</TableHead>
                <TableHead className="text-right">Conversions</TableHead>
                <TableHead className="text-right">Listings</TableHead>
                <TableHead>Joined</TableHead>
                <TableHead>Last Login</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {data?.users.map((u) => (
                <TableRow
                  key={u.id}
                  className="cursor-pointer"
                  onClick={() => onSelectUser(u.id)}
                >
                  <TableCell>
                    <div>
                      <p className="font-medium">
                        {u.first_name} {u.last_name}
                      </p>
                      <p className="text-xs text-muted-foreground">{u.email}</p>
                    </div>
                  </TableCell>
                  <TableCell>{tierBadge(u.tier)}</TableCell>
                  <TableCell>
                    {u.email_verified ? (
                      <ShieldCheck className="h-4 w-4 text-green-500" />
                    ) : (
                      <span className="text-xs text-muted-foreground">No</span>
                    )}
                  </TableCell>
                  <TableCell className="text-right">{u.conversion_count}</TableCell>
                  <TableCell className="text-right">{u.listing_count}</TableCell>
                  <TableCell className="text-xs text-muted-foreground">
                    {u.created_at ? new Date(u.created_at).toLocaleDateString() : "—"}
                  </TableCell>
                  <TableCell className="text-xs text-muted-foreground">
                    {u.last_login ? new Date(u.last_login).toLocaleDateString() : "Never"}
                  </TableCell>
                </TableRow>
              ))}
              {data?.users.length === 0 && (
                <TableRow>
                  <TableCell colSpan={7} className="py-8 text-center text-muted-foreground">
                    No users found.
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>

          {/* Pagination */}
          <div className="flex items-center justify-between text-sm text-muted-foreground">
            <span>
              {data?.total ?? 0} users total
            </span>
            <div className="flex items-center gap-2">
              <Button
                variant="outline"
                size="sm"
                disabled={page <= 1}
                onClick={() => setPage((p) => p - 1)}
              >
                <ChevronLeft className="h-4 w-4" />
              </Button>
              <span>
                Page {page} of {totalPages}
              </span>
              <Button
                variant="outline"
                size="sm"
                disabled={page >= totalPages}
                onClick={() => setPage((p) => p + 1)}
              >
                <ChevronRight className="h-4 w-4" />
              </Button>
            </div>
          </div>
        </>
      )}
    </div>
  );
}

// ─── User Detail Panel ──────────────────────────────────────

function UserDetailPanel({
  userId,
  onBack,
}: {
  userId: string;
  onBack: () => void;
}) {
  const { data, isLoading } = useQuery({
    queryKey: ["admin-user", userId],
    queryFn: () => getAdminUserDetail(userId),
  });

  if (isLoading) {
    return (
      <div className="flex justify-center py-12">
        <LoadingSpinner size={24} />
      </div>
    );
  }

  if (!data) return null;

  return (
    <div className="space-y-6">
      <Button variant="ghost" size="sm" onClick={onBack}>
        <ChevronLeft className="mr-1 h-4 w-4" /> Back to users
      </Button>

      {/* User info grid */}
      <div className="grid gap-4 md:grid-cols-2">
        <div className="space-y-3 rounded-xl border bg-card p-5">
          <h3 className="text-sm font-semibold text-muted-foreground">Profile</h3>
          <div className="space-y-1 text-sm">
            <p>
              <span className="text-muted-foreground">Name:</span>{" "}
              {data.first_name} {data.last_name}
            </p>
            <p>
              <span className="text-muted-foreground">Email:</span> {data.email}
            </p>
            <p>
              <span className="text-muted-foreground">Verified:</span>{" "}
              {data.email_verified ? "Yes" : "No"}
            </p>
            <p>
              <span className="text-muted-foreground">Tier:</span>{" "}
              <span className="capitalize">{data.tier}</span>
            </p>
            <p>
              <span className="text-muted-foreground">Active:</span>{" "}
              {data.is_active ? "Yes" : "No"}
            </p>
          </div>
        </div>

        <div className="space-y-3 rounded-xl border bg-card p-5">
          <h3 className="text-sm font-semibold text-muted-foreground">Details</h3>
          <div className="space-y-1 text-sm">
            <p>
              <span className="text-muted-foreground">Location:</span>{" "}
              {[data.city, data.state, data.country].filter(Boolean).join(", ") || "—"}
            </p>
            <p>
              <span className="text-muted-foreground">Joined:</span>{" "}
              {data.created_at ? new Date(data.created_at).toLocaleString() : "—"}
            </p>
            <p>
              <span className="text-muted-foreground">Last login:</span>{" "}
              {data.last_login ? new Date(data.last_login).toLocaleString() : "Never"}
            </p>
            <p>
              <span className="text-muted-foreground">Stripe ID:</span>{" "}
              {data.stripe_customer_id || "—"}
            </p>
            <p>
              <span className="text-muted-foreground">Conversions:</span>{" "}
              {data.conversion_count}
            </p>
            <p>
              <span className="text-muted-foreground">Listings:</span>{" "}
              {data.listing_count}
            </p>
          </div>
        </div>
      </div>

      {/* User's recent errors */}
      <div>
        <h3 className="mb-3 text-sm font-semibold">
          Recent Errors ({data.recent_errors.length})
        </h3>
        {data.recent_errors.length > 0 ? (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Error</TableHead>
                <TableHead>Source URL</TableHead>
                <TableHead>Time</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {data.recent_errors.map((err) => (
                <TableRow key={err.id}>
                  <TableCell className="max-w-xs">
                    <p className="truncate text-sm text-destructive">
                      {err.error_message}
                    </p>
                  </TableCell>
                  <TableCell className="max-w-xs">
                    <p className="truncate text-xs text-muted-foreground">
                      {err.source_url}
                    </p>
                  </TableCell>
                  <TableCell className="whitespace-nowrap text-xs text-muted-foreground">
                    {err.created_at ? new Date(err.created_at).toLocaleString() : "—"}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        ) : (
          <p className="rounded-lg border border-dashed p-6 text-center text-sm text-muted-foreground">
            No errors found for this user.
          </p>
        )}
      </div>
    </div>
  );
}

// ─── Errors Tab ─────────────────────────────────────────────

function ErrorsTab() {
  const [page, setPage] = useState(1);

  const { data, isLoading } = useQuery({
    queryKey: ["admin-errors", page],
    queryFn: () => getAdminErrors({ page, page_size: 25 }),
    staleTime: 10_000,
  });

  const totalPages = data ? Math.ceil(data.total / data.page_size) : 1;

  return (
    <div className="space-y-4">
      {isLoading ? (
        <div className="flex justify-center py-12">
          <LoadingSpinner size={24} />
        </div>
      ) : (
        <>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>User</TableHead>
                <TableHead>Error</TableHead>
                <TableHead>Source URL</TableHead>
                <TableHead>Time</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {data?.errors.map((err) => (
                <TableRow key={err.id}>
                  <TableCell className="whitespace-nowrap text-sm">
                    {err.user_email}
                  </TableCell>
                  <TableCell className="max-w-sm">
                    <p className="truncate text-sm text-destructive">
                      {err.error_message}
                    </p>
                  </TableCell>
                  <TableCell className="max-w-xs">
                    <p className="truncate text-xs text-muted-foreground">
                      {err.source_url}
                    </p>
                  </TableCell>
                  <TableCell className="whitespace-nowrap text-xs text-muted-foreground">
                    {err.created_at
                      ? new Date(err.created_at).toLocaleString()
                      : "—"}
                  </TableCell>
                </TableRow>
              ))}
              {data?.errors.length === 0 && (
                <TableRow>
                  <TableCell colSpan={4} className="py-8 text-center text-muted-foreground">
                    No errors found.
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>

          <div className="flex items-center justify-between text-sm text-muted-foreground">
            <span>{data?.total ?? 0} errors total</span>
            <div className="flex items-center gap-2">
              <Button
                variant="outline"
                size="sm"
                disabled={page <= 1}
                onClick={() => setPage((p) => p - 1)}
              >
                <ChevronLeft className="h-4 w-4" />
              </Button>
              <span>
                Page {page} of {totalPages}
              </span>
              <Button
                variant="outline"
                size="sm"
                disabled={page >= totalPages}
                onClick={() => setPage((p) => p + 1)}
              >
                <ChevronRight className="h-4 w-4" />
              </Button>
            </div>
          </div>
        </>
      )}
    </div>
  );
}

// ─── Main Admin Page ────────────────────────────────────────

export function AdminPage() {
  const [authed, setAuthed] = useState(false);
  const [activeTab, setActiveTab] = useState<"overview" | "users" | "errors">("overview");
  const [selectedUserId, setSelectedUserId] = useState<string | null>(null);

  // Check for existing admin key on mount
  useEffect(() => {
    const key = getAdminKey();
    if (key) {
      validateAdminKey(key).then((valid) => {
        if (valid) setAuthed(true);
      });
    }
  }, []);

  if (!authed) {
    return <AdminLoginGate onAuth={() => setAuthed(true)} />;
  }

  const tabs = [
    { key: "overview" as const, label: "Overview" },
    { key: "users" as const, label: "Users" },
    { key: "errors" as const, label: "Errors" },
  ];

  return (
    <div className="min-h-screen bg-background">
      {/* Top header */}
      <header className="flex h-16 items-center justify-between border-b bg-card px-6">
        <div className="flex items-center gap-3">
          <ShieldCheck className="h-5 w-5 text-accentPurple" />
          <h1 className="text-lg font-semibold">Admin Dashboard</h1>
        </div>
        <Button
          variant="ghost"
          size="sm"
          onClick={() => {
            sessionStorage.removeItem("konvertit_admin_key");
            setAuthed(false);
          }}
        >
          Lock
        </Button>
      </header>

      {/* Tabs */}
      <div className="border-b bg-card px-6">
        <div className="flex gap-1">
          {tabs.map((tab) => (
            <button
              key={tab.key}
              className={`border-b-2 px-4 py-3 text-sm font-medium transition-colors ${
                activeTab === tab.key
                  ? "border-accentPurple text-foreground"
                  : "border-transparent text-muted-foreground hover:text-foreground"
              }`}
              onClick={() => {
                setActiveTab(tab.key);
                setSelectedUserId(null);
              }}
            >
              {tab.label}
            </button>
          ))}
        </div>
      </div>

      {/* Content */}
      <div className="mx-auto max-w-7xl p-6">
        {activeTab === "overview" && <OverviewTab />}
        {activeTab === "users" && !selectedUserId && (
          <UsersTab onSelectUser={(id) => setSelectedUserId(id)} />
        )}
        {activeTab === "users" && selectedUserId && (
          <UserDetailPanel
            userId={selectedUserId}
            onBack={() => setSelectedUserId(null)}
          />
        )}
        {activeTab === "errors" && <ErrorsTab />}
      </div>
    </div>
  );
}

// ─── Overview Tab ───────────────────────────────────────────

function OverviewTab() {
  const { data, isLoading } = useQuery({
    queryKey: ["admin-stats"],
    queryFn: getAdminStats,
    staleTime: 15_000,
  });

  if (isLoading) {
    return (
      <div className="flex justify-center py-12">
        <LoadingSpinner size={24} />
      </div>
    );
  }

  if (!data) return null;

  return (
    <div className="space-y-6">
      {/* Main stats */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard
          title="Total Users"
          value={data.total_users}
          icon={Users}
          description={`${data.active_users} active, ${data.verified_users} verified`}
        />
        <StatCard
          title="New Users Today"
          value={data.new_users_today}
          icon={UserPlus}
          description={`${data.new_users_this_week} this week`}
        />
        <StatCard
          title="Total Conversions"
          value={data.total_conversions}
          icon={ArrowRightLeft}
          description={`${data.conversions_today} today`}
        />
        <StatCard
          title="Failed Conversions"
          value={data.failed_conversions}
          icon={AlertTriangle}
          description="All time"
        />
      </div>

      {/* Secondary stats */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        <StatCard
          title="Total Listings"
          value={data.total_listings}
          icon={List}
          description={`${data.active_listings} active`}
        />
        <div className="rounded-xl border bg-card p-5">
          <p className="text-sm text-muted-foreground">Users by Tier</p>
          <div className="mt-3 space-y-2">
            {Object.entries(data.users_by_tier).map(([tier, count]) => (
              <div key={tier} className="flex items-center justify-between text-sm">
                <span className="capitalize">{tier}</span>
                <span className="font-medium">{count}</span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
