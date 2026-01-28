#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = [
#     "zai-sdk",
#     "httpx",
#     "sniffio",
#     "anyio",
#     "python-dotenv",
# ]
# ///
"""Test Z.AI video generation with CogVideoX model.

Video generation is async - submit a job and poll for results.

Usage:
    ./test_zai_video.py "a cat walking on a beach at sunset"
    ./test_zai_video.py --image input.png "cat starts walking forward"
    ./test_zai_video.py --quality 1080p --fps 60 "epic battle scene"
"""

import argparse
import os
import sys
import time
from pathlib import Path

from dotenv import load_dotenv
import httpx
from zai import ZaiClient

# Load from ~/.claude/.env if exists
load_dotenv(Path.cwd().parent / ".env")


def generate_video(
    prompt: str,
    image_path: Path | None = None,
    quality: str = "720p",
    fps: int = 30,
    output_dir: Path | None = None,
) -> Path:
    """Generate a video using Z.AI's CogVideoX API.

    Args:
        prompt: Text description of the desired video
        image_path: Optional image for image-to-video generation
        quality: Video quality (720p, 1080p, 4K)
        fps: Frames per second (30 or 60)
        output_dir: Directory to save video (default: ~/generated-images/)

    Returns:
        Path to the saved video file
    """
    api_key = (
        os.environ.get("Z_AI_API_KEY")
        or os.environ.get("ZAI_API_KEY")
        or os.environ.get("ZHIPUAI_API_KEY")
    )
    if not api_key:
        raise ValueError(
            "API key not found. Set Z_AI_API_KEY environment variable.\n"
            "Get your key from: https://z.ai/model-api"
        )

    print(f"Generating video with CogVideoX...")
    print(f"  Prompt: {prompt}")
    print(f"  Quality: {quality}, FPS: {fps}")
    if image_path:
        print(f"  Input image: {image_path}")

    client = ZaiClient(api_key=api_key)

    # Prepare request
    request_params = {
        "model": "cogvideox-3",
        "prompt": prompt,
        "quality": quality,
        "fps": fps,
    }

    # Add image for image-to-video
    if image_path:
        if not image_path.exists():
            raise FileNotFoundError(f"Image not found: {image_path}")
        # For image-to-video, we'd need to upload the image first
        # This depends on the exact API format
        print("  Note: Image-to-video requires base64 encoding of image")
        import base64

        with open(image_path, "rb") as f:
            request_params["image"] = base64.b64encode(f.read()).decode()

    # Submit async job
    print("  Submitting video generation job...")
    response = client.videos.generations(
        **request_params,
        async_mode=True,  # Video generation is always async
    )

    if not hasattr(response, "id"):
        raise ValueError("No job ID in response")

    job_id = response.id
    print(f"  Job ID: {job_id}")
    print("  Waiting for video generation (this may take 1-5 minutes)...")

    # Poll for results
    max_attempts = 60  # 5 minutes max
    poll_interval = 5  # seconds

    for attempt in range(max_attempts):
        time.sleep(poll_interval)

        result = client.videos.retrieve(job_id)

        status = getattr(result, "task_status", None)
        if status == "SUCCESS":
            video_url = result.video_result[0].url if result.video_result else None
            if not video_url:
                raise ValueError("No video URL in result")

            print(f"  Video ready: {video_url[:80]}...")
            break
        elif status in ("FAIL", "CANCELLED"):
            raise ValueError(f"Video generation failed: {status}")
        else:
            elapsed = (attempt + 1) * poll_interval
            print(f"  Still processing... ({elapsed}s elapsed)")
    else:
        raise TimeoutError("Video generation timed out after 5 minutes")

    # Download video
    output_dir = output_dir or Path.home() / "generated-images"
    output_dir.mkdir(parents=True, exist_ok=True)

    safe_prompt = "".join(c if c.isalnum() or c in " -_" else "" for c in prompt)[:40]
    safe_prompt = safe_prompt.strip().replace(" ", "_")
    output_path = output_dir / f"{safe_prompt}_cogvideox.mp4"

    counter = 1
    while output_path.exists():
        output_path = output_dir / f"{safe_prompt}_cogvideox_{counter}.mp4"
        counter += 1

    print(f"  Downloading to: {output_path}")

    with httpx.Client(timeout=120) as http_client:
        video_response = http_client.get(video_url)
        video_response.raise_for_status()
        output_path.write_bytes(video_response.content)

    print(f"  Saved: {output_path}")
    return output_path


def main():
    parser = argparse.ArgumentParser(description="Generate videos using Z.AI CogVideoX")
    parser.add_argument("prompt", help="Text description of the desired video")
    parser.add_argument(
        "--image",
        type=Path,
        default=None,
        help="Input image for image-to-video generation",
    )
    parser.add_argument(
        "--quality",
        choices=["720p", "1080p", "4K"],
        default="720p",
        help="Video quality (default: 720p)",
    )
    parser.add_argument(
        "--fps",
        type=int,
        choices=[30, 60],
        default=30,
        help="Frames per second (default: 30)",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Output directory (default: ~/generated-images/)",
    )

    args = parser.parse_args()

    try:
        output_path = generate_video(
            prompt=args.prompt,
            image_path=args.image,
            quality=args.quality,
            fps=args.fps,
            output_dir=args.output_dir,
        )
        print(f"\nSuccess! Video saved to: {output_path}")

        # Try to open the video on macOS
        if sys.platform == "darwin":
            os.system(f"open '{output_path}'")

    except Exception as e:
        print(f"\nError: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
