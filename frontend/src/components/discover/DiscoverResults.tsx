import { Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { ProductCard } from "./ProductCard";
import { ErrorAlert } from "@/components/shared/ErrorAlert";
import type { DiscoveryProduct } from "@/types/api";

interface DiscoverResultsProps {
  products: DiscoveryProduct[];
  isLoading: boolean;
  error: Error | null;
  page: number;
  totalPages: number | null;
  onPageChange: (page: number) => void;
  selectedUrls: Set<string>;
  onToggleSelect: (product: DiscoveryProduct) => void;
}

export function DiscoverResults({
  products,
  isLoading,
  error,
  page,
  totalPages,
  onPageChange,
  selectedUrls,
  onToggleSelect,
}: DiscoverResultsProps) {
  if (error) return <ErrorAlert error={error} />;

  if (isLoading && products.length === 0) {
    return (
      <div className="flex items-center justify-center py-12">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    );
  }

  if (products.length === 0) {
    return (
      <p className="py-12 text-center text-sm text-muted-foreground">
        No results found. Try a different search term.
      </p>
    );
  }

  return (
    <div className="space-y-6">
      {/* Results count */}
      <div className="flex items-center justify-between">
        <p className="text-sm text-muted-foreground">
          {products.length} products found
          {isLoading && " (updating...)"}
        </p>
      </div>

      {/* Results grid */}
      <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-4">
        {products.map((product, i) => (
          <ProductCard
            key={`${product.url}-${i}`}
            product={product}
            selected={selectedUrls.has(product.url)}
            onToggleSelect={onToggleSelect}
          />
        ))}
      </div>

      {/* Pagination */}
      <div className="flex items-center justify-center gap-2">
        <Button
          variant="outline"
          size="sm"
          disabled={page <= 1 || isLoading}
          onClick={() => onPageChange(page - 1)}
        >
          Previous
        </Button>
        <span className="text-sm text-muted-foreground">
          Page {page}
          {totalPages ? ` of ${totalPages}` : ""}
        </span>
        <Button
          variant="outline"
          size="sm"
          disabled={
            (totalPages != null && page >= totalPages) || isLoading
          }
          onClick={() => onPageChange(page + 1)}
        >
          Next
        </Button>
      </div>
    </div>
  );
}
