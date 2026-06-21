// Base URL for backend API calls.
//
// - Dev: unset, so this is '' and calls stay relative ('/api/...'), routed by
//   the Vite dev proxy (which strips the /api prefix) to the local backend.
// - Prod: set VITE_API_BASE to the deployed backend origin (e.g. the Render
//   URL). Calls then go straight to the backend ('<origin>/api/...'); the
//   backend strips the /api prefix. Going direct (not via a frontend-host
//   rewrite) keeps the SSE /profiles/stream endpoint unbuffered.
export const API_BASE: string = import.meta.env.VITE_API_BASE ?? ''
