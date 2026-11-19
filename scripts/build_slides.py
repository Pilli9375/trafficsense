"""Build the capstone final-review deck from the university template and the checked report sources.

    python scripts/build_slides.py            # docs/ppt/TrafficSense_Capstone_Final_Review.pptx + .pdf
    python scripts/build_slides.py --png      # also render every slide to docs/ppt/build/slide_NN.png

The template (paths.slides_template, never edited: the build works on a copy) is filled with text
from trafficsense.report.slides_content; every number on a slide is tagged and checked against
outputs/ by the report's own checker. The PDF is LibreOffice's conversion of the PPTX.
"""
import argparse
import shutil

from trafficsense.report import slides


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--png", action="store_true", help="also render each slide to a PNG in the work folder")
    args = ap.parse_args()
    template, work, out = slides.paths()
    pptx = slides.build()
    print(f"wrote {pptx}")
    pdf = slides.render_pdf(pptx, work)
    shutil.copyfile(pdf, pptx.with_suffix(".pdf"))
    print(f"wrote {pptx.with_suffix('.pdf')}")
    if args.png:
        for p in slides.render_pngs(pdf, work):
            pass
        print(f"rendered the slides to {work}")


if __name__ == "__main__":
    main()
