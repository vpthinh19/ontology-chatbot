# Reference PDF OCR Conversion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Convert every image-only PDF in `references/` to faithful Markdown using OCR, and re-parse Decisions 729 and 1052 to validate and correct their existing Markdown files.

**Architecture:** Render every PDF page to a high-resolution image, run Vietnamese and English OCR on the rendered pages, then reconstruct headings, numbered clauses, lists, and tables in one Markdown file per PDF. Keep raster images and raw OCR output in a temporary directory so only the final Markdown files remain in the repository.

**Tech Stack:** Poppler `pdftoppm`, Tesseract OCR 5 with `vie+eng`, Markdown, shell validation commands

## Global Constraints

- OCR is mandatory because the PDFs are scans of paper documents.
- Process `references/Qd317.pdf`, `references/Qd500.pdf`, `references/Qd729.pdf`, and `references/Qd1052.pdf`.
- Create Markdown for Decisions 317 and 500.
- Re-parse Decisions 729 and 1052 from their PDFs and correct the existing Markdown when the OCR/page image shows a discrepancy.
- Preserve Vietnamese diacritics, document numbering, article numbering, monetary values, tables, and appendices.
- Do not alter unrelated existing workspace changes.

---

### Task 1: Build the OCR evidence set

**Files:**
- Read: `references/Qd317.pdf`
- Read: `references/Qd500.pdf`
- Read: `references/Qd729.pdf`
- Read: `references/Qd1052.pdf`
- Create temporarily: `/tmp/ontology-chatbot-ocr/<document>/page-*.png`
- Create temporarily: `/tmp/ontology-chatbot-ocr/<document>/page-*.txt`

**Interfaces:**
- Consumes: the four image-only PDFs and Tesseract `vie+eng` language data
- Produces: page images and page-aligned raw OCR text for all 57 pages

- [ ] **Step 1: Verify the PDF inventory and page counts**

Run: `for f in references/*.pdf; do pdfinfo "$f" | sed -n '/^Pages:/p'; done`

Expected: Qd317 has 2 pages, Qd500 has 19, Qd729 has 6, and Qd1052 has 30.

- [ ] **Step 2: Render every page at OCR resolution**

Run for each document: `pdftoppm -r 300 -png references/QdNNN.pdf /tmp/ontology-chatbot-ocr/QdNNN/page`

Expected: one PNG per PDF page, with the same count reported by `pdfinfo`.

- [ ] **Step 3: OCR every rendered page**

Run for each page: `tesseract page-NN.png page-NN -l vie+eng --psm 6 preserve_interword_spaces=1`

Expected: a non-empty UTF-8 text file for every rendered page.

- [ ] **Step 4: Spot-check OCR against page images**

Inspect the first page, every table-heavy page, and the last page of each document. Correct errors involving decision numbers, dates, article numbers, quantities, and Vietnamese diacritics during Markdown reconstruction.

### Task 2: Create Markdown for Decisions 317 and 500

**Files:**
- Create: `references/Qd317.md`
- Create: `references/Qd500.md`

**Interfaces:**
- Consumes: page images and raw OCR text from Task 1
- Produces: readable, source-faithful Markdown transcriptions for both decisions

- [ ] **Step 1: Reconstruct Decision 317**

Use headings for the issuing authority, decision title, and articles; retain numbered paragraphs and signature/recipient information that is legible in the scan.

- [ ] **Step 2: Reconstruct Decision 500**

Use headings for chapters and articles, numbered Markdown lists for clauses, and Markdown tables where rows and columns are semantically significant.

- [ ] **Step 3: Validate coverage**

Run: `rg -n '^#{1,6} |^\*\*Điều [0-9]+|^#### Điều [0-9]+' references/Qd317.md references/Qd500.md`

Expected: all decision titles, chapters, articles, and appendices visible in the scans are represented in order.

### Task 3: Validate and correct Decisions 729 and 1052

**Files:**
- Modify: `references/Qd729.md`
- Modify: `references/Qd1052.md`

**Interfaces:**
- Consumes: existing Markdown plus independent OCR/page-image evidence from Task 1
- Produces: corrected Markdown whose content and structure match the scans

- [ ] **Step 1: Compare Decision 729 page by page**

Check all six pages, especially the split tuition table, values expressed as `đ/TC` or `đ/năm`, cohort applicability, and both appendices. Update only discrepancies supported by the page image.

- [ ] **Step 2: Compare Decision 1052 page by page**

Check all 30 pages, including the table of contents, Articles 1–32, appendix headings, score-conversion tables, form codes, and page-boundary continuations. Update only discrepancies supported by the page image.

- [ ] **Step 3: Scan for common OCR residue**

Run: `rg -n '\| 0 \||\| 1 \||Số:.* /|\b[lI]0[0-9]{2}\b|�' references/Qd729.md references/Qd1052.md`

Expected: every match is either corrected from the scan or confirmed as genuine source text.

### Task 4: Verify the final deliverables

**Files:**
- Verify: `references/Qd317.md`
- Verify: `references/Qd500.md`
- Verify: `references/Qd729.md`
- Verify: `references/Qd1052.md`

**Interfaces:**
- Consumes: the four final Markdown files and their OCR/page-image evidence
- Produces: an evidence-backed completion report

- [ ] **Step 1: Verify all expected Markdown files exist and are non-empty**

Run: `test -s references/Qd317.md && test -s references/Qd500.md && test -s references/Qd729.md && test -s references/Qd1052.md`

Expected: exit status 0.

- [ ] **Step 2: Verify UTF-8 and basic Markdown integrity**

Run: `file references/Qd{317,500,729,1052}.md && rg -n '�|^<<<<<<<|^=======|^>>>>>>>' references/Qd{317,500,729,1052}.md`

Expected: files are UTF-8 text and contain no replacement characters or conflict markers.

- [ ] **Step 3: Run source-fidelity tests**

Run: `UV_CACHE_DIR=/tmp/ontology-chatbot-uv-cache uv run pytest tests/ontology/test_source_fidelity.py -q`

Expected: all source-fidelity tests pass; if the test suite does not yet cover Qd317/Qd500, also report the page-by-page checks performed above.

