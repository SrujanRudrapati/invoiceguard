"""Retime the demo to narration and mux: demo/final.mp4 (H.264 30 fps, AAC 192k, -16 LUFS).

Inputs
  demo/audio/sceneNN.mp3            narration, one clip per scene
  demo/scene_plan.json              scene lengths (clip + 0.5 s lead-in + 1.0 s tail, frame-rounded)
  demo/raw/scene_NN.mp4             slide scenes from the first cut (trimmed to the new length)
  demo/raw/retime_manifest.json     app scenes 4-10 re-recorded on narration cues (raw webm)

App clips start on the first frame after the magenta sync marker (see record_scene.js), so
cue times are exact on screen. Narration starts 0.5 s into its scene and is never cut.

Usage: uv run python scripts/demo/narrate.py
"""

import json
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEMO = ROOT / "demo"
RAW = DEMO / "raw"
PARTS = DEMO / "final_parts"
FPS = 30
LEAD_IN_MS = 500
SCAN_FPS = 100  # marker search resolution (10 ms)
SCAN_SECONDS = 10
APP_SCENES = range(4, 11)
LOUDNESS = "I=-16:TP=-1.5:LRA=11"

ON_SCREEN = {
    1: 'Slide: "InvoiceGuard" and "Catch bad invoices first, automate clean ones second"',
    2: "Slide: three problems (invoice checking, ASU Surplus intake, pipeline failures), "
       "why invoices",
    3: "Slide: how it works: the model reads, software checks evidence and math, people decide",
    4: "Review desk overview: queue rail, PDF with evidence highlight, fields panel",
    5: "Approved tab: Ironclad Security GmbH ($4,714.13) opens at 0.5 s; J from 4.2 s to "
       "18.5 s through every field to Total",
    6: "Harbourview Catering opens at 0.5 s; invoice date 2026-10-05 at 15.5 s, due date "
       '2026-11-04 at 18.1 s, S at 20.7 s; "Approved. Added to eval set" toast to the end',
    7: "Ironclad Security GmbH ($6,447.00) opens at 0.5 s: the prompt-injection reason",
    8: "Granite Network Systems opens at 0.5 s: the arithmetic reason",
    9: "Rejected tab: the shipping notice (doc_018) opens at 0.5 s: Not an invoice",
    10: "Evals page at 0.5 s; cost vs recall chart from 11.1 s; field accuracy by run from 23.9 s",
    11: "Slide: three findings (2/6 -> 6/6, Sonnet 20x cost with no decision changed, 3 -> 0)",
    12: "Slide: the alternative, patterns only (0.879 fields, 11 of 16 auto-approved)",
    13: "Slide: git tags v0 to v4.1 and six lines of CLAUDE.md's working agreement",
    14: "Slide: what's mocked, limits, next steps, when I'd stop",
    15: "Slide: name, repo link, time spent",
}


def run(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(args, check=True, capture_output=True, text=True)


def duration(path: Path) -> float:
    out = run("ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0",
              str(path)).stdout
    return float(out)


def marker_end(video: str) -> float:
    """Seconds into the raw video of the first frame after the magenta sync marker."""
    raw = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", video, "-t", str(SCAN_SECONDS),
         "-vf", f"fps={SCAN_FPS},crop=12:12:6:6,scale=1:1", "-f", "rawvideo",
         "-pix_fmt", "rgb24", "-"], check=True, capture_output=True).stdout
    frames = [raw[i:i + 3] for i in range(0, len(raw), 3)]
    magenta = [i for i, (r, g, b) in enumerate(frames) if r > 200 and g < 90 and b > 200]
    if not magenta:
        raise RuntimeError(f"no sync marker in {video}")
    return (magenta[-1] + 1) / SCAN_FPS


def encode_video(src: str, start: float, seconds: float, out: Path) -> None:
    """Cut [start, start + seconds], holding the last frame if the source runs short."""
    filters = f"tpad=stop_mode=clone:stop_duration=3,fps={FPS},scale=1920:1080,format=yuv420p"
    run("ffmpeg", "-y", "-i", src, "-ss", f"{start:.3f}", "-vf", filters, "-t", f"{seconds:.4f}",
        "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-an", str(out))


