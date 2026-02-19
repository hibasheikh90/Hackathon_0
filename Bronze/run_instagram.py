"""Quick runner for Instagram posting."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from integrations.social.instagram import InstagramPlatform

ig = InstagramPlatform()
result = ig.post(
    "Testing our new post automation! 🚀",
    media=[Path("test_post.png")],
)

print(f"Success: {result.success}")
if result.error:
    print(f"Error: {result.error}")
else:
    print(f"Posted {result.content_length} chars to {result.platform}")
