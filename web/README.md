# web

The browser UI. React and TypeScript on Vite, talking to the API in
`../my-agent`.

Three views for a recruiter — the candidate list, a candidate's interviews, and
one interview showing its checklist against the scores with the transcript
below — plus a call page a candidate uses to join the interview room.

See the [top-level README](../README.md) for how to run the whole thing.

## Running

```bash
npm install
npm run dev      # http://localhost:5173
```

The dev server proxies `/candidate` and `/interview` to `127.0.0.1:8000`, so the
browser stays on one origin and development needs no CORS. Start the API with:

```bash
cd ../my-agent && uv run uvicorn api.app:app --port 8000
```

## Checks

```bash
npm run build    # tsc -b && vite build
npm run lint
```

There are no frontend tests; the build, the typecheck, and the lint are the
coverage.

## Notes

- `src/types.ts` mirrors the API schemas by hand. Nothing generates them.
- `livekit-client` is far larger than the rest of the app combined, so the call
  page is lazy-loaded. The initial bundle is about 86 kB gzipped against 135 kB
  for the call page alone.
- TypeScript `strict` is on, which the Vite template did not enable.
- `R` refreshes on every page, and the interview screen polls itself while the
  checklist is being generated.
