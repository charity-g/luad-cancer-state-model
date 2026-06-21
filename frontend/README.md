# LUAD Cancer State Model — Frontend

User-facing frontend for the lung adenocarcinoma (LUAD) cancer-state model.

## Stack

- [Vite](https://vite.dev/) + React 19 + TypeScript
- [Tailwind CSS](https://tailwindcss.com/) v4 (via `@tailwindcss/vite`)
- [React Router](https://reactrouter.com/) v7
- ESLint + Prettier

## Getting started

```bash
npm install
npm run dev      # start the dev server
```

## Scripts

| Script            | Description                       |
| ----------------- | --------------------------------- |
| `npm run dev`     | Start Vite dev server             |
| `npm run build`   | Type-check and build for prod     |
| `npm run preview` | Preview the production build      |
| `npm run lint`    | Run ESLint                        |
| `npm run format`  | Format `src` with Prettier        |

## Structure

```
src/
  components/   Shared UI (Layout, nav)
  pages/        Route pages (Home, Model, NotFound)
  App.tsx       Route definitions
  main.tsx      App entry + BrowserRouter
  index.css     Tailwind entry
```
