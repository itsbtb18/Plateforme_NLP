# Compilation du rapport LaTeX

## Fichiers

- **RAPPORT_CHATBOT_JURIDIQUE.tex** — Source LaTeX du rapport
- **RAPPORT_CHATBOT_JURIDIQUE_MATHEMATIQUES_ETENDU.md** — Version Markdown (formules en `$...$` et `$$...$$`)

## Compiler le PDF (LaTeX)

```bash
cd reports
pdflatex RAPPORT_CHATBOT_JURIDIQUE.tex
pdflatex RAPPORT_CHATBOT_JURIDIQUE.tex   # 2e passage pour la table des matières
```

Ou avec `latexmk` :
```bash
latexmk -pdf RAPPORT_CHATBOT_JURIDIQUE.tex
```

## Prérequis

- Distribution LaTeX : TeX Live, MiKTeX, ou MacTeX
- Packages : `amsmath`, `amssymb`, `geometry`, `booktabs`, `hyperref`, `listings`, `babel`

## Exporter le Markdown en PDF (formules mathématiques respectées)

**Avec Docker** (recommandé si pandoc/LaTeX non installés) :
```bash
cd reports
docker run --rm --entrypoint "" \
  -v "$(pwd)":/data -w /data \
  pandoc/latex:latest \
  /usr/local/bin/pandoc RAPPORT_CHATBOT_JURIDIQUE_MATHEMATIQUES_ETENDU.md \
  -o RAPPORT_CHATBOT_JURIDIQUE_MATHEMATIQUES_ETENDU.pdf \
  --pdf-engine=xelatex \
  -V geometry:margin=2.5cm \
  -V fontsize=11pt \
  --toc \
  --number-sections
```

**Avec pandoc installé localement** :
```bash
cd reports
pandoc RAPPORT_CHATBOT_JURIDIQUE_MATHEMATIQUES_ETENDU.md \
  -o RAPPORT_CHATBOT_JURIDIQUE_MATHEMATIQUES_ETENDU.pdf \
  --pdf-engine=xelatex \
  -V geometry:margin=2.5cm \
  --toc \
  --number-sections
```

**Script fourni** : `./convert_md_to_pdf.sh` (nécessite pandoc + texlive-xetex)
