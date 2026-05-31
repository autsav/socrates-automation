"""
Beat Sync — detects energy peaks in audio and aligns Reel transitions to them.

Uses ffmpeg ebur128 + volumedetect filters (zero Python dependencies).
Falls back to fixed timing if no clear peaks are found.

Research: Reels with beat-synced cuts have 20-30% higher completion rates.
"""

import subprocess
import re
from pathlib import Path

# Mood → xfade transition type mapping
# ffmpeg 4.4+ supports: fade, wipe*, slide*, smooth*, circle*, vert*, horz*,
# diag*, *slice, hblur, dissolve, pixelize, radial, cube*, swap*, flip*
TRANSITION_TYPES = {
    "calm_stoic":         "fade",        # gentle, unobtrusive
    "cinematic_hopeful":  "smoothup",    # uplifting
    "dark_philosophical": "pixelize",    # edgy, modern
    "dramatic_ancient":   "distance",     # epic, dramatic
    "epic_warrior":       "slideup",      # energetic
    "mystical_greek":     "fadewhite",    # ethereal — fade to white
    "stark_minimal":      "wipeleft",     # clean, minimal
}

# Default fixed timing (fallback)
DEFAULT_SCENE_DURATIONS = [4.0, 8.0, 3.0]
DEFAULT_TRANSITION_DURATION = 0.5


def _parse_ebur128(stderr_text: str) -> list[tuple[float, float]]:
    """
    Parse ffmpeg ebur128 momentary loudness output.
    Returns list of (timestamp_seconds, loudness_lufs) tuples.
    """
    readings = []
    # ebur128 prints lines like: "  t: 0.4    M:-23.4 S:-23.4     I: -23.4 LUFS"
    pattern = re.compile(r"t:\s*([\d.]+)\s+M:\s*([-\d.]+)")
    for line in stderr_text.splitlines():
        match = pattern.search(line)
        if match:
            t = float(match.group(1))
            lufs = float(match.group(2))
            readings.append((t, lufs))
    return readings


def _find_peaks(
    readings: list[tuple[float, float]],
    min_peak_distance: float = 1.2,
    threshold_percentile: float = 0.75,
) -> list[float]:
    """
    Find local maxima in loudness curve that are above a percentile threshold.
    Filters peaks that are at least `min_peak_distance` seconds apart.
    """
    if len(readings) < 3:
        return []

    # Sort by loudness to find threshold
    loudness_values = [l for _, l in readings]
    loudness_values.sort()
    threshold_idx = int(len(loudness_values) * threshold_percentile)
    threshold = loudness_values[min(threshold_idx, len(loudness_values) - 1)]

    peaks = []
    for i in range(1, len(readings) - 1):
        prev_t, prev_l = readings[i - 1]
        curr_t, curr_l = readings[i]
        next_t, next_l = readings[i + 1]

        # Local maximum above threshold
        if curr_l > threshold and curr_l > prev_l and curr_l > next_l:
            # Check min distance from last peak
            if not peaks or (curr_t - peaks[-1]) >= min_peak_distance:
                peaks.append(curr_t)

    return peaks


def detect_energy_peaks(
    audio_path: Path,
    min_peak_distance: float = 1.2,
) -> list[float]:
    """
    Detect energy peaks (beats/drops) in an audio file using ffmpeg ebur128.
    Returns list of timestamps in seconds.

    Args:
        audio_path: Path to MP3 or other audio file
        min_peak_distance: Minimum seconds between detected peaks
    """
    if not audio_path.exists():
        return []

    cmd = [
        "ffmpeg", "-y",
        "-i", str(audio_path),
        "-af", "ebur128=peak=true",
        "-f", "null",
        "-",
    ]

    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=30
        )
    except Exception:
        return []

    # ebur128 outputs readings to stderr
    readings = _parse_ebur128(result.stderr)
    if not readings:
        return []

    peaks = _find_peaks(readings, min_peak_distance=min_peak_distance)
    return peaks


