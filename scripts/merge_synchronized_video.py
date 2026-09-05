"""
Merges the choreographed Playwright recording with the male voiceover and synchronized subtitles.
Outputs:
- d:/hackathon/RazorPay/razp_sentinel_5min_showcase.mp4
- d:/hackathon/RazorPay/razp_sentinel_5min_showcase.webm
"""
import os
import subprocess
import shutil
from pathlib import Path
import imageio_ffmpeg

FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()
RECORDING_DIR = r"d:\hackathon\RazorPay\recordings"
AUDIO_SRC = r"d:\hackathon\RazorPay\narration_voiceover.mp3"
SRT_SRC = r"d:\hackathon\RazorPay\subtitles.srt"
OUTPUT_MP4 = r"d:\hackathon\RazorPay\razp_sentinel_5min_showcase.mp4"
OUTPUT_WEBM = r"d:\hackathon\RazorPay\razp_sentinel_5min_showcase.webm"
ARTIFACT_DIR = r"C:\Users\Masood\.gemini\antigravity-ide\brain\e16ac2c2-f60e-45d8-8cd5-d350fd58e966"

def main():
    print("Locating latest recorded video...")
    webm_files = [os.path.join(RECORDING_DIR, f) for f in os.listdir(RECORDING_DIR) if f.endswith('.webm')]
    if not webm_files:
        raise RuntimeError("No recorded webm video found in " + RECORDING_DIR)
    
    webm_files.sort(key=lambda x: os.path.getmtime(x), reverse=True)
    raw_video = webm_files[0]
    print(f"Latest raw video: {raw_video} ({os.path.getsize(raw_video) / (1024*1024):.2f} MB)")

    # [1] Render MP4 with H.264, AAC audio, and soft subtitles
    print(f"\n[1/2] Encoding MP4 with audio and subtitles to: {OUTPUT_MP4}...")
    mp4_cmd = [
        FFMPEG, "-y",
        "-i", raw_video,
        "-i", AUDIO_SRC,
        "-i", SRT_SRC,
        "-c:v", "libx264",
        "-pix_fmt", "yuv420p",
        "-vf", "scale=trunc(iw/2)*2:trunc(ih/2)*2",
        "-crf", "18",
        "-preset", "medium",
        "-c:a", "aac",
        "-b:a", "192k",
        "-c:s", "mov_text",
        "-metadata:s:s:0", "language=eng",
        "-metadata:s:s:0", "title=English",
        "-shortest",
        OUTPUT_MP4
    ]
    res_mp4 = subprocess.run(mp4_cmd, capture_output=True, text=True)
    if res_mp4.returncode != 0:
        print("MP4 Error:", res_mp4.stderr[-600:])
    else:
        print(f"MP4 successfully generated! Size: {os.path.getsize(OUTPUT_MP4) / (1024*1024):.2f} MB")

    # [2] Render WebM with VP9 and Opus audio
    print(f"\n[2/2] Encoding WebM to: {OUTPUT_WEBM}...")
    webm_cmd = [
        FFMPEG, "-y",
        "-i", raw_video,
        "-i", AUDIO_SRC,
        "-c:v", "libvpx-vp9",
        "-crf", "28",
        "-b:v", "0",
        "-c:a", "libopus",
        "-b:a", "128k",
        "-shortest",
        OUTPUT_WEBM
    ]
    res_webm = subprocess.run(webm_cmd, capture_output=True, text=True)
    if res_webm.returncode != 0:
        print("WebM Error:", res_webm.stderr[-600:])
    else:
        print(f"WebM successfully generated! Size: {os.path.getsize(OUTPUT_WEBM) / (1024*1024):.2f} MB")

    # Copy to artifacts directory
    print("\nCopying outputs to artifact directory...")
    shutil.copy2(OUTPUT_MP4, os.path.join(ARTIFACT_DIR, "razp_sentinel_5min_showcase.mp4"))
    shutil.copy2(OUTPUT_WEBM, os.path.join(ARTIFACT_DIR, "razp_sentinel_5min_showcase.webm"))
    print("All files synchronized and deployed!")

if __name__ == "__main__":
    main()
