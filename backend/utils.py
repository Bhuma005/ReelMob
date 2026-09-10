import re
from urllib.parse import urlparse

def sanitize_url(url: str) -> str:
    """Ensures a URL is valid and strips dangerous characters/injections"""
    if not url:
        return ""
    # Parse and rebuild to strip weird protocol injections
    parsed = urlparse(url)
    if parsed.scheme not in ['http', 'https']:
        return ""
    clean_url = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
    if parsed.query:
        clean_url += f"?{parsed.query}"
    return clean_url

def sanitize_filename(filename: str) -> str:
    """Removes path traversals and invalid OS characters for file-system safety across platforms."""
    if not filename:
        return "unnamed_file"
    # Remove path components
    filename = filename.replace("..", "").replace("/", "").replace("\\", "")
    # Remove invalid characters
    return re.sub(r'[<>:"|?*]', '_', filename)
