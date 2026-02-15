import { DollarSign, StopCircle } from "lucide-react";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Button } from "@/components/ui/button";
import { StatusBadge } from "@/components/shared/StatusBadge";
import type { Listing } from "@/types/api";

interface ListingsTableProps {
  listings: Listing[];
  onUpdatePrice: (listing: Listing) => void;
  onEndListing: (listing: Listing) => void;
}

function formatDate(dateStr: string | null): string {
  if (!dateStr) return "—";
  return new Date(dateStr).toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
  });
}

export function ListingsTable({
  listings,
  onUpdatePrice,
  onEndListing,
}: ListingsTableProps) {
  if (listings.length === 0) {
    return (
      <div className="flex flex-col items-center gap-2 py-12 text-center">
        <p className="text-sm text-muted-foreground">No listings found.</p>
      </div>
    );
  }

  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead className="w-[40%]">Title</TableHead>
          <TableHead>Price</TableHead>
          <TableHead>Status</TableHead>
          <TableHead>eBay ID</TableHead>
          <TableHead>Listed</TableHead>
          <TableHead className="text-right">Actions</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {listings.map((listing) => (
          <TableRow key={listing.id}>
            <TableCell className="font-medium max-w-[300px] truncate">
              {listing.title}
            </TableCell>
            <TableCell>${listing.price.toFixed(2)}</TableCell>
            <TableCell>
              <StatusBadge status={listing.status} />
            </TableCell>
            <TableCell className="text-muted-foreground text-xs">
              {listing.ebay_item_id ?? "—"}
            </TableCell>
            <TableCell className="text-muted-foreground text-xs">
              {formatDate(listing.listed_at)}
            </TableCell>
            <TableCell className="text-right">
              <div className="flex justify-end gap-1">
                <Button
                  variant="ghost"
                  size="icon"
                  title="Update price"
                  onClick={() => onUpdatePrice(listing)}
                >
                  <DollarSign className="h-4 w-4" />
                </Button>
                {(listing.status === "active" || listing.status === "draft") && (
                  <Button
                    variant="ghost"
                    size="icon"
                    title="End listing"
                    onClick={() => onEndListing(listing)}
                  >
                    <StopCircle className="h-4 w-4 text-destructive" />
                  </Button>
                )}
              </div>
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}
