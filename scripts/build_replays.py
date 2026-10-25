"""Regenerate the Network Replay page's data from the committed runs, in one command.

    python scripts/build_replays.py           # make missing or stale replays, then check them all
    python scripts/build_replays.py --force   # make every replay again

For a fresh clone or another laptop: the replays (about 15 MB) are not in git, so this rebuilds
them from what is: each run's summary.json, and decisions.jsonl for LLM runs. No LLM is called.
Deterministic runs are simulated again, LLM runs are replayed from their logged decisions, and
every replay must reproduce its run's metrics exactly or the script fails.

paths.replays (configs/default.yaml) is data/external/replays. If it does not exist it is
created as a plain folder inside the clone. If you keep the replays elsewhere (on D, say),
create that symlink first. A symlink whose target is missing is an error, not a silent new folder.

This is a wrapper around make_replays.py (selection check, replay, then make_replays.py --check).
It needs a clean git tree, because each replay's meta.json records the commit.
"""
import argparse
import subprocess
import sys
from pathlib import Path

from trafficsense.config import load_config, resolve_path


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--force", action="store_true", help="make every replay again")
    args = ap.parse_args()
    out = resolve_path(load_config("configs/default.yaml"), "replays")
    if out.is_symlink() and not out.exists():
        raise SystemExit(f"{out} is a symlink to {out.readlink()}, which does not exist. "
                         "Create the target folder or remove the symlink, then run again.")
    if not out.exists():
        out.mkdir(parents=True)
        print(f"created {out}")
    make = Path(__file__).resolve().parent / "make_replays.py"
    subprocess.run([sys.executable, str(make)] + (["--force"] if args.force else []), check=True)
    sys.exit(subprocess.run([sys.executable, str(make), "--check"]).returncode)


if __name__ == "__main__":
    main()
