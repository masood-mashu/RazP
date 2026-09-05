"""
Converts WebP animation frames + MP3 voiceover + SRT subtitles into a production MP4 & WebM video.
"""
import os
import subprocess
import shutil
from pathlib import Path
from PIL import Image
import imageio_ffmpeg

FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()
WEBP_SRC = r"d:\hackathon\RazorPay\razp_5min_submission_showcase.webp"
AUDIO_SRC = r"d:\hackathon\RazorPay\narration_voiceover.mp3"
SRT_SRC = r"d:\hackathon\RazorPay\subtitles.srt"
OUTPUT_MP4 = r"d:\hackathon\RazorPay\razp_sentinel_5min_showcase.mp4"
OUTPUT_WEBM = r"d:\hackathon\RazorPay\razp_sentinel_5min_showcase.webm"
TEMP_FRAME_DIR = r"d:\hackathon\RazorPay\.temp_frames"

def main():
    print("[1/4] Extracting frames from animated WebP...")
    os.makedirs(TEMP_FRAME_DIR, exist_ok=True)
    
    img = Image.open(WEBP_SRC)
    n_frames = img.n_frames
    print(f"Total animation frames: {n_frames}")
    
    # Extract frames sequentially
    for i in range(n_frames):
        img.seek(i)
        frame_path = os.path.join(TEMP_FRAME_DIR, f"frame_{i:05d}.jpg")
        img.convert("RGB").save(frame_path, quality=90)
        if i % 200 == 0 or i == n_frames - 1:
            print(f"  Extracted frame {i}/{n_frames}...")

    # Audio duration is ~306.34 seconds.
    # To match audio perfectly: 1189 frames / 306.34s = ~3.8813 fps
    fps = n_frames / 306.34
    print(f"[2/4] Target video framerate to match narration duration: {fps:.4f} fps")

    # [3/4] Render MP4 with embedded audio and soft subtitles (mov_text)
    print(f"[3/4] Rendering high-definition MP4 with audio and subtitles to: {OUTPUT_MP4}...")
    
    mp4_cmd = [
        FFMPEG, "-y",
        "-framerate", f"{fps:.4f}",
        "-i", os.path.join(TEMP_FRAME_DIR, "frame_%05d.jpg"),
        "-i", AUDIO_SRC,
        "-i", SRT_SRC,
        "-c:v", "libx264",
        "-pix_fmt", "yuv420p",
        "-crf", "22",
        "-preset", "medium",
        "-c:a", "aac",
        "-b:a", "128k",
        "-c:s", "mov_text",
        "-metadata:s:s:0", "language=eng",
        "-metadata:s:s:0", "title=English",
        "-shortest",
        OUTPUT_MP4
    ]
    res_mp4 = subprocess.run(mp4_cmd, capture_output=True, text=True)
    if res_mp4.returncode != 0:
        print("MP4 stderr:", res_mp4.stderr[-500:])
    else:
        print(f"MP4 rendered successfully! Size: {os.path.getsize(OUTPUT_MP4) / (1024*1024):.2f} MB")

    # [4/4] Render WebM for direct web browser streaming
    print(f"[4/4] Rendering high-definition WebM with audio to: {OUTPUT_WEBM}...")
    webm_cmd = [
        FFMPEG, "-y",
        "-framerate", f"{fps:.4f}",
        "-i", os.path.join(TEMP_FRAME_DIR, "frame_%05d.jpg"),
        "-i", AUDIO_SRC,
        "-c:v", "libvpx-vp9",
        "-crf", "30",
        "-b:v", "0",
        "-c:a", "libopus",
        "-b:a", "96k",
        "-shortest",
        OUTPUT_WEBM
    ]
    res_webm = subprocess.run(webm_cmd, capture_output=True, text=True)
    if res_webm.returncode != 0:
        print("WebM stderr:", res_webm.stderr[-500:])
    else:
        print(f"WebM rendered successfully! Size: {os.path.getsize(OUTPUT_WEBM) / (1024*1024):.2f} MB")

    # Cleanup temp frames
    print("Cleaning up temporary frame images...")
    shutil.rmtree(TEMP_FRAME_DIR, ignore_errors=True)
    print("All video renders complete!")

if __name__ == "__main__":
    main()
