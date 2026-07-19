"""
Instagram Poster — uploads image to Cloudinary (public URL), then posts via Meta Graph API.
Flow: local JPEG → Cloudinary CDN URL → Meta /media → Meta /media_publish
"""

import time
import requests
import cloudinary
import cloudinary.uploader
from pathlib import Path


# ── Retry helper ──────────────────────────────────────────────────────────────

_SANITIZE_PATTERNS = ["access_token", "api_secret", "api_key"]


def _sanitize_url(url: str) -> str:
    """Strip sensitive query params from URLs for safe logging."""
    import urllib.parse
    parsed = urllib.parse.urlparse(url)
    params = urllib.parse.parse_qs(parsed.query)
    for key in list(params.keys()):
        if any(p in key.lower() for p in _SANITIZE_PATTERNS):
            params[key] = ["***REDACTED***"]
    new_query = urllib.parse.urlencode(params, doseq=True)
    return urllib.parse.urlunparse(parsed._replace(query=new_query))


def _retry_request(func, max_retries=3, backoff=2):
    """Retry func on ConnectionError, Timeout, or 5xx status."""
    for attempt in range(max_retries):
        try:
            return func()
        except (requests.ConnectionError, requests.Timeout):
            if attempt == max_retries - 1:
                raise
            wait = backoff ** attempt
            time.sleep(wait)
        except requests.HTTPError as e:
            status = e.response.status_code if e.response else 0
            if status >= 500 and attempt < max_retries - 1:
                wait = backoff ** attempt
                time.sleep(wait)
            else:
                # Sanitize before re-raising to prevent token leaks in logs
                if e.response is not None and e.response.request is not None:
                    req = e.response.request
                    sanitized_url = _sanitize_url(str(req.url))
                    raise requests.HTTPError(
                        f"{status} Client Error: for url: {sanitized_url}",
                        response=e.response,
                    )
                raise


# ── Cloudinary upload ─────────────────────────────────────────────────────────

def upload_to_cloudinary(image_path: str | Path, config: dict) -> str:
    """
    Upload image to Cloudinary. Returns public HTTPS URL.
    Free tier: 25GB storage, 25GB bandwidth/month — plenty for daily posts.
    """
    cloudinary.config(
        cloud_name=config["cloud_name"],
        api_key=config["api_key"],
        api_secret=config["api_secret"],
        secure=True
    )

    def _upload():
        result = cloudinary.uploader.upload(
            str(image_path),
            folder="socrates_posts",
            resource_type="image",
            format="jpg",
            quality="auto:best",
        )
        return result

    result = _retry_request(_upload, max_retries=3)

    url = result.get("secure_url")
    if not url:
        raise ValueError("Cloudinary upload failed: no secure_url in response")

    return url


# ── Meta Graph API ─────────────────────────────────────────────────────────────

GRAPH_URL = "https://graph.instagram.com/v22.0"
FB_GRAPH_URL = "https://graph.facebook.com/v22.0"


def _graph(access_token: str) -> str:
    """Pick the Graph host by token type: Facebook-login tokens (EAA…) publish
    via graph.facebook.com; Instagram-login tokens via graph.instagram.com.
    Both speak the same Content Publishing API for IG business accounts."""
    return FB_GRAPH_URL if (access_token or "").startswith("EAA") else GRAPH_URL


def _create_media_container(ig_account_id: str, image_url: str, caption: str, access_token: str) -> str:
    """Step 1: Create media container. Returns container ID."""
    url = f"{_graph(access_token)}/{ig_account_id}/media"
    params = {
        "image_url": image_url,
        "caption": caption,
        "access_token": access_token,
    }

    def _post():
        resp = requests.post(url, params=params, timeout=30)
        resp.raise_for_status()
        return resp

    response = _retry_request(_post, max_retries=3)

    data = response.json()
    container_id = data.get("id")
    if not container_id:
        raise ValueError(f"No container ID in response: {data}")

    return container_id


