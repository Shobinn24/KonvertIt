import { useState } from "react";
import { TopBar } from "@/components/layout/TopBar";
import { StatusTabs } from "@/components/listings/StatusTabs";
import { ListingsTable } from "@/components/listings/ListingsTable";
import { UpdatePriceModal } from "@/components/listings/UpdatePriceModal";
import { EndListingDialog } from "@/components/listings/EndListingDialog";
import { PaginationBar } from "@/components/shared/PaginationBar";
import { LoadingSpinner } from "@/components/shared/LoadingSpinner";
import { ErrorAlert } from "@/components/shared/ErrorAlert";
import {
  useListingsQuery,
  useUpdatePriceMutation,
  useEndListingMutation,
} from "@/hooks/useListings";
import type { Listing } from "@/types/api";

const PAGE_SIZE = 20;

export function ListingsPage() {
  const [statusFilter, setStatusFilter] = useState("all");
  const [page, setPage] = useState(0);

  // Modals
  const [priceTarget, setPriceTarget] = useState<Listing | null>(null);
  const [priceOpen, setPriceOpen] = useState(false);
  const [endTarget, setEndTarget] = useState<Listing | null>(null);
  const [endOpen, setEndOpen] = useState(false);

  const query = useListingsQuery({
    status: statusFilter === "all" ? undefined : statusFilter,
    limit: PAGE_SIZE,
    offset: page * PAGE_SIZE,
  });

  const updatePrice = useUpdatePriceMutation();
  const endListing = useEndListingMutation();

  const handleStatusChange = (value: string) => {
    setStatusFilter(value);
    setPage(0);
  };

  const handleUpdatePrice = (listingId: string, price: number) => {
    updatePrice.mutate(
      { listingId, price },
      { onSuccess: () => setPriceOpen(false) },
    );
  };

  const handleEndListing = (listingId: string) => {
    endListing.mutate(listingId, {
      onSuccess: () => setEndOpen(false),
    });
  };

  return (
    <>
      <TopBar title="Listings" />
      <div className="space-y-4 p-6">
        <StatusTabs value={statusFilter} onChange={handleStatusChange} />

        {query.isLoading ? (
          <div className="flex items-center justify-center p-12">
            <LoadingSpinner size={32} />
          </div>
        ) : query.error ? (
          <ErrorAlert error={query.error} />
        ) : (
          <>
            <ListingsTable
              listings={query.data?.listings ?? []}
              onUpdatePrice={(listing) => {
                setPriceTarget(listing);
                setPriceOpen(true);
              }}
              onEndListing={(listing) => {
                setEndTarget(listing);
                setEndOpen(true);
              }}
            />
            <PaginationBar
              total={query.data?.total ?? 0}
              page={page}
              pageSize={PAGE_SIZE}
              onPageChange={setPage}
            />
          </>
        )}
      </div>

      <UpdatePriceModal
        listing={priceTarget}
        open={priceOpen}
        onOpenChange={setPriceOpen}
        onSubmit={handleUpdatePrice}
        isPending={updatePrice.isPending}
        error={updatePrice.error}
      />

      <EndListingDialog
        listing={endTarget}
        open={endOpen}
        onOpenChange={setEndOpen}
        onConfirm={handleEndListing}
        isPending={endListing.isPending}
        error={endListing.error}
      />
    </>
  );
}
