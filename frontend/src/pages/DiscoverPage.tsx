import { useState } from "react";
import { TopBar } from "@/components/layout/TopBar";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { SearchBar } from "@/components/discover/SearchBar";
import { DiscoverResults } from "@/components/discover/DiscoverResults";
import { useDiscoverSearch } from "@/hooks/useDiscover";

export function DiscoverPage() {
  const [searchParams, setSearchParams] = useState({
    query: "",
    marketplace: "amazon" as "amazon" | "walmart",
    page: 1,
  });

  const { data, isLoading, error } = useDiscoverSearch(searchParams);

  const handleSearch = (query: string, marketplace: "amazon" | "walmart") => {
    setSearchParams({ query, marketplace, page: 1 });
  };

  const handlePageChange = (page: number) => {
    setSearchParams((prev) => ({ ...prev, page }));
  };

  return (
    <>
      <TopBar title="Discover Products" />
      <div className="space-y-6 p-6">
        <Card>
          <CardHeader>
            <CardTitle>Search Marketplaces</CardTitle>
          </CardHeader>
          <CardContent>
            <SearchBar onSearch={handleSearch} isLoading={isLoading} />
            <p className="mt-2 text-xs text-muted-foreground">
              Search for products on Amazon or Walmart. Click "Convert" to turn
              any product into an eBay listing.
            </p>
          </CardContent>
        </Card>

        {searchParams.query && (
          <DiscoverResults
            products={data?.products ?? []}
            isLoading={isLoading}
            error={error as Error | null}
            page={searchParams.page}
            totalPages={data?.total_pages ?? null}
            onPageChange={handlePageChange}
          />
        )}
      </div>
    </>
  );
}
