import { useNavigate } from "react-router-dom";
import { Star, ArrowRight, Check } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import type { DiscoveryProduct } from "@/types/api";

interface ProductCardProps {
  product: DiscoveryProduct;
  selected?: boolean;
  onToggleSelect?: (product: DiscoveryProduct) => void;
}

export function ProductCard({
  product,
  selected = false,
  onToggleSelect,
}: ProductCardProps) {
  const navigate = useNavigate();

  const handleConvert = () => {
    navigate(`/convert?url=${encodeURIComponent(product.url)}`);
  };

  const handleCheckbox = (e: React.MouseEvent) => {
    e.stopPropagation();
    onToggleSelect?.(product);
  };

  return (
    <Card
      className={`overflow-hidden transition-all hover:shadow-md ${
        selected ? "ring-2 ring-primary shadow-md" : ""
      }`}
    >
      {/* Product image */}
      <div className="relative aspect-square bg-gray-50">
        {product.image ? (
          <img
            src={product.image}
            alt={product.name}
            className="h-full w-full object-contain p-2"
            loading="lazy"
          />
        ) : (
          <div className="flex h-full items-center justify-center text-sm text-muted-foreground">
            No image
          </div>
        )}

        {/* Selection checkbox — top right */}
        {onToggleSelect && (
          <button
            type="button"
            onClick={handleCheckbox}
            className={`absolute right-2 top-2 flex h-6 w-6 items-center justify-center rounded-md border-2 transition-colors ${
              selected
                ? "border-primary bg-primary text-primary-foreground"
                : "border-gray-300 bg-white/90 hover:border-primary"
            }`}
          >
            {selected && <Check className="h-4 w-4" />}
          </button>
        )}

        {/* Badges overlay */}
        <div className="absolute left-2 top-2 flex flex-col gap-1">
          {product.is_best_seller && (
            <Badge className="bg-orange-500 text-white text-xs">
              Best Seller
            </Badge>
          )}
          {product.is_amazons_choice && (
            <Badge className="bg-blue-900 text-white text-xs">
              Amazon's Choice
            </Badge>
          )}
          {product.is_prime && (
            <Badge variant="outline" className="bg-white text-xs">
              Prime
            </Badge>
          )}
        </div>
      </div>

      <CardContent className="space-y-2 p-3">
        {/* Title */}
        <p
          className="line-clamp-2 text-sm font-medium leading-tight"
          title={product.name}
        >
          {product.name}
        </p>

        {/* Price */}
        <p className="text-lg font-bold">
          {product.price_symbol}
          {product.price.toFixed(2)}
        </p>

        {/* Rating */}
        {product.stars != null && (
          <div className="flex items-center gap-1 text-xs text-muted-foreground">
            <Star className="h-3 w-3 fill-yellow-400 text-yellow-400" />
            <span>{product.stars}</span>
            {product.total_reviews != null && (
              <span>({product.total_reviews.toLocaleString()})</span>
            )}
          </div>
        )}

        {/* Seller (Walmart) */}
        {product.seller && (
          <p className="truncate text-xs text-muted-foreground">
            Sold by {product.seller}
          </p>
        )}

        {/* Convert button */}
        <Button size="sm" className="w-full" onClick={handleConvert}>
          Convert
          <ArrowRight className="ml-1 h-3 w-3" />
        </Button>
      </CardContent>
    </Card>
  );
}
