# Progressive Loading Pattern

Pattern for instant page loads with background status checks.

## When to Use

Use this pattern when:
- Items require slow async checks (network connections, health checks, file system scans)
- You want instant page load (show spinners, not blank page)
- Results can be cached for subsequent loads
- Checks can run in parallel

## Backend Pattern

### 1. Use CachedStatusChecker

```python
from agentwire.cached_status import CachedStatusChecker

# In your server class
self.machine_checker = CachedStatusChecker(ttl_seconds=30)

# In API endpoint
async def api_machines(self, request):
    raw_machines = load_machines_from_config()

    # Check function returns status data
    async def check_machine(machine):
        status = await self._check_machine_status(machine)
        ip = await self._resolve_hostname(machine['host']) if status == 'online' else None
        return {'status': status, 'ip': ip}

    # Returns immediately with cached or "checking" status
    machines = await self.machine_checker.get_with_status(
        raw_machines,
        check_fn=check_machine,
        id_field='id'
    )

    return web.json_response(machines)
```

### 2. Manual Implementation

If you don't need the full utility:

```python
# Return items with status="checking"
for item in items:
    result.append({**item, 'status': 'checking'})

# Trigger background checks (don't await)
asyncio.create_task(self._background_check(items))

return result
```

## Frontend Pattern

### 1. Use setupAutoRefresh

```javascript
import { setupAutoRefresh } from '../utils/auto-refresh.js';

async function fetchItems() {
    const response = await fetch('/api/items');
    const items = await response.json();

    // Auto-refresh while any items have status="checking"
    setupAutoRefresh(items, itemsWindow);

    return items;
}
```

### 2. Render with Spinner

```javascript
function renderItem(item) {
    const cardOptions = {
        id: item.id,
        name: item.name,
        // ... other options
    };

    // Show spinner while checking, status dot when known
    if (item.status === 'checking') {
        cardOptions.activityState = 'processing';  // Shows spinner
    } else {
        cardOptions.statusOnline = item.status === 'online';  // Shows dot
    }

    return ListCard(cardOptions);
}
```

## Complete Example

See `agentwire/static/js/windows/machines-window.js` for reference implementation.

### Flow

1. **Initial Load** (0ms)
   - API returns items with `status: "checking"`
   - Page renders immediately with spinners

2. **Background Checks** (0-1500ms)
   - Server checks all items in parallel
   - Results cached with 30s TTL

3. **Auto Refresh** (2000ms)
   - Frontend refreshes after 2s delay
   - API returns cached status
   - Spinners → status dots

4. **Subsequent Loads** (instant)
   - Cache hit, no spinners needed

## Benefits

- ✅ Instant page load (no waiting for checks)
- ✅ Progressive updates (spinners → real status)
- ✅ Parallel checks (N items = 1.5s, not N × 1.5s)
- ✅ Cached results (fast subsequent loads)
- ✅ Automatic retries (if still checking)

## Configuration

**Backend Cache TTL:**
```python
CachedStatusChecker(ttl_seconds=30)  # Default 30s
```

**Frontend Refresh Delay:**
```javascript
setupAutoRefresh(items, window, 'status', 'checking', 2000)  // 2s delay
```
