"""
Rich HTML description builder for eBay listings.

Generates mobile-responsive, eBay-compliant HTML descriptions from scraped
product data. All CSS is inline since eBay strips <style> tags.

Templates:
    MODERN  — Card-based layout with hero image, feature grid, and image gallery
    CLASSIC — Traditional eBay listing style with bold headers and HR separators
    MINIMAL — Lightweight text-focused layout for simple products

Usage:
    builder = DescriptionBuilder()
    html = builder.build(product)                        # default MODERN
    html = builder.build(product, DescriptionTemplate.CLASSIC)
    variants = builder.build_all_templates(product)      # dict of all 3
"""

import re
from enum import StrEnum

from app.core.models import ScrapedProduct


class DescriptionTemplate(StrEnum):
    """Available description layout templates."""

    MODERN = "modern"
    CLASSIC = "classic"
    MINIMAL = "minimal"


# ─── Color Palette ──────────────────────────────────────────────

_COLORS = {
    "primary": "#2563EB",       # Blue accent
    "primary_dark": "#1D4ED8",
    "bg": "#FFFFFF",
    "bg_alt": "#F8FAFC",
    "border": "#E2E8F0",
    "text": "#1E293B",
    "text_secondary": "#64748B",
    "success": "#16A34A",
}


class DescriptionBuilder:
    """
    Builds rich HTML descriptions for eBay listings from scraped product data.

    Features:
    - Three template variants for A/B testing (modern, classic, minimal)
    - Inline CSS throughout (eBay strips <style> tags)
    - Mobile-responsive layouts (max-width containers, fluid images)
    - Image gallery with up to 4 thumbnails
    - Automatic feature bullet extraction from description text
    - HTML-escaped user content to prevent XSS
    """

    # ─── Public API ──────────────────────────────────────────

    def build(
        self,
        product: ScrapedProduct,
        template: DescriptionTemplate = DescriptionTemplate.MODERN,
    ) -> str:
        """
        Build an HTML description for an eBay listing.

        Args:
            product: Scraped product data.
            template: Layout template to use.

        Returns:
            HTML string for the eBay listing description.
        """
        builders = {
            DescriptionTemplate.MODERN: self._build_modern,
            DescriptionTemplate.CLASSIC: self._build_classic,
            DescriptionTemplate.MINIMAL: self._build_minimal,
        }
        builder_fn = builders.get(template, self._build_modern)
        return builder_fn(product)

    def build_all_templates(
        self, product: ScrapedProduct
    ) -> dict[str, str]:
        """
        Build all template variants for A/B testing.

        Args:
            product: Scraped product data.

        Returns:
            Dict mapping template name to HTML string.
        """
        return {
            t.value: self.build(product, t)
            for t in DescriptionTemplate
        }

    # ─── Modern Template ─────────────────────────────────────

    def _build_modern(self, product: ScrapedProduct) -> str:
        """Card-based modern layout with hero image, features, and gallery."""
        sections: list[str] = []

        # ── Header banner
        sections.append(
            f'<div style="background:{_COLORS["primary"]};color:#FFF;'
            f'padding:16px 24px;border-radius:8px 8px 0 0;">'
            f'<h2 style="margin:0;font-size:20px;font-weight:700;'
            f'line-height:1.3;">{self._escape(product.title)}</h2>'
            f"</div>"
        )

        # ── Hero image + description row
        hero_parts: list[str] = []
        if product.has_images:
            hero_parts.append(
                f'<div style="flex:0 0 280px;text-align:center;">'
                f'<img src="{self._escape(product.images[0])}" '
                f'alt="{self._escape(product.title)}" '
                f'style="max-width:280px;max-height:280px;border-radius:6px;'
                f'object-fit:contain;" />'
                f"</div>"
            )

        desc_html = ""
        if product.description:
            features = self._extract_features(product.description)
            if features:
                bullets = "".join(
                    f'<li style="margin-bottom:6px;line-height:1.5;">'
                    f"{self._escape(f)}</li>"
                    for f in features
                )
                desc_html = (
                    f'<ul style="padding-left:20px;margin:0;'
                    f'color:{_COLORS["text"]};">{bullets}</ul>'
                )
            else:
                desc_html = (
                    f'<p style="color:{_COLORS["text"]};line-height:1.6;'
                    f'margin:0;">{self._escape(product.description)}</p>'
                )

        if desc_html:
            hero_parts.append(
                f'<div style="flex:1;min-width:200px;">{desc_html}</div>'
            )

        if hero_parts:
            sections.append(
                f'<div style="display:flex;gap:24px;padding:20px;'
                f'flex-wrap:wrap;align-items:flex-start;">'
                f'{"".join(hero_parts)}</div>'
            )

        # ── Specs table
        specs = self._build_specs(product)
        if specs:
            rows = "".join(
                f'<tr><td style="padding:10px 14px;font-weight:600;'
                f'color:{_COLORS["text"]};border-bottom:1px solid '
                f'{_COLORS["border"]};width:35%;background:{_COLORS["bg_alt"]};">'
                f"{self._escape(k)}</td>"
                f'<td style="padding:10px 14px;color:{_COLORS["text"]};'
                f'border-bottom:1px solid {_COLORS["border"]};">'
                f"{self._escape(v)}</td></tr>"
                for k, v in specs
            )
            sections.append(
                f'<table style="width:100%;border-collapse:collapse;'
                f'margin:0 0 16px 0;border:1px solid {_COLORS["border"]};'
                f'border-radius:6px;overflow:hidden;">'
                f'<thead><tr><th colspan="2" style="background:{_COLORS["primary"]};'
                f'color:#FFF;padding:10px 14px;text-align:left;font-size:14px;'
                f'font-weight:600;">Product Details</th></tr></thead>'
                f"<tbody>{rows}</tbody></table>"
            )

        # ── Image gallery (up to 4 extra images)
        gallery_images = product.images[1:5] if len(product.images) > 1 else []
        if gallery_images:
            thumbs = "".join(
                f'<img src="{self._escape(img)}" '
                f'alt="Product image" '
                f'style="width:120px;height:120px;object-fit:contain;'
                f"border:1px solid {_COLORS['border']};border-radius:4px;"
                f'background:#FFF;" />'
                for img in gallery_images
            )
            sections.append(
                f'<div style="padding:0 20px 16px 20px;">'
                f'<p style="font-weight:600;color:{_COLORS["text"]};'
                f'margin:0 0 10px 0;font-size:14px;">More Images</p>'
                f'<div style="display:flex;gap:10px;flex-wrap:wrap;">'
                f"{thumbs}</div></div>"
            )

        # ── KonvertIt footer
        footer = self._build_footer()

        body = "\n".join(sections)
        return (
            f'<div style="font-family:Arial,Helvetica,sans-serif;'
            f"max-width:800px;margin:0 auto;background:{_COLORS['bg']};"
            f"border:1px solid {_COLORS['border']};border-radius:8px;"
            f'overflow:hidden;">\n{body}\n{footer}\n</div>'
        )

    # ─── Classic Template ────────────────────────────────────

    def _build_classic(self, product: ScrapedProduct) -> str:
        """Traditional eBay listing with bold headers and HR separators."""
        sections: list[str] = []

        # Title
        sections.append(
            f'<h2 style="color:{_COLORS["primary"]};font-size:22px;'
            f'margin:0 0 10px 0;padding-bottom:10px;'
            f'border-bottom:2px solid {_COLORS["primary"]};">'
            f"{self._escape(product.title)}</h2>"
        )

        # Hero image
        if product.has_images:
            sections.append(
                f'<div style="text-align:center;margin:16px 0;">'
                f'<img src="{self._escape(product.images[0])}" '
                f'alt="{self._escape(product.title)}" '
                f'style="max-width:400px;max-height:400px;object-fit:contain;" />'
                f"</div>"
            )

        # Description
        if product.description:
            sections.append(
                f'<h3 style="color:{_COLORS["text"]};font-size:16px;'
                f'margin:16px 0 8px 0;">Description</h3>'
            )
            features = self._extract_features(product.description)
            if features:
                bullets = "".join(
                    f'<li style="margin-bottom:4px;">{self._escape(f)}</li>'
                    for f in features
                )
                sections.append(
                    f'<ul style="padding-left:24px;color:{_COLORS["text"]};'
                    f'line-height:1.6;">{bullets}</ul>'
                )
            else:
                sections.append(
                    f'<p style="color:{_COLORS["text"]};line-height:1.6;">'
                    f"{self._escape(product.description)}</p>"
                )

        # Separator
        sections.append(
            f'<hr style="border:0;border-top:1px solid {_COLORS["border"]};'
            f'margin:16px 0;" />'
        )

        # Specs table
        specs = self._build_specs(product)
        if specs:
            sections.append(
                f'<h3 style="color:{_COLORS["text"]};font-size:16px;'
                f'margin:0 0 10px 0;">Product Details</h3>'
            )
            rows = "".join(
                f'<tr><td style="padding:8px 12px;font-weight:bold;'
                f'background:{_COLORS["bg_alt"]};border:1px solid '
                f'{_COLORS["border"]};width:35%;">{self._escape(k)}</td>'
                f'<td style="padding:8px 12px;border:1px solid '
                f'{_COLORS["border"]};">{self._escape(v)}</td></tr>'
                for k, v in specs
            )
            sections.append(
                f'<table style="width:100%;border-collapse:collapse;'
                f'margin-bottom:16px;">{rows}</table>'
            )

        # Image gallery
        gallery_images = product.images[1:5] if len(product.images) > 1 else []
        if gallery_images:
            sections.append(
                f'<hr style="border:0;border-top:1px solid {_COLORS["border"]};'
                f'margin:16px 0;" />'
            )
            sections.append(
                f'<h3 style="color:{_COLORS["text"]};font-size:16px;'
                f'margin:0 0 10px 0;">Additional Images</h3>'
            )
            thumbs = "".join(
                f'<img src="{self._escape(img)}" alt="Product image" '
                f'style="width:140px;height:140px;object-fit:contain;'
                f"border:1px solid {_COLORS['border']};margin:4px;"
                f'background:#FFF;" />'
                for img in gallery_images
            )
            sections.append(
                f'<div style="display:flex;gap:8px;flex-wrap:wrap;">'
                f"{thumbs}</div>"
            )

        footer = self._build_footer()
        body = "\n".join(sections)
        return (
            f'<div style="font-family:Arial,Helvetica,sans-serif;'
            f"max-width:800px;margin:0 auto;padding:24px;"
            f'background:{_COLORS["bg"]};">\n{body}\n{footer}\n</div>'
        )

    # ─── Minimal Template ────────────────────────────────────

    def _build_minimal(self, product: ScrapedProduct) -> str:
        """Lightweight text-focused layout for simple products."""
        sections: list[str] = []

        # Title
        sections.append(
            f'<h2 style="font-size:18px;color:{_COLORS["text"]};'
            f'margin:0 0 12px 0;">{self._escape(product.title)}</h2>'
        )

        # Description
        if product.description:
            features = self._extract_features(product.description)
            if features:
                bullets = "".join(
                    f'<li style="margin-bottom:4px;">{self._escape(f)}</li>'
                    for f in features
                )
                sections.append(
                    f'<ul style="padding-left:20px;color:{_COLORS["text"]};'
                    f'line-height:1.5;margin:0 0 12px 0;">{bullets}</ul>'
                )
            else:
                sections.append(
                    f'<p style="color:{_COLORS["text"]};line-height:1.5;'
                    f'margin:0 0 12px 0;">{self._escape(product.description)}</p>'
                )

        # Compact specs (inline, no table)
        specs = self._build_specs(product)
        if specs:
            spec_items = " &bull; ".join(
                f"<strong>{self._escape(k)}:</strong> {self._escape(v)}"
                for k, v in specs
            )
            sections.append(
                f'<p style="color:{_COLORS["text_secondary"]};font-size:13px;'
                f'line-height:1.6;margin:0 0 12px 0;">{spec_items}</p>'
            )

        # Single image only for minimal
        if product.has_images:
            sections.append(
                f'<div style="text-align:center;margin:12px 0;">'
                f'<img src="{self._escape(product.images[0])}" '
                f'alt="{self._escape(product.title)}" '
                f'style="max-width:300px;max-height:300px;object-fit:contain;" />'
                f"</div>"
            )

        body = "\n".join(sections)
        return (
            f'<div style="font-family:Arial,Helvetica,sans-serif;'
            f"max-width:600px;margin:0 auto;padding:16px;"
            f'color:{_COLORS["text"]};">\n{body}\n</div>'
        )

    # ─── Shared Helpers ──────────────────────────────────────

    def _extract_features(self, description: str) -> list[str]:
        """
        Extract feature bullet points from a description string.

        Recognizes common bullet prefixes: •, -, *, ►, ✓, ✔
        Falls back to splitting on sentences if no bullets are found
        (only if there are 2+ sentences).

        Returns:
            List of feature strings (empty list if plain paragraph is better).
        """
        if not description:
            return []

        # Try structured bullet patterns first
        bullet_pattern = re.compile(
            r"(?:^|\n)\s*[•\-\*►✓✔]\s*(.+?)(?=\n|$)"
        )
        bullets = bullet_pattern.findall(description)
        if bullets:
            return [b.strip() for b in bullets if b.strip()]

        # Try numbered list patterns: "1. Something", "1) Something"
        numbered_pattern = re.compile(
            r"(?:^|\n)\s*\d+[.)]\s*(.+?)(?=\n|$)"
        )
        numbered = numbered_pattern.findall(description)
        if len(numbered) >= 2:
            return [n.strip() for n in numbered if n.strip()]

        # Fall back to sentence splitting (only if multiple sentences)
        sentences = [
            s.strip() for s in re.split(r"(?<=[.!])\s+", description) if s.strip()
        ]
        if len(sentences) >= 3:
            return sentences[:8]  # Cap at 8 bullets

        # Not enough structure — return empty (caller renders as paragraph)
        return []

    def _build_specs(self, product: ScrapedProduct) -> list[tuple[str, str]]:
        """Build a list of (label, value) spec pairs from product data."""
        specs: list[tuple[str, str]] = []

        if product.brand:
            specs.append(("Brand", product.brand))
        if product.category:
            specs.append(("Category", product.category))
        if product.availability:
            specs.append(("Availability", product.availability))

        # Source marketplace for transparency
        if product.source_marketplace:
            marketplace_display = product.source_marketplace.value.title()
            specs.append(("Source", marketplace_display))

        return specs

    def _build_footer(self) -> str:
        """Build a small KonvertIt branding footer."""
        return (
            f'<div style="text-align:center;padding:12px;'
            f"border-top:1px solid {_COLORS['border']};"
            f'margin-top:8px;">'
            f'<p style="margin:0;font-size:11px;color:{_COLORS["text_secondary"]};">'
            f"Listed with KonvertIt</p></div>"
        )

    def _escape(self, text: str) -> str:
        """Basic HTML escaping to prevent XSS."""
        return (
            text.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
        )
