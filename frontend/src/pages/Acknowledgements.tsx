export default function Acknowledgements() {
  return (
    <div className="mx-auto w-full max-w-3xl px-4 py-10 space-y-10">

      <div>
        <h1 className="text-2xl font-bold tracking-tight text-white">Acknowledgements</h1>
        <p className="mt-2 text-sm text-white/70">
          This work draws on open databases, research resources, and tools made freely available
          by the scientific community.
        </p>
      </div>

      {/* Databases */}
      <section>
        <h2 className="mb-4 text-xs font-semibold uppercase tracking-widest text-white/50">
          Databases &amp; Data Sources
        </h2>
        <div className="space-y-3">
          {[
            {
              name: 'DepMap',
              url: 'https://depmap.org',
              description:
                'Cancer Dependency Map — genome-scale CRISPR screens and omics data across cancer cell lines, providing mutation profiles and dependency scores used as primary input.',
            },
            {
              name: 'KEGG',
              url: 'https://www.kegg.jp',
              description:
                'Kyoto Encyclopedia of Genes and Genomes — pathway topology, gene–pathway membership, and protein interaction data used for network construction and visualisation.',
            },
            {
              name: 'UniProt / Swiss-Prot',
              url: 'https://www.uniprot.org',
              description:
                'Canonical protein sequences and accession numbers used to normalise gene symbols and anchor 3-D structural visualisation.',
            },
            {
              name: 'Therapeutic Target Database (TTD)',
              url: 'https://db.idrblab.net/ttd',
              description:
                'Drug–target associations used to surface clinically relevant compounds for mutated proteins.',
            },
            {
              name: 'dbSNP / ClinVar',
              url: 'https://www.ncbi.nlm.nih.gov/snp',
              description:
                'Variant identifiers (rsIDs) and clinical significance annotations used during mutation normalisation.',
            },
            {
              name: 'AlphaFold Protein Structure Database',
              url: 'https://alphafold.ebi.ac.uk',
              description:
                'Predicted 3-D protein structures rendered in the structure viewer for mutated proteins with known UniProt accessions.',
            },
          ].map((item) => (
            <div key={item.name} className="rounded-lg border border-white/20 bg-white/10 backdrop-blur-sm px-4 py-3">
              <div className="flex items-baseline gap-2 flex-wrap">
                <a
                  href={item.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-sm font-semibold text-white hover:text-white/75 hover:underline"
                >
                  {item.name}
                </a>
                <span className="font-mono text-[10px] text-white/40">{item.url}</span>
              </div>
              <p className="mt-1 text-xs leading-relaxed text-white/65">{item.description}</p>
            </div>
          ))}
        </div>
      </section>

      {/* Tools & Libraries */}
      <section>
        <h2 className="mb-4 text-xs font-semibold uppercase tracking-widest text-white/50">
          Tools &amp; Libraries
        </h2>
        <div className="space-y-3">
          {[
            {
              name: 'Anthropic Claude',
              url: 'https://www.anthropic.com',
              description:
                'Large language model powering variant effect prediction, mechanistic reasoning, and conversational agent functionality.',
            },
            {
              name: 'Neo4j',
              url: 'https://neo4j.com',
              description:
                'Graph database storing mutation–protein–pathway networks and enabling Cypher-based traversal queries.',
            },
            {
              name: 'FastAPI',
              url: 'https://fastapi.tiangolo.com',
              description:
                'Python web framework serving the SSE streaming analysis pipeline and REST endpoints.',
            },
            {
              name: 'React & Vite',
              url: 'https://react.dev',
              description:
                'Frontend framework and build tooling powering the interactive workspace.',
            },
            {
              name: 'Tailwind CSS',
              url: 'https://tailwindcss.com',
              description: 'Utility-first CSS framework used throughout the UI.',
            },
            {
              name: 'Mol* (Molstar)',
              url: 'https://molstar.org',
              description:
                'High-performance 3-D molecular visualisation library embedded in the structure viewer.',
            },
          ].map((item) => (
            <div key={item.name} className="rounded-lg border border-white/20 bg-white/10 backdrop-blur-sm px-4 py-3">
              <div className="flex items-baseline gap-2 flex-wrap">
                <a
                  href={item.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-sm font-semibold text-white hover:text-white/75 hover:underline"
                >
                  {item.name}
                </a>
                <span className="font-mono text-[10px] text-white/40">{item.url}</span>
              </div>
              <p className="mt-1 text-xs leading-relaxed text-white/65">{item.description}</p>
            </div>
          ))}
        </div>
      </section>

      {/* Disclaimer */}
      <section className="rounded-xl border border-amber-300/40 bg-amber-400/15 backdrop-blur-sm px-4 py-4 text-xs leading-relaxed text-amber-100">
        <p className="font-semibold">Research use only</p>
        <p className="mt-1 text-amber-100/80">
          This tool is intended for exploratory research and educational purposes. It does not
          constitute clinical advice and should not be used to guide patient care. Variant effect
          predictions are computational estimates and may be incorrect.
        </p>
      </section>
    </div>
  )
}
