"""
Database repository layer for KonvertIt.

All repositories inherit from BaseRepository and provide tenant-isolated
CRUD operations plus entity-specific query methods.

Usage:
    from app.db.repositories import ProductRepository, ConversionRepository

    product_repo = ProductRepository(session)
    products = await product_repo.find_by_user(user_id)
"""

from app.db.repositories.base_repo import BaseRepository
from app.db.repositories.conversion_repo import ConversionRepository
from app.db.repositories.ebay_credential_repo import EbayCredentialRepository
from app.db.repositories.listing_repo import ListingRepository
from app.db.repositories.price_history_repo import PriceHistoryRepository
from app.db.repositories.product_repo import ProductRepository
from app.db.repositories.user_repo import UserRepository

__all__ = [
    "BaseRepository",
    "ConversionRepository",
    "EbayCredentialRepository",
    "ListingRepository",
    "PriceHistoryRepository",
    "ProductRepository",
    "UserRepository",
]
