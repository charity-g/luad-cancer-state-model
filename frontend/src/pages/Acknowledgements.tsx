import {
  Database,
  Dna,
  BrainCircuit,
  Network,
  FlaskConical,
  Microscope,
  ExternalLink,
} from "lucide-react";

const sources = [
  {
    title: "DepMap (Cancer Dependency Map)",
    organization: "Broad Institute",
    icon: <BrainCircuit className="w-5 h-5" />,
    description:
      "The drug-routing and pathway vulnerability components of Workbench were informed by LUAD mutation and dependency data from the Cancer Dependency Map (DepMap) project.",
    citation:
      "Tsherniak A, Vazquez F, Montgomery PG, et al. Defining a Cancer Dependency Map. Cell. 2017;170(3):564–576.e16.",
    link: "https://depmap.org",
  },
  {
    title: "TCGA (The Cancer Genome Atlas)",
    organization: "National Cancer Institute",
    icon: <Database className="w-5 h-5" />,
    description:
      "TCGA provided foundational cancer genomics datasets and molecular characterization resources relevant to LUAD biology and pathway interpretation.",
    citation:
      "The Cancer Genome Atlas Research Network. Comprehensive molecular profiling of lung adenocarcinoma. Nature. 2014;511:543–550.",
    link: "https://www.cancer.gov/tcga",
  },
  {
    title: "COSMIC",
    organization: "Wellcome Sanger Institute",
    icon: <Dna className="w-5 h-5" />,
    description:
      "COSMIC mutation annotations informed cancer variant interpretation and oncogenic context.",
    citation:
      "Tate JG, Bamford S, Jubb HC, et al. COSMIC: the Catalogue Of Somatic Mutations In Cancer. Nucleic Acids Research. 2019.",
    link: "https://cancer.sanger.ac.uk/cosmic",
  },
  {
    title: "RCSB Protein Data Bank (PDB)",
    organization: "RCSB Protein Data Bank",
    icon: <Microscope className="w-5 h-5" />,
    description:
      "Protein structures displayed in Workbench are derived from the Protein Data Bank.",
    citation:
      "Berman HM, Westbrook J, Feng Z, et al. The Protein Data Bank. Nucleic Acids Research. 2000.",
    link: "https://www.rcsb.org",
  },
  {
    title: "UniProt",
    organization: "UniProt Consortium",
    icon: <FlaskConical className="w-5 h-5" />,
    description:
      "UniProt protein identifiers and annotations were used for biological entity normalization and protein metadata.",
    citation:
      "The UniProt Consortium. UniProt: the Universal Protein Knowledgebase. Nucleic Acids Research. 2025.",
    link: "https://www.uniprot.org",
  },
  {
    title: "CPTAC",
    organization: "National Cancer Institute",
    icon: <Network className="w-5 h-5" />,
    description:
      "CPTAC proteomic resources informed pathway-level and protein-level cancer context.",
    citation:
      "Edwards NJ, Oberti M, Thangudu RR, et al. The CPTAC Data Portal: A Resource for Cancer Proteomics Research. Journal of Proteome Research. 2015.",
    link: "https://proteomics.cancer.gov/programs/cptac",
  },
  {
    title: "DrugBank",
    organization: "DrugBank",
    icon: <Database className="w-5 h-5" />,
    description:
      "Drug-target relationships and therapeutic context were informed by DrugBank and related pharmacological resources.",
    citation:
      "Wishart DS, Feunang YD, Guo AC, et al. DrugBank 5.0: a major update to the DrugBank database. Nucleic Acids Research. 2018.",
    link: "https://go.drugbank.com",
  },
  {
    title: "KEGG",
    organization: "Kyoto Encyclopedia of Genes and Genomes",
    icon: <Network className="w-5 h-5" />,
    description:
      "KEGG pathway relationships and biological pathway mappings were used in graph construction and pathway visualization.",
    citation:
      "Kanehisa M, Goto S. KEGG: Kyoto Encyclopedia of Genes and Genomes. Nucleic Acids Research. 2000.",
    link: "https://www.kegg.jp",
  },
  {
    title: "Neo4j",
    organization: "Neo4j",
    icon: <Database className="w-5 h-5" />,
    description:
      "Workbench uses Neo4j Aura as the graph database and knowledge graph infrastructure layer.",
    citation: "",
    link: "https://neo4j.com",
  },
  {
    title: "Anthropic Claude",
    organization: "Anthropic",
    icon: <BrainCircuit className="w-5 h-5" />,
    description:
      "Claude models were used for mutation hydration, text-to-Cypher planning, and graph-grounded mechanistic reasoning.",
    citation: "",
    link: "https://www.anthropic.com",
  },
];

export default function Acknowledgements() {
  return (
    <div className="min-h-screen bg-[#0a0f1c] text-white">
      <div className="max-w-6xl mx-auto px-6 py-20">
        {/* Header */}
        <div className="mb-16">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full border border-cyan-500/30 bg-cyan-500/10 text-cyan-300 text-sm mb-6">
            Biomedical Infrastructure
          </div>

          <h1 className="text-5xl font-bold tracking-tight mb-6">
            Acknowledgements & Data Attribution
          </h1>

          <p className="text-slate-300 text-lg max-w-3xl leading-relaxed">
            Workbench was built using publicly available biomedical datasets,
            pathway resources, and scientific infrastructure from the following
            organizations and projects. We gratefully acknowledge their
            contributions to open scientific research and computational biology.
          </p>
        </div>

        {/* Cards */}
        <div className="grid gap-6">
          {sources.map((source) => (
            <div
              key={source.title}
              className="rounded-2xl border border-white/10 bg-white/5 backdrop-blur-sm p-7 hover:border-cyan-500/30 transition-all"
            >
              <div className="flex items-start justify-between gap-6">
                <div className="flex-1">
                  <div className="flex items-center gap-3 mb-3">
                    <div className="p-2 rounded-lg bg-cyan-500/10 text-cyan-300 border border-cyan-500/20">
                      {source.icon}
                    </div>

                    <div>
                      <h2 className="text-xl font-semibold">
                        {source.title}
                      </h2>
                      <p className="text-slate-400 text-sm">
                        {source.organization}
                      </p>
                    </div>
                  </div>

                  <p className="text-slate-300 leading-relaxed mb-5">
                    {source.description}
                  </p>

                  {source.citation && (
                    <div className="mb-4">
                      <div className="text-xs uppercase tracking-wider text-cyan-300 mb-2">
                        Citation
                      </div>

                      <div className="text-sm text-slate-400 italic leading-relaxed">
                        {source.citation}
                      </div>
                    </div>
                  )}

                  <a
                    href={source.link}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex items-center gap-2 text-cyan-300 hover:text-cyan-200 transition-colors text-sm font-medium"
                  >
                    Visit Resource
                    <ExternalLink className="w-4 h-4" />
                  </a>
                </div>
              </div>
            </div>
          ))}
        </div>

        {/* Footer */}
        <div className="mt-20 rounded-2xl border border-cyan-500/20 bg-cyan-500/5 p-8">
          <h3 className="text-2xl font-semibold mb-4">Special Thanks</h3>

          <p className="text-slate-300 leading-relaxed">
            We thank the researchers, engineers, clinicians, and open-science
            communities behind these resources for making large-scale biomedical
            data and computational tools accessible to the broader research
            ecosystem. Their work made Workbench possible.
          </p>
        </div>
      </div>
    </div>
  );
}
