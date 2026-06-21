import { Link } from 'react-router-dom'

export default function NotFound() {
  return (
    <section className="text-center">
      <h1 className="text-2xl font-bold">404 — Not Found</h1>
      <Link to="/" className="mt-4 inline-block text-slate-900 underline">
        Back home
      </Link>
    </section>
  )
}
