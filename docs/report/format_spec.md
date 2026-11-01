# Thesis format specification

The college capstone thesis format, read from the example thesis the college gave us
(`paths.thesis_format` in `configs/default.yaml`; the file stays on D: and out of git). We follow
its **format and structure**, none of its content. `scripts/check_report_format.py` checks the
built `report.docx` against this file.

Each rule says where it comes from: **[format]** is measured from the example's XML
(`word/document.xml`, `styles.xml`, `footer2.xml`); **[ours]** is a choice we made where the
example is silent, inconsistent, or has an obvious artefact; the reason is given.

## Page

| Item | Rule | Source |
|---|---|---|
| Paper | US Letter, 21.59 x 27.94 cm (12240 x 15840 twips), portrait | [format] both sections |
| Margins | top 2.54 cm, bottom 1.50 cm, left 3.175 cm, right 3.175 cm (1440 / 851 / 1800 / 1800 twips) for the **whole report** | [format] section 1 |
| Header / footer distance | 1.27 cm each (720 twips) | [format] |
| Text block | 15.24 cm wide, 23.9 cm high | follows from the above |
| Binding gutter | none | [format] `gutter="0"` |

The example's second section (certificate onwards) has top 0.25 cm, right 1.9 cm, bottom 2.2 cm,
left 3.0 cm. A 0.25 cm top margin is an artefact (text touches the paper edge), so we use the
first section's margins throughout. Because the footer (1.27 cm) is taller than the 1.50 cm bottom
margin leaves room for, Word and LibreOffice push the last body line up to clear the page number;
that is expected and matches the example.

Wide tables that do not fit 15.24 cm at 10 pt are set at 9 pt; if still too wide they go on a
landscape page (same margins rotated). [ours]

## Fonts and paragraphs

| Element | Rule | Source |
|---|---|---|
| Body text | Times New Roman 12 pt, line spacing 1.5 (`line=360 auto`), justified, first-line indent 0.5 in (1.27 cm) | [format] body paragraphs |
| Paragraph spacing | 0 pt before, 12 pt after (one blank line) | [ours]: the example separates paragraphs with empty paragraphs; we use space-after instead so there are no empty paragraphs |
| First paragraph after a heading | same as body (indented) | [format] |
| Bulleted / numbered lists | 1.5 spacing, justified, indent 0.5 in, hanging 0.25 in, no first-line indent | [format] objectives list |
| Tables | Table Grid (single 0.5 pt black borders), Times New Roman 10 pt, single spacing, header row bold and repeated on each page | [format] `TableGrid` style (10 pt) and the cost table |
| Table breaks | no row splits across pages; a table of up to 20 rows stays on one page with its caption; 12 pt of space after every table | [ours] |
| Code listings | Consolas 8.5 pt, single spacing, left aligned, no indent, light border | [ours]: the example sets its code in Times New Roman 12 (code columns do not line up); you asked for monospaced |
| Footnotes | not used | [format] none |
| Every other text | Times New Roman | [ours]: the example mixes in Verdana on the certificate page; treated as an artefact |

The PDF is rendered with the real Times New Roman and Consolas (and Symbol for bullets) read in
place from the Windows font folder, `paths.report_fonts` (nothing copied or installed); the build
fails if they are missing. Equations are the one exception: LibreOffice converts Word equations
into its own formula objects, which it sets in its own formula fonts (Liberation Serif,
OpenSymbol) whatever the document says; Word shows the same equations in Cambria Math.

## Headings

