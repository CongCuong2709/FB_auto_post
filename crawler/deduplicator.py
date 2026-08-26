from difflib import SequenceMatcher


def deduplicate_posts(posts: list) -> list:
    """
    Loại bài viết trùng lặp theo 3 cấp độ:
      Level 1 — URL: cùng link → trùng tuyệt đối
      Level 2 — Hash 50 ký tự đầu: bài copy-paste
      Level 3 — Fuzzy 85%: viết lại nhưng cùng nội dung
    Giữ lại bài đầu tiên xuất hiện trong mỗi nhóm trùng.
    """
    if not posts:
        return []

    seen_urls: set[str] = set()
    seen_hashes: set[str] = set()
    unique: list[dict] = []

    for post in posts:
        # --- Level 1: URL ---
        url = (post.get("url") or "").strip()
        if url and url in seen_urls:
            continue
        if url:
            seen_urls.add(url)

        # --- Level 2: content hash ---
        content = (post.get("content") or "").strip()
        key = content[:50].lower().replace(" ", "").replace("\n", "")
        if key and key in seen_hashes:
            continue
        if key:
            seen_hashes.add(key)

        # --- Level 3: fuzzy match (against last 30 kept posts for speed) ---
        snippet = content[:200]
        is_dup = False
        for kept in unique[-30:]:
            ratio = SequenceMatcher(
                None, snippet, (kept.get("content") or "")[:200]
            ).ratio()
            if ratio >= 0.85:
                is_dup = True
                break

        if not is_dup:
            unique.append(post)

    return unique
