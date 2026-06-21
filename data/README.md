

# mutation profile data

### OmicsSomaticMutations.csv

Pipeline: Mutations

MAF-like file containing information on all the somatic point mutations and indels called in the DepMap cell lines. 
The calls are generated from Mutect2. 

Additional processed mutation matrices containing genotyped mutation calls are available for download as part of the full DepMap Data Release.

**Columns:**

- Chrom
- Pos
- Ref
- Alt
- AF
- DP
- RefCount
- AltCount
- GT
- PS
- VariantType
- VariantInfo
- DNAChange
- ProteinChange
- HugoSymbol
- EnsemblGeneID
- EnsemblFeatureID
- HgncName
- HgncFamily
- UniprotID
- DbsnpRsID
- GcContent
- NMD
- MolecularConsequence
- VepImpact
- VepBiotype
- VepHgncID
- VepExistingVariation
- VepManeSelect
- VepENSP
- VepSwissprot
- Sift
- Polyphen
- GnomadeAF
- GnomadgAF
- VepClinSig
- VepSomatic
- VepPliGeneValue
- VepLofTool
- OncogeneHighImpact
- TumorSuppressorHighImpact
- TranscriptLikelyLof
- Brca1FuncScore
- CivicID
- CivicDescription
- CivicScore
- LikelyLoF
- HessDriver
- HessSignature
- RevelScore
- PharmgkbId
- GwasDisease
- GwasPmID
- GtexGene
- ProveanPrediction
- AMClass
- AMPathogenicity
- Hotspot
- Rescue
- EntrezGeneID
- ModelID
- ModelConditionID
- SequencingID
- IsDefaultEntryForModel
- IsDefaultEntryForMC



For details, see https://storage.googleapis.com/shared-portal-files/Tools/26Q1_Mutation_Pipeline_Documentation.pdf

# TCGA Data 
Patient	KRAS	EGFR	TP53	p-AKT	ERK expr	Copy number	Survival
TCGA-01	G12C	WT	Mut	high	high	MET amp	14 mo
TCGA-02	WT	L858R	WT	medium	high	ERBB2 gain	48 mo
TCGA-03	BRAF V600E	WT	Mut	low	high	none	20 mo