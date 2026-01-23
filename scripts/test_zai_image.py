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
"""Test Z.AI image generation with GLM-Image model.

Usage:
    ./test_zai_image.py "a futuristic city at sunset"
    ./test_zai_image.py --model cogview-4-250304 "a cat playing piano"
    ./test_zai_image.py --quality standard "quick sketch of mountains"
"""

import argparse
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
import httpx
from zai import ZaiClient

# Load from ~/.claude/.env if exists
load_dotenv(Path.home() / ".claude" / ".env")


def generate_image(
    prompt: str,
    model: str = "glm-image",
    quality: str = "hd",
    size: str = "1280x1280",
    output_dir: Path | None = None,
) -> Path:
    """Generate an image using Z.AI's image generation API.

    Args:
        prompt: Text description of the desired image
        model: Model to use (glm-image or cogview-4-250304)
        quality: Image quality (hd ~20s, standard ~5-10s)
        size: Image dimensions (default 1280x1280)
        output_dir: Directory to save image (default: current directory)

    Returns:
        Path to the saved image file
    """
    api_key = os.environ.get("Z_AI_API_KEY") or os.environ.get("ZAI_API_KEY") or os.environ.get("ZHIPUAI_API_KEY")
    if not api_key:
        raise ValueError(
            "API key not found. Set Z_AI_API_KEY environment variable.\n"
            "Get your key from: https://z.ai/model-api"
        )

    print(f"Generating image with {model}...")
    print(f"  Prompt: {prompt}")
    print(f"  Quality: {quality} (hd ~20s, standard ~5-10s)")
    print(f"  Size: {size}")

    client = ZaiClient(api_key=api_key)

    # Generate image
    response = client.images.generations(
        model=model,
        prompt=prompt,
        quality=quality,
        size=size,
    )

    # Get image URL from response
    if not response.data or not response.data[0].url:
        raise ValueError("No image URL in response")

    image_url = response.data[0].url
    print(f"  Generated: {image_url[:80]}...")

    # Download and save image
    output_dir = output_dir or Path.cwd()
    output_dir.mkdir(parents=True, exist_ok=True)

    # Create filename from prompt
    safe_prompt = "".join(c if c.isalnum() or c in " -_" else "" for c in prompt)[:50]
    safe_prompt = safe_prompt.strip().replace(" ", "_")
    output_path = output_dir / f"{safe_prompt}_{model}.png"

    # Handle duplicate filenames
    counter = 1
    while output_path.exists():
        output_path = output_dir / f"{safe_prompt}_{model}_{counter}.png"
        counter += 1

    print(f"  Downloading to: {output_path}")

    with httpx.Client() as http_client:
        img_response = http_client.get(image_url)
        img_response.raise_for_status()
        output_path.write_bytes(img_response.content)

    print(f"  Saved: {output_path}")
    return output_path


def main():
    parser = argparse.ArgumentParser(
        description="Generate images using Z.AI GLM-Image or CogView-4"
    )
    parser.add_argument("prompt", help="Text description of the desired image")
    parser.add_argument(
        "--model",
        choices=["glm-image", "cogview-4-250304"],
        default="glm-image",
        help="Model to use (default: glm-image)",
    )
    parser.add_argument(
        "--quality",
        choices=["hd", "standard"],
        default="hd",
        help="Image quality: hd (~20s) or standard (~5-10s)",
    )
    parser.add_argument(
        "--size",
        default="1280x1280",
        help="Image size (default: 1280x1280)",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Output directory (default: current directory)",
    )

    args = parser.parse_args()

    try:
        output_path = generate_image(
            prompt=args.prompt,
            model=args.model,
            quality=args.quality,
            size=args.size,
            output_dir=args.output_dir,
        )
        print(f"\nSuccess! Image saved to: {output_path}")

        # Try to open the image on macOS
        if sys.platform == "darwin":
            os.system(f"open '{output_path}'")

    except Exception as e:
        print(f"\nError: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
