"""
eBay credential–specific database repository.

Handles CRUD and query operations for eBay OAuth tokens,
including token expiry checks and active credential lookup.
"""

import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import EbayCredential
from app.db.repositories.base_repo import BaseRepository


class EbayCredentialRepository(BaseRepository[EbayCredential]):
    """Repository for EbayCredential CRUD and token management queries."""

    def __init__(self, session: AsyncSession):
        super().__init__(session, EbayCredential)

    async def find_by_user(
        self,
        user_id: uuid.UUID,
    ) -> list[EbayCredential]:
        """
        Get all eBay credentials for a user.

        Args:
            user_id: Owner user ID.

        Returns:
            List of EbayCredential records.
        """
        stmt = (
            select(EbayCredential)
            .where(EbayCredential.user_id == user_id)
            .order_by(EbayCredential.created_at.desc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def find_active(
        self,
        user_id: uuid.UUID,
        sandbox: bool | None = None,
    ) -> list[EbayCredential]:
        """
        Get eBay credentials with non-expired tokens.

        Args:
            user_id: Owner user ID.
            sandbox: Filter by sandbox mode. None = all.

        Returns:
            List of active (non-expired) credentials.
        """
        now = datetime.now(UTC)
        stmt = (
            select(EbayCredential)
            .where(
                EbayCredential.user_id == user_id,
                # Token is active if expiry is NULL or in the future
                (
                    (EbayCredential.token_expiry.is_(None))
                    | (EbayCredential.token_expiry > now)
                ),
            )
        )
        if sandbox is not None:
            stmt = stmt.where(EbayCredential.sandbox_mode == sandbox)

        stmt = stmt.order_by(EbayCredential.created_at.desc())
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def find_by_store_name(
        self,
        user_id: uuid.UUID,
        store_name: str,
    ) -> EbayCredential | None:
        """
        Find a specific credential by store name.

        Args:
            user_id: Owner user ID.
            store_name: The eBay store name to look up.

        Returns:
            Matching EbayCredential or None.
        """
        stmt = (
            select(EbayCredential)
            .where(
                EbayCredential.user_id == user_id,
                EbayCredential.store_name == store_name,
            )
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def update_tokens(
        self,
        credential_id: uuid.UUID,
        access_token: str,
        refresh_token: str,
        token_expiry: datetime | None = None,
    ) -> EbayCredential | None:
        """
        Update OAuth tokens after a refresh cycle.

        Args:
            credential_id: The credential's primary key.
            access_token: New encrypted access token.
            refresh_token: New encrypted refresh token.
            token_expiry: When the new access token expires.

        Returns:
            Updated EbayCredential, or None if not found.
        """
        credential = await self.get_by_id(credential_id)
        if credential is None:
            return None

        credential.access_token = access_token
        credential.refresh_token = refresh_token
        credential.token_expiry = token_expiry
        await self.session.flush()
        return credential
