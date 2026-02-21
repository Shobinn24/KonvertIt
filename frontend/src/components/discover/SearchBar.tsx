import { useState } from "react";
import { Search, Loader2 } from "lucide-react";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

interface SearchBarProps {
  onSearch: (query: string, marketplace: "amazon" | "walmart") => void;
  isLoading: boolean;
  initialQuery?: string;
  initialMarketplace?: "amazon" | "walmart";
}

export function SearchBar({
  onSearch,
  isLoading,
  initialQuery = "",
  initialMarketplace = "amazon",
}: SearchBarProps) {
  const [query, setQuery] = useState(initialQuery);
  const [marketplace, setMarketplace] = useState<"amazon" | "walmart">(
    initialMarketplace,
  );

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const trimmed = query.trim();
    if (trimmed) onSearch(trimmed, marketplace);
  };

  return (
    <form onSubmit={handleSubmit} className="flex gap-2">
      <Select
        value={marketplace}
        onValueChange={(v) => setMarketplace(v as "amazon" | "walmart")}
      >
        <SelectTrigger className="w-36">
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value="amazon">Amazon</SelectItem>
          <SelectItem value="walmart">Walmart</SelectItem>
        </SelectContent>
      </Select>

      <Input
        placeholder="Search for products..."
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        disabled={isLoading}
        className="flex-1"
      />

      <Button type="submit" disabled={isLoading || !query.trim()}>
        {isLoading ? (
          <>
            <Loader2 className="mr-2 h-4 w-4 animate-spin" />
            Searching...
          </>
        ) : (
          <>
            <Search className="mr-2 h-4 w-4" />
            Search
          </>
        )}
      </Button>
    </form>
  );
}
