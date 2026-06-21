import { Link } from 'react-router-dom'

export default function Home() {
  return (
    <section>
      <h1 className="text-3xl font-bold tracking-tight">Lung Adenocarcinoma State Model</h1>
      <p className="mt-3 max-w-2xl text-slate-600">
        A frontend for exploring and visualizing cancer-state model predictions. Built with Vite,
        React, TypeScript, Tailwind CSS, and React Router.
      </p>
      <Link
        to="/model"
        className="mt-6 inline-block rounded-md bg-slate-900 px-4 py-2 text-sm font-medium text-white hover:bg-slate-700"
      >
        Open the model →
      </Link>
    </section>
  )
}
