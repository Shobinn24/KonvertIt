import { useNavigate } from "react-router-dom";
import { ArrowRight, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import type { DiscoveryProduct } from "@/types/api";

interface SelectionBarProps {
  selectedProducts: Map<string, DiscoveryProduct>;
  onClear: () => void;
}

export function SelectionBar({ selectedProducts, onClear }: SelectionBarProps) {
  const navigate = useNavigate();
  const count = selectedProducts.size;

  if (count === 0) return null;

  const handleConvert = () => {
    const urls = Array.from(selectedProducts.keys());

    if (urls.length === 1) {
      // Single product → single convert tab
      navigate(`/convert?url=${encodeURIComponent(urls[0]!)}`);;
    } else {
      // Multiple products → bulk convert tab
      const params = new URLSearchParams();
      params.set("tab", "bulk");
      for (const url of urls) {
        params.append("urls", url);
      }
      navigate(`/convert?${params.toString()}`);
    }
  };

  return (
    <div className="fixed bottom-0 left-0 right-0 z-50 border-t bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/80">
      <div className="mx-auto flex max-w-7xl items-center justify-between px-6 py-3">
        <span className="text-sm font-medium">
          {count} product{count !== 1 ? "s" : ""} selected
        </span>

        <div className="flex items-center gap-2">
          <Button variant="ghost" size="sm" onClick={onClear}>
            <X className="mr-1 h-4 w-4" />
            Clear
          </Button>
          <Button size="sm" onClick={handleConvert}>
            Convert Selected
            <ArrowRight className="ml-1 h-4 w-4" />
          </Button>
        </div>
      </div>
    </div>
  );
}
