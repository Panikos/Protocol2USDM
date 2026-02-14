---
description: Start the web UI dev server and verify it loads correctly
---

## Steps

1. Check if the dev server is already running on port 3000:
// turbo
```
Get-NetTCPConnection -LocalPort 3000 -ErrorAction SilentlyContinue | Select-Object -First 1
```

2. If not running, start the dev server:
```
cd web-ui && npm run dev
```

3. Open the browser preview at http://localhost:3000

4. Verify the home page loads with the protocol list.

5. To run TypeScript type-checking:
// turbo
```
npx tsc --noEmit --pretty
```

6. To regenerate TypeScript types from USDM schema:
```
python scripts/generate_ts_types.py
```
