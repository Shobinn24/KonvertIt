import { useState, useCallback, useEffect } from "react";
import { useSearchParams as useRouterSearchParams } from "react-router-dom";
import { TopBar } from "@/components/layout/TopBar";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { SearchBar } from "@/components/discover/SearchBar";
import { DiscoverResults } from "@/components/discover/DiscoverResults";
import { SelectionBar } from "@/components/discover/SelectionBar";
import { useDiscoverSearch } from "@/hooks/useDiscover";
import type { DiscoveryProduct } from "@/types/api";

export function DiscoverPage() {
  // Persist search state in URL params so it survives navigation
  const [urlParams, setUrlParams] = useRouterSearchParams();
  const query = urlParams.get("q") || "";
  const marketplace =
    (urlParams.get("marketplace") as "amazon" | "walmart") || "amazon";
  const page = Number(urlParams.get("page") || "1");

  const { data, isLoading, error } = useDiscoverSearch({
    query,
    marketplace,
    page,
  });

  // Multi-select state (keyed by URL for dedup)
  const [selectedProducts, setSelectedProducts] = useState<
    Map<string, DiscoveryProduct>
  >(new Map());

  // Clear selections when search changes
  useEffect(() => {
    setSelectedProducts(new Map());
  }, [query, marketplace]);

  const handleSearch = (
    newQuery: string,
    newMarketplace: "amazon" | "walmart",
  ) => {
    setUrlParams({ q: newQuery, marketplace: newMarketplace, page: "1" });
  };

  const handlePageChange = (newPage: number) => {
    setUrlParams((prev) => {
      const next = new URLSearchParams(prev);
      next.set("page", String(newPage));
      return next;
    });
  };

  const handleToggleSelect = useCallback((product: DiscoveryProduct) => {
    setSelectedProducts((prev) => {
      const next = new Map(prev);
      if (next.has(product.url)) {
        next.delete(product.url);
      } else {
        next.set(product.url, product);
      }
      return next;
    });
  }, []);

  const handleClearSelection = useCallback(() => {
    setSelectedProducts(new Map());
  }, []);

  const selectedUrls = new Set(selectedProducts.keys());

  return (
    <>
      <TopBar title="Discover Products" />
      <div className="space-y-6 p-6 pb-24">
        <Card>
          <CardHeader>
            <CardTitle>Search Marketplaces</CardTitle>
          </CardHeader>
          <CardContent>
            <SearchBar
              onSearch={handleSearch}
              isLoading={isLoading}
              initialQuery={query}
              initialMarketplace={marketplace}
            />
            <p className="mt-2 text-xs text-muted-foreground">
              Search for products on Amazon or Walmart. Select products to
              convert, or click "Convert" on any card for a quick single
              conversion.
            </p>
          </CardContent>
        </Card>

        {query && (
          <DiscoverResults
            products={data?.products ?? []}
            isLoading={isLoading}
            error={error as Error | null}
            page={page}
            totalPages={data?.total_pages ?? null}
            onPageChange={handlePageChange}
            selectedUrls={selectedUrls}
            onToggleSelect={handleToggleSelect}
          />
        )}
      </div>

      <SelectionBar
        selectedProducts={selectedProducts}
        onClear={handleClearSelection}
      />
    </>
  );
}