def _wait_for_container(container_id: str, access_token: str, max_wait: int = 120) -> bool:
    """Poll until container status is FINISHED."""
    url = f"{_graph(access_token)}/{container_id}"
    params = {"fields": "status_code", "access_token": access_token}

    for _ in range(max_wait // 5):
        def _poll():
            resp = requests.get(url, params=params, timeout=15)
            resp.raise_for_status()
            return resp

        try:
            response = _retry_request(_poll, max_retries=2)
        except (requests.ConnectionError, requests.Timeout, requests.HTTPError):
            # On polling failure, keep trying until max_wait
            time.sleep(5)
            continue

        data = response.json()
        status = data.get("status_code", "")

        if status == "FINISHED":
            return True
        if status == "ERROR":
            raise ValueError(f"Media container processing error: {data}")

        time.sleep(5)

    raise TimeoutError(f"Container {container_id} did not finish in {max_wait}s")


def _publish_container(ig_account_id: str, container_id: str, access_token: str) -> str:
    """Step 2: Publish container. Returns post ID."""
    url = f"{_graph(access_token)}/{ig_account_id}/media_publish"
    params = {
        "creation_id": container_id,
        "access_token": access_token,
    }

    def _post():
        resp = requests.post(url, params=params, timeout=30)
        resp.raise_for_status()
        return resp

    response = _retry_request(_post, max_retries=3)

    data = response.json()
    post_id = data.get("id")
    if not post_id:
        raise ValueError(f"No post ID in response: {data}")

    return post_id


def upload_video_to_cloudinary(video_path: str | Path, config: dict) -> str:
    """
    Upload video to Cloudinary. Returns public HTTPS URL.
    Used for Reels (video posts).
    """
    cloudinary.config(
        cloud_name=config["cloud_name"],
        api_key=config["api_key"],
        api_secret=config["api_secret"],
        secure=True
    )

    def _upload():
        result = cloudinary.uploader.upload(
            str(video_path),
            folder="socrates_posts",
            resource_type="video",
        )
        return result

    result = _retry_request(_upload, max_retries=3)

    url = result.get("secure_url")
    if not url:
        raise ValueError("Cloudinary video upload failed: no secure_url in response")

    return url


def _create_reel_container(
    ig_account_id: str,
    video_url: str,
    caption: str,
    access_token: str,
    cover_url: str | None = None,
) -> str:
    """Create a Reel media container. Returns container ID."""
    url = f"{_graph(access_token)}/{ig_account_id}/media"
    params = {
        "media_type": "REELS",
        "video_url": video_url,
        "caption": caption,
        "access_token": access_token,
    }
    if cover_url:
        params["cover_url"] = cover_url

    def _post():
        resp = requests.post(url, params=params, timeout=30)
        resp.raise_for_status()
        return resp

    response = _retry_request(_post, max_retries=3)

    data = response.json()
    container_id = data.get("id")
    if not container_id:
        raise ValueError(f"No container ID in response: {data}")

    return container_id


def post_to_instagram(
    image_path: str | Path,
    caption: str,
    ig_account_id: str,
    access_token: str,
    cloudinary_config: dict
) -> str:
    """
    Full flow: upload image → create container → publish.
    Returns Instagram post ID.
    """
    print("  Uploading to Cloudinary...")
    public_url = upload_to_cloudinary(image_path, cloudinary_config)
    print(f"  Public URL: {public_url}")

    print("  Creating Meta media container...")
    container_id = _create_media_container(ig_account_id, public_url, caption, access_token)
    print(f"  Container ID: {container_id}")

    print("  Waiting for container to finish processing...")
    _wait_for_container(container_id, access_token)

    print("  Publishing to Instagram...")
    post_id = _publish_container(ig_account_id, container_id, access_token)

    return post_id


def _create_carousel_item_container(ig_account_id: str, image_url: str, access_token: str) -> str:
    """Create a carousel child container (image, no caption). Returns container ID."""
    url = f"{_graph(access_token)}/{ig_account_id}/media"
    params = {
        "image_url": image_url,
        "is_carousel_item": "true",
        "access_token": access_token,
    }

    def _post():
        resp = requests.post(url, params=params, timeout=30)
        resp.raise_for_status()
        return resp

    response = _retry_request(_post, max_retries=3)

    data = response.json()
    container_id = data.get("id")
    if not container_id:
        raise ValueError(f"No container ID in response: {data}")

    return container_id


def _create_carousel_container(
    ig_account_id: str, children_ids: list[str], caption: str, access_token: str
) -> str:
    """Create the parent carousel container referencing child item containers."""
    url = f"{_graph(access_token)}/{ig_account_id}/media"
    params = {
        "media_type": "CAROUSEL",
        "children": ",".join(children_ids),
        "caption": caption,
        "access_token": access_token,
    }

    def _post():
        resp = requests.post(url, params=params, timeout=30)
        resp.raise_for_status()
        return resp

    response = _retry_request(_post, max_retries=3)

    data = response.json()
    container_id = data.get("id")
    if not container_id:
        raise ValueError(f"No container ID in response: {data}")

    return container_id


def post_carousel_to_instagram(
    image_paths: list[str | Path],
    caption: str,
    ig_account_id: str,
    access_token: str,
    cloudinary_config: dict,
) -> str:
    """
    Full flow: upload each slide → create carousel item containers →
    create parent carousel container → publish.
    Returns Instagram post ID.
    """
    children_ids = []
    for i, image_path in enumerate(image_paths):
        print(f"  Uploading carousel slide {i + 1}/{len(image_paths)} to Cloudinary...")
        public_url = upload_to_cloudinary(image_path, cloudinary_config)
        print(f"  Creating carousel item container {i + 1}/{len(image_paths)}...")
        container_id = _create_carousel_item_container(ig_account_id, public_url, access_token)
        children_ids.append(container_id)

    print("  Creating parent carousel container...")
    carousel_id = _create_carousel_container(ig_account_id, children_ids, caption, access_token)
    print(f"  Carousel container ID: {carousel_id}")

    print("  Waiting for carousel container to finish processing...")
    _wait_for_container(carousel_id, access_token)

    print("  Publishing carousel to Instagram...")
    post_id = _publish_container(ig_account_id, carousel_id, access_token)

    return post_id


def post_reel_to_instagram(
    video_path: str | Path,
    caption: str,
    ig_account_id: str,
    access_token: str,
    cloudinary_config: dict,
    cover_path: str | Path | None = None,
) -> str:
    """
    Full flow: upload video → (optional cover) → create Reel container → publish.
    Returns Instagram post ID.
    """
    print("  Uploading video to Cloudinary...")
    public_url = upload_video_to_cloudinary(video_path, cloudinary_config)
    print(f"  Public URL: {public_url}")

    cover_url = None
    if cover_path:
        print("  Uploading cover image to Cloudinary...")
        cover_url = upload_to_cloudinary(cover_path, cloudinary_config)
        print(f"  Cover URL: {cover_url}")

    print("  Creating Reel media container...")
    container_id = _create_reel_container(
        ig_account_id, public_url, caption, access_token, cover_url=cover_url
    )
    print(f"  Container ID: {container_id}")

    print("  Waiting for container to finish processing...")
    _wait_for_container(container_id, access_token, max_wait=360)  # video processing is slow

    print("  Publishing Reel to Instagram...")
    post_id = _publish_container(ig_account_id, container_id, access_token)

    return post_id