def build_video(plan: list[dict], app_raw: dict[str, str]) -> tuple[Path, dict[int, float]]:
    clips, cuts = [], {}
    for scene in plan:
        n, out = scene["scene"], PARTS / f"v{scene['scene']:02d}.mp4"
        if n in APP_SCENES:
            cuts[n] = marker_end(app_raw[str(n)])
            encode_video(app_raw[str(n)], cuts[n], scene["seconds"], out)
        else:
            encode_video(str(RAW / f"scene_{n:02d}.mp4"), 0.0, scene["seconds"], out)
        clips.append(out)
    concat = PARTS / "video_concat.txt"
    concat.write_text("".join(f"file '{c}'\n" for c in clips))
    video = PARTS / "video.mp4"
    run("ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(concat), "-c", "copy", str(video))
    return video, cuts


def build_audio(plan: list[dict]) -> Path:
    """Each clip delayed 0.5 s and padded with silence to its scene length, then joined."""
    inputs, chains = [], []
    for i, scene in enumerate(plan):
        inputs += ["-i", str(DEMO / "audio" / f"scene{scene['scene']:02d}.mp3")]
        chains.append(f"[{i}:a]aresample=48000,aformat=channel_layouts=mono,"
                      f"adelay={LEAD_IN_MS}:all=1,apad=whole_dur={scene['seconds']:.4f},"
                      f"atrim=0:{scene['seconds']:.4f}[a{i}]")
    joined = "".join(f"[a{i}]" for i in range(len(plan)))
    graph = ";".join(chains) + f";{joined}concat=n={len(plan)}:v=0:a=1[out]"
    wav = PARTS / "narration.wav"
    run("ffmpeg", "-y", *inputs, "-filter_complex", graph, "-map", "[out]", "-c:a", "pcm_s16le",
        str(wav))
    return wav


def loudnorm(wav: Path) -> Path:
    """Two-pass EBU R128 normalisation to -16 LUFS, encoded as AAC 192 kbps."""
    first = subprocess.run(["ffmpeg", "-i", str(wav), "-af",
                            f"loudnorm={LOUDNESS}:print_format=json", "-f", "null", "-"],
                           capture_output=True, text=True, check=True).stderr
    m = json.loads(re.search(r"\{[^{}]*\"input_i\"[^{}]*\}", first, re.S).group(0))
    second = (f"loudnorm={LOUDNESS}:measured_I={m['input_i']}:measured_TP={m['input_tp']}:"
              f"measured_LRA={m['input_lra']}:measured_thresh={m['input_thresh']}:"
              f"offset={m['target_offset']}:linear=true,aresample=48000")
    out = PARTS / "narration.m4a"
    run("ffmpeg", "-y", "-i", str(wav), "-af", second, "-c:a", "aac", "-b:a", "192k", str(out))
    return out


def stamp(seconds: float) -> str:
    return f"{int(seconds // 60)}:{seconds % 60:04.1f}"


def main() -> None:
    PARTS.mkdir(exist_ok=True)
    plan = json.loads((DEMO / "scene_plan.json").read_text())
    app_raw = json.loads((RAW / "retime_manifest.json").read_text())
    video, cuts = build_video(plan, app_raw)
    audio = loudnorm(build_audio(plan))
    final = DEMO / "final.mp4"
    run("ffmpeg", "-y", "-i", str(video), "-i", str(audio), "-map", "0:v", "-map", "1:a",
        "-c", "copy", "-movflags", "+faststart", str(final))
    total = sum(s["seconds"] for s in plan)
    rows = [f"| {stamp(s['start'])} | {s['scene']} | {s['clip']:.2f}s | {s['seconds']:.2f}s | "
            f"{ON_SCREEN[s['scene']]} |" for s in plan]
    (DEMO / "timestamps.md").write_text(
        "# Demo timestamps (narrated cut, demo/final.mp4)\n\n"
        "Narration starts 0.5 s into each scene; each scene ends 1.0 s after its narration.\n\n"
        "| Start | Scene | Narration | Scene length | On screen |\n|---|---|---|---|---|\n"
        + "\n".join(rows) + f"\n\nTotal: {stamp(total)}\n")
    print(json.dumps({"final": str(final), "total": round(total, 4),
                      "video_s": duration(video), "audio_s": duration(audio),
                      "final_s": duration(final), "app_cuts_s": cuts}, indent=1))


if __name__ == "__main__":
    main()
