"""
Cached status checker utility for progressive loading.

Pattern:
1. Return items immediately with status="checking"
2. Trigger background checks
3. Cache results with TTL
4. Subsequent requests use cache

Usage:
    checker = CachedStatusChecker(ttl_seconds=30)

    # In API handler:
    items = await checker.get_with_status(
        raw_items,
        check_fn=lambda item: check_machine_status(item),
        id_field='id'
    )
"""

import asyncio
import time
from typing import Any, Callable, Dict, List, Optional


class CachedStatusChecker:
    """Manage cached status checks with background updates."""

    def __init__(self, ttl_seconds: int = 30):
        """
        Initialize checker.

        Args:
            ttl_seconds: How long to cache results (default 30s)
        """
        self.ttl_seconds = ttl_seconds
        self._cache: Dict[str, Dict[str, Any]] = {}

    async def get_with_status(
        self,
        items: List[Dict[str, Any]],
        check_fn: Callable[[Dict[str, Any]], Any],
        id_field: str = 'id',
        checking_status: str = 'checking'
    ) -> List[Dict[str, Any]]:
        """
        Get items with cached or checking status.

        Triggers background checks for uncached/stale items.

        Args:
            items: List of items to check
            check_fn: Async function that checks one item and returns status data
            id_field: Field name to use as cache key
            checking_status: Status value to use for unchecked items

        Returns:
            List of items with status field added/updated
        """
        result = []
        items_to_check = []

        for item in items:
            item_id = item.get(id_field)
            if not item_id:
                continue

            cached = self._cache.get(item_id)

            # Use cache if fresh
            if cached and (time.time() - cached.get('timestamp', 0)) < self.ttl_seconds:
                result.append({
                    **item,
                    **cached['data']
                })
            else:
                # No cache or stale - return as checking
                result.append({
                    **item,
                    'status': checking_status
                })
                items_to_check.append(item)

        # Trigger background checks (don't await)
        if items_to_check:
            asyncio.create_task(self._background_check(items_to_check, check_fn, id_field))

        return result

    async def _background_check(
        self,
        items: List[Dict[str, Any]],
        check_fn: Callable,
        id_field: str
    ):
        """Run checks in background and update cache."""
        async def check_and_cache(item):
            try:
                status_data = await check_fn(item)
                item_id = item.get(id_field)
                self._cache[item_id] = {
                    'data': status_data,
                    'timestamp': time.time()
                }
            except Exception:
                # Silently fail - item will retry on next request
                pass

        # Check all items in parallel
        await asyncio.gather(
            *[check_and_cache(item) for item in items],
            return_exceptions=True
        )

    def clear_cache(self, item_id: Optional[str] = None):
        """Clear cache for specific item or all items."""
        if item_id:
            self._cache.pop(item_id, None)
        else:
            self._cache.clear()
