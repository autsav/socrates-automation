import os

from supabase import create_client, Client

_url = os.environ.get("SUPABASE_URL", "")
_key = os.environ.get("SUPABASE_SERVICE_KEY", "")

_supabase: Client | None = None


def get_supabase() -> Client:
    global _supabase
    if _supabase is None:
        _supabase = create_client(_url, _key)
    return _supabase


def upload_to_storage(
    bucket: str,
    path: str,
    file_data: bytes,
    content_type: str,
) -> str:
    supabase = get_supabase()
    supabase.storage.from_(bucket).upload(
        path=path,
        file=file_data,
        file_options={"content-type": content_type},
    )
    try:
        return supabase.storage.from_(bucket).get_public_url(path)
    except Exception:
        # Upload succeeded but URL retrieval failed — clean up the orphaned file
        try:
            supabase.storage.from_(bucket).remove([path])
        except Exception:
            pass  # Best-effort cleanup
        raise