| Level | Look | Example | Source |
|---|---|---|---|
| Chapter (Heading 1) | two centred lines, bold, 14 pt, capitals: `CHAPTER n` then the title; starts a new page | `CHAPTER 1` / `INTRODUCTION` | [format] |
| Section (Heading 2) | `n.m Title`, bold 14 pt, left, title case | `1.1 Objectives` | [format] (14 pt is the example's usual section size) |
| Subsection (Heading 3) | `n.m.k Title`, bold 13 pt, left | `2.4.1 Software Details` | [format] (the example's 2.4.2 is 13 pt) |
| Deeper levels | bold 12 pt run-in paragraph, unnumbered, not in the contents | | [ours]: the example has three levels |
| Front-matter titles | centred, bold 14 pt, capitals, new page: CERTIFICATE, ACKNOWLEDGEMENTS, ABSTRACT, TABLE OF CONTENTS, LIST OF TABLES, LIST OF FIGURES; also REFERENCES and BIODATA | | [format] layout; the example mixes 12/14 pt and "List of Tables" in title case, unified here [ours] |

Numbering is decimal, `n.m` and `n.m.k`, no trailing full stop, a space between number and title
[format]. All headings keep with the next paragraph (no heading alone at a page foot) [ours].
Headings are real Word heading styles (Heading 1-3, Times New Roman, black), so the contents is a
live field; the example's own heading styles are Calibri Light blue and unused, so we redefine
them.

## Captions

| Item | Rule | Source |
|---|---|---|
| Figure caption | **below** the figure, centred, Caption style (Times New Roman 10 pt bold), text `Figure n Title`, `n` a `SEQ Figure` field numbered **continuously through the whole report** (1, 2, 3, ... across chapters) | [format] `Figure 1 Automobile Sales`, `SEQ Figure \* ARABIC` |
| Caption title and note | the title is short, as in the format; our longer explanation of a figure or table follows directly below the title in 10 pt regular ("Caption Note"), so no caption text is dropped | [ours] |
| Table caption | **above** the table, Caption style, text `Table c.n Title` (`c` = chapter, `n` restarts in each chapter: `SEQ Table`, with `\r 1` on a chapter's first table, because LibreOffice ignores `\s 1`) | [format] `Table 3.1 List of components and their costs` |
| Figure size | centred, at most 15.24 cm wide, kept on the same page as its caption | [format] / [ours] |
| Text references | "Figure 4", "Table 4.2" (same words as the captions) | [format] |

Appendix tables are numbered as Chapter 6 (`Table 6.n`) because the appendix is Chapter 6 in the
format.

## Header, footer and page numbers

| Item | Rule | Source |
|---|---|---|
| Header | empty | [format] `header1.xml` is an empty paragraph |
| Footer | page number centred, Times New Roman 12 pt, `PAGE` field | [format] `footer2.xml` (default footer) |
| Front matter (title page to List of Figures) | lower-case roman (i, ii, iii, ...); the title page counts as i but shows no number | [format] section 1 `pgNumType fmt=lowerRoman` + `titlePg` |
| Body (Chapter 1 to the last page) | Arabic, restarting at 1 on the first page of Chapter 1 | as you specified |

Deviation from the example, as you asked: in the example only the title page is roman; the
certificate onwards is Arabic from 1, so Chapter 1 starts on page 7. We use roman for all the
front matter and Arabic from Chapter 1. Biodata and the NOTE page continue the Arabic numbering
[format].

## Section order

Each item starts on a new page. Roman-numbered front matter:

1. **Title page** [format layout, all centred]: title bold 16 pt; `A CAPSTONE PROJECT REPORT`
   bold 12; `Capstone Project ID: 3328F4C8 · Fall Semester 2026-27` 12 pt (directly under the
   report line; [ours], the format has no slot for it); *Submitted in partial fulfillment of the /
   requirement for the award of the / Degree of* italic 12; `BACHELOR OF TECHNOLOGY` / `IN` /
   `COMPUTER SCIENCE AND ENGINEERING` bold 12; *by* italic; the four `NAME (REG. NO.)` lines bold
   14; *Under the Guidance of* italic; `DR. MOHD IRFAN` bold 12; VIT-AP logo (6.9 x 2.1 cm, taken
   from the college file at build time, not kept in git as a file); `SCHOOL OF COMPUTER SCIENCE
   AND ENGINEERING` / `VIT-AP UNIVERSITY` / `AMARAVATI- 522237` 14 pt; *NOVEMBER 2026* italic 14.
2. **Certificate**: the example's certificate wording with our title, the four students and
   register numbers, and "Bachelor of Technology in Computer Science and Engineering"; right
   aligned signature line, `Dr. Mohd Irfan`, `Guide`; centred bold `The thesis is satisfactory /
   unsatisfactory`; signature lines for `Internal Examiner` (left) and `External Examiner`
   (right); centred bold `Approved by`; `PROGRAM CHAIR` (left) and `DEAN` (right), each with a
   blank name line and signature line, then `B. Tech. CSE` (left, italic) and `School of Computer
   Science and Engineering` (right, italic).
3. **Acknowledgements** (TOC entry)
4. **Abstract**, one page (TOC entry)
5. **Table of Contents**: a live `TOC` field built from hidden `TC` entries (so a chapter reads
   `1 Introduction`, as in the format, although its heading has two lines). Entries:
   Acknowledgements, Abstract, List of Tables, List of Figures, every chapter, sections and
   subsections to level 3, References, Biodata; dotted leader, right-aligned page number. The
   example's contents is a hand-made 4-column table; a live field cannot be a table.
6. **List of Tables**: live `TOC \c "Table"` field, `Table c.n Title .... page`.
7. **List of Figures**: live `TOC \c "Figure"` field, `Figure n Title .... page`.

Arabic-numbered body:

8. **Chapter 1 Introduction**: 1.1 Objectives, 1.2 Background and Literature Survey, 1.3
   Organization of the Report, 1.4 Team Contributions (Table 1.1).
9. **Chapter 2 Proposed System and Methodology**: 2.1 Proposed System, 2.2 Working Methodology,
   2.3 Standards, 2.4 System Details, 2.4.1 Software Details, 2.4.2 Hardware Details.
10. **Chapter 3 Cost Analysis**: 3.1 List of Components and Their Cost (Table 3.1).
11. **Chapter 4 Results and Discussions**
12. **Chapter 5 Conclusion and Future Work**
13. **Chapter 6 Appendix**
14. **References**: unnumbered heading, entries `[1] ...` in order of first citation, IEEE style,
    hanging indent [format].
15. **Biodata**: one page per student [format layout]: centred bold 14 pt `BIODATA`; a bordered
    3.5 x 4.5 cm box (a passport photo; the example's box is 3.3 x 2.8 cm) labelled `Photo` at the
    left; to its right `Name :`, `Register No. :`,
    `Mobile Number :`, `E-mail :`, `Permanent Address :` (the example spells it "Permanaent";
    corrected). Mobile number and address are blank underlined lines to be filled by hand.
16. **NOTE page**: the example's NOTE, bold 18 pt, with `MANDATORY` in red as in the example; the
    typo "Its" is corrected to "It is": "NOTE: It is MANDATORY for a student to attach all the PPT's, Sample
    Materials, Specification Sheets, Programming Codes and a 5-10 minutes demo Video of the
    Project Digitally In CD. Stick the Compact Disk (CD) in the final page of the Thesis after
    binding it."

Not in the format, so not in the report: the Declaration page and the List of Abbreviations as
front matter (the abbreviations move into the appendix).

## Blank lines (for handwriting)

A blank is a run of underlined tab or underscore characters that is real, editable text, with its
label in front (`Mobile Number : ________`), as on a printed form. Used for: signatures (guide,
internal and external examiner, program chair, dean), the program chair's and dean's names, and
each student's mobile number and permanent address (two lines). The report never contains `{{`,
`}}`, `TBD`, `[fill in]` or invented names, numbers or addresses.

## Fields

The Word file asks to update fields when opened (`w:updateFields` in `settings.xml`). Before that,
every field already shows correct values: the build converts the `.docx` to PDF with LibreOffice,
reads the page of every heading and caption from the PDF, writes those page numbers into the
fields' stored results, and converts again; the published PDF is that second conversion of the
same `.docx`.
