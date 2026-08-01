# QuizArena frontend

React + Vite SPA for admin, participant, and host display clients.

## Scripts

```bash
npm ci
npm run dev      # http://localhost:5173 (proxies /api and /ws)
npm test
npm run build
npm run lint
```

## Environment

See [../docs/EnvironmentVariables.md](../docs/EnvironmentVariables.md) and `.env.example`.

When unset, the app defaults to same-origin `/api/v1` and `ws(s)://<host>/ws` (nginx production layout).
