def normalize_title(title: str) -> str:
    """Normalize a title for better matching

    Args:
        title: The original title

    Returns:
        Normalized title for matching
    """
    import re
    # Convert to lowercase
    normalized = title.lower()
    # Remove special characters
    normalized = re.sub(r'[^a-z0-9\s]', '', normalized)
    # Remove extra spaces
    normalized = re.sub(r'\s+', ' ', normalized).strip()
    # Remove common articles at the beginning
    for article in ['the ', 'a ', 'an ']:
        if normalized.startswith(article):
            normalized = normalized[len(article):]
    return normalized