def calculate_synced_offsets(
    peaks: list[float],
    target_total: float = 14.0,
    transition_duration: float = 0.5,
    min_scene_dur: tuple[float, float, float] = (2.0, 4.0, 2.0),
    max_scene_dur: tuple[float, float, float] = (6.0, 12.0, 5.0),
) -> tuple[list[float], list[float], bool]:
    """
    Given detected peaks, return optimal scene durations and transition offsets.

    Args:
        peaks: List of peak timestamps (seconds)
        target_total: Target total reel duration
        transition_duration: Crossfade duration
        min_scene_dur: Minimum duration for [hook, quote, cta]
        max_scene_dur: Maximum duration for [hook, quote, cta]

    Returns:
        (scene_durations, transition_offsets, used_beats)
        scene_durations: [hook_dur, quote_dur, cta_dur]
        transition_offsets: [offset_1, offset_2] for xfade
        used_beats: True if peaks influenced timing, False if fallback
    """
    if len(peaks) < 2:
        # Not enough peaks — use default timing
        hook_dur, quote_dur, cta_dur = DEFAULT_SCENE_DURATIONS
        offset_1 = hook_dur - transition_duration
        offset_2 = hook_dur + quote_dur - 2 * transition_duration
        return (
            [hook_dur, quote_dur, cta_dur],
            [offset_1, offset_2],
            False,
        )

    # Use first peak for hook→quote transition, second for quote→CTA
    peak_1 = peaks[0]
    peak_2 = peaks[1] if len(peaks) > 1 else peaks[0] + 5.0

    # Ensure peaks are within reasonable bounds
    peak_1 = max(min_scene_dur[0] + transition_duration, peak_1)
    peak_1 = min(max_scene_dur[0], peak_1)

    peak_2 = max(peak_1 + min_scene_dur[1] + transition_duration, peak_2)
    peak_2 = min(peak_1 + max_scene_dur[1], peak_2)

    # Ensure total doesn't exceed target
    max_end = peak_2 + max_scene_dur[2]
    if max_end > target_total:
        # Compress proportionally
        excess = max_end - target_total
        peak_2 -= excess * 0.6
        peak_1 -= excess * 0.3

    hook_dur = peak_1
    quote_dur = peak_2 - peak_1 + transition_duration
    cta_dur = max(target_total - peak_2, min_scene_dur[2])
    cta_dur = min(cta_dur, max_scene_dur[2])

    # Clamp to minimums
    hook_dur = max(hook_dur, min_scene_dur[0])
    quote_dur = max(quote_dur, min_scene_dur[1])
    cta_dur = max(cta_dur, min_scene_dur[2])

    # Recalculate offsets for xfade
    offset_1 = hook_dur - transition_duration
    v01_dur = hook_dur + quote_dur - transition_duration
    offset_2 = v01_dur - transition_duration

    actual_total = v01_dur + cta_dur - transition_duration

    return (
        [round(hook_dur, 2), round(quote_dur, 2), round(cta_dur, 2)],
        [round(offset_1, 2), round(offset_2, 2)],
        True,
    )


def get_transition_type(mood: str) -> str:
    """Return the xfade transition type for a given mood."""
    return TRANSITION_TYPES.get(mood, "fade")


def analyze_audio_for_sync(
    audio_path: Path,
    mood: str,
    target_total: float = 14.0,
) -> dict:
    """
    Full analysis: detect peaks, calculate synced offsets, pick transition type.

    Returns dict with keys:
        - scene_durations: [hook, quote, cta]
        - transition_offsets: [offset_1, offset_2]
        - transition_type: xfade filter name
        - used_beats: bool
        - peaks: list of detected peak timestamps
    """
    peaks = detect_energy_peaks(audio_path)
    scene_durs, offsets, used_beats = calculate_synced_offsets(
        peaks, target_total=target_total
    )
    trans_type = get_transition_type(mood)

    return {
        "scene_durations": scene_durs,
        "transition_offsets": offsets,
        "transition_type": trans_type,
        "used_beats": used_beats,
        "peaks": peaks,
    }


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python beat_sync.py <audio_file.mp3>")
        sys.exit(1)

    path = Path(sys.argv[1])
    result = analyze_audio_for_sync(path, mood="dark_philosophical")
    print(f"Audio: {path}")
    print(f"Detected peaks: {result['peaks']}")
    print(f"Scene durations: {result['scene_durations']}")
    print(f"Transition offsets: {result['transition_offsets']}")
    print(f"Transition type: {result['transition_type']}")
    print(f"Used beat sync: {result['used_beats']}")
