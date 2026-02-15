import { useState } from "react";
import { Loader2 } from "lucide-react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
  DialogDescription,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { ErrorAlert } from "@/components/shared/ErrorAlert";
import type { Listing } from "@/types/api";

interface UpdatePriceModalProps {
  listing: Listing | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSubmit: (listingId: string, price: number) => void;
  isPending: boolean;
  error: Error | null;
}

export function UpdatePriceModal({
  listing,
  open,
  onOpenChange,
  onSubmit,
  isPending,
  error,
}: UpdatePriceModalProps) {
  const [price, setPrice] = useState("");

  const handleOpen = (isOpen: boolean) => {
    if (isOpen && listing) {
      setPrice(listing.price.toFixed(2));
    }
    onOpenChange(isOpen);
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!listing) return;
    const parsed = parseFloat(price);
    if (isNaN(parsed) || parsed <= 0) return;
    onSubmit(listing.id, parsed);
  };

  return (
    <Dialog open={open} onOpenChange={handleOpen}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Update Price</DialogTitle>
          <DialogDescription>
            {listing ? `Set a new price for "${listing.title}"` : ""}
          </DialogDescription>
        </DialogHeader>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="space-y-2">
            <label htmlFor="price" className="text-sm font-medium">
              New Price ($)
            </label>
            <Input
              id="price"
              type="number"
              step="0.01"
              min="0.01"
              value={price}
              onChange={(e) => setPrice(e.target.value)}
              disabled={isPending}
            />
          </div>
          <ErrorAlert error={error} />
          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              onClick={() => onOpenChange(false)}
              disabled={isPending}
            >
              Cancel
            </Button>
            <Button type="submit" disabled={isPending || !price}>
              {isPending ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin" />
                  Updating...
                </>
              ) : (
                "Update Price"
              )}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
