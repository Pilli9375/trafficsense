"""Checks for the report's private Biodata pages (src/trafficsense/report/biodata.py).

    python scripts/check_biodata.py              # both checks below
    python scripts/check_biodata.py --personal   # the personal build only
    python scripts/check_biodata.py --leaks      # the tracked-files search only
    python scripts/check_biodata.py --require    # a missing private file is an error, not a skip

--personal: docs/report/build_private/report_personal.docx and .pdf have four biodata pages in
  the order of the title page, each with the student's name, register number, 10-digit phone,
  e-mail, address and the right photo, nothing blank; and the same page count and the same
  contents/list page numbers as the public docs/report/report.docx and .pdf.
--leaks: no git-tracked file contains any student's phone number, e-mail address, home address or
  photo (searched as text, inside .docx/.zip files, in the text of PDFs, and among tracked images).

Both need the private file (paths.biodata). Without it they print that they were skipped and exit 0
(there is nothing to search for), or exit 1 with --require. The private details are never printed.
"""
import argparse
import sys

from trafficsense.config import load_config, repo_root, resolve_path
from trafficsense.report import biodata

ROOT = repo_root()


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--personal", action="store_true")
    ap.add_argument("--leaks", action="store_true")
    ap.add_argument("--require", action="store_true", help="a missing private file fails instead of skipping")
    args = ap.parse_args()
    both = not (args.personal or args.leaks)
    cfg = load_config("configs/default.yaml")
    students, why = biodata.load_optional(resolve_path(cfg, "biodata"), resolve_path(cfg, "biodata_photos"))
    if students is None:
        print(f"SKIPPED: {why}; there is nothing to check against")
        sys.exit(1 if args.require else 0)
    errors = []
    if args.personal or both:
        priv = resolve_path(cfg, "report_private")
        pair = (priv / "report_personal.docx", priv / "report_personal.pdf")
        for f in pair:
            if not f.is_file():
                errors.append(f"{f.relative_to(ROOT)} not found: run scripts/build_report.py first")
        if not errors:
            errors += biodata.check_personal(*pair, students)
            errors += biodata.compare_with_public(pair, (ROOT / "docs/report/report.docx", ROOT / "docs/report/report.pdf"))
            if not errors:
                print(f"personal build: {len(students)} biodata pages complete (name, register number, 10-digit phone, "
                      f"e-mail, address, photo); page count and contents/lists match the public report "
                      f"({biodata.pdf_page_count(pair[1])} pages)")
    if args.leaks or both:
        leaks, n = biodata.check_no_leaks(ROOT, students)
        errors += leaks
        if not leaks:
            print(f"no leaks: none of the {len(students)} students' phone numbers, e-mails, addresses or photos "
                  f"is in any of the {n} git-tracked files")
    if errors:
        print("\n".join(errors))
        print(f"{len(errors)} problem(s)")
        sys.exit(1)


if __name__ == "__main__":
    main()
