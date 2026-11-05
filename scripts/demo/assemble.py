"""Join recorded scenes into demo/demo.mp4 (H.264, 30 fps) and write demo/timestamps.md.

Input: demo/raw/manifest.json, a list of what scripts/demo/record_scene.js returned per scene:
  [{"scene": 1, "video": ".../demo/raw/abc.webm", "leadMs": 412, "seconds": 30}, ...]
Each clip is trimmed past its blank lead-in and cut to exactly `seconds`.

Usage: uv run python scripts/demo/assemble.py
"""

import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEMO = ROOT / "demo"
RAW = DEMO / "raw"
FPS = 30

ON_SCREEN = {
    1: 'Slide: "InvoiceGuard" and "Catch bad invoices first, automate clean ones second"',
    2: "Slide: three problems (invoice checking, ASU Surplus intake, pipeline failures), "
       "why invoices",
    3: "Slide: how it works: the model reads, software checks evidence and math, people decide",
    4: "Review desk overview: queue rail, PDF with evidence highlight, fields panel; "
       "shortcut sheet (?)",
    5: "Approved tab, Ironclad Security GmbH ($4,714.13), J through every field with its evidence",
    6: "Review tab, Harbourview Catering: invoice date 2026-10-05, due date 2026-11-04, S, "
       '"Approved. Added to eval set" toast',
    7: "Ironclad Security GmbH ($6,447.00): the prompt-injection reason",
    8: "Granite Network Systems: the arithmetic reason, then K to Tax and Subtotal",
    9: "Rejected tab, the shipping notice (doc_018): Not an invoice",
    10: "Evals page: cost per document vs review recall, then field accuracy by run",
    11: "Slide: three findings (2/6 -> 6/6, Sonnet 20x cost with no decision changed, 3 -> 0)",
    12: "Slide: the alternative, patterns only (0.879 fields, 11 of 16 auto-approved)",
    13: "Slide: git tags v0 to v4.1 and six lines of CLAUDE.md's working agreement",
    14: "Slide: what's mocked, limits, next steps, when I'd stop",
    15: "Slide: name, repo link, time spent",
}


def run(*args: str) -> None:
    subprocess.run(args, check=True, capture_output=True)


PAD_S = 3  # the browser starts capturing slightly after the context opens, so clips run short


def encode_scene(entry: dict, out: Path) -> None:
    """Skip the blank lead-in, then hold the last frame so the clip is exactly `seconds` long."""
    filters = f"tpad=stop_mode=clone:stop_duration={PAD_S},fps={FPS},scale=1920:1080,format=yuv420p"
    run("ffmpeg", "-y", "-i", entry["video"], "-ss", f"{entry['leadMs'] / 1000:.3f}",
        "-vf", filters, "-t", str(entry["seconds"]),
        "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-an", str(out))


def stamp(seconds: int) -> str:
    return f"{seconds // 60}:{seconds % 60:02d}"


def main() -> None:
    manifest = sorted(json.loads((RAW / "manifest.json").read_text()), key=lambda e: e["scene"])
    clips, start, rows = [], 0, []
    for entry in manifest:
        clip = RAW / f"scene_{entry['scene']:02d}.mp4"
        encode_scene(entry, clip)
        clips.append(clip)
        rows.append(f"| {stamp(start)} | {entry['scene']} | {entry['seconds']}s | "
                    f"{ON_SCREEN[entry['scene']]} |")
        start += entry["seconds"]
    concat = RAW / "concat.txt"
    concat.write_text("".join(f"file '{c}'\n" for c in clips))
    run("ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(concat), "-c", "copy",
        str(DEMO / "demo.mp4"))
    (DEMO / "timestamps.md").write_text(
        "# Demo timestamps\n\n| Start | Scene | Length | On screen |\n|---|---|---|---|\n"
        + "\n".join(rows) + f"\n\nTotal: {stamp(start)}\n")
    print(f"Wrote {DEMO / 'demo.mp4'} ({stamp(start)}) and {DEMO / 'timestamps.md'}")


if __name__ == "__main__":
    main()
