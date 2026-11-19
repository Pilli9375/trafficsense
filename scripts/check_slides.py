"""Check the capstone final-review deck (docs/ppt/TrafficSense_Capstone_Final_Review.pptx).

    python scripts/check_slides.py [--sizes]

Verifies: slide titles and order match the university template, at most 18 slides, every number on a
slide (and in its notes) appears in the report sources, no template placeholder text left, no phone
numbers, addresses, e-mails or photos, body text at least 16 pt, at most 5 bullets per slide, no text
overflowing its box, nothing overlapping the logo or the page number, speaker notes of 3 to 5 sentences
on every slide, the bibliography equal to the report's reference text, and the GitHub link on the last
slide. Exit status 1 if anything fails.
"""
import sys

from trafficsense.report import slides


def main():
    if "--sizes" in sys.argv:       # smallest text size on each slide
        for n, pt, where in slides.font_sizes():
            print(f"slide {n:2d}: smallest text {pt if pt else '-'} pt ({where})")
    probs = slides.check()
    for p in probs:
        print("FAIL", p)
    if probs:
        sys.exit(1)
    print("slides OK")


if __name__ == "__main__":
    main()
