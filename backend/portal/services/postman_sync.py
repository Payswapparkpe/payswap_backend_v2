"""
Postman API sync: fetch collections from Postman and return flattened requests for portal UI.
Postman API: https://api.getpostman.com (X-Api-Key header).
"""

import requests


POSTMAN_API_BASE = "https://api.getpostman.com"


def _get_url_from_request(request_obj):
    """Extract final URL string from Postman request.url (can be string or object)."""
    if not request_obj:
        return ""
    url = request_obj.get("url")
    if isinstance(url, str):
        return url
    if isinstance(url, dict):
        raw = url.get("raw")
        if raw:
            return raw
        # Build from host/path
        host = url.get("host") or []
        path = url.get("path") or []
        protocol = url.get("protocol") or "https"
        if isinstance(host, list):
            host_str = ".".join(str(h) for h in host)
        else:
            host_str = str(host)
        path_str = "/".join(str(p) for p in path)
        if path_str and not path_str.startswith("/"):
            path_str = "/" + path_str
        return f"{protocol}://{host_str}{path_str or '/'}"
    return ""


def _extract_headers(request_obj):
    """Get headers as list of {key, value} from request.header (Postman format)."""
    if not request_obj:
        return []
    header = request_obj.get("header") or []
    return [{"key": h.get("key", ""), "value": h.get("value", "")} for h in header if h.get("key")]


def _extract_body(request_obj):
    """Get body string from request.body (Postman: mode raw => body)."""
    if not request_obj:
        return ""
    body = request_obj.get("body") or {}
    if body.get("mode") == "raw" and "raw" in body:
        return body["raw"] or ""
    return ""


def _flatten_items(items, prefix=""):
    """
    Recursively flatten Postman collection items into list of requests.
    Each item can be a request (has 'request') or a folder (has 'item').
    Returns list of { id, name, method, url, headers, body }.
    """
    out = []
    for it in items or []:
        name = it.get("name") or "Untitled"
        if it.get("request"):
            req = it["request"]
            out.append({
                "id": it.get("id"),
                "name": name,
                "method": (req.get("method") or "GET").upper(),
                "url": _get_url_from_request(req),
                "headers": _extract_headers(req),
                "body": _extract_body(req),
            })
        elif it.get("item"):
            # Folder: recurse
            sub = _flatten_items(it["item"], prefix=name + " / ")
            out.extend(sub)
    return out


def fetch_postman_collections(api_key):
    """
    Fetch all collections from Postman API and return flattened structure for portal UI.
    api_key: Postman API key (X-Api-Key).
    Returns: { "success": True, "collections": [ { "id", "name", "uid", "requests": [...] } ] }
    or { "success": False, "error": "..." }.
    """
    if not api_key or not api_key.strip():
        return {"success": False, "error": "Postman API key is required."}
    headers = {"X-Api-Key": api_key.strip()}
    try:
        r = requests.get(f"{POSTMAN_API_BASE}/collections", headers=headers, timeout=15)
        if r.status_code == 401:
            return {"success": False, "error": "Invalid Postman API key."}
        if r.status_code != 200:
            return {"success": False, "error": f"Postman API returned {r.status_code}."}
        data = r.json()
        collections_list = data.get("collections") or []
        result_collections = []
        for coll in collections_list:
            uid = coll.get("uid") or coll.get("id")
            name = coll.get("name") or "Unnamed"
            # Fetch full collection to get items
            try:
                cr = requests.get(
                    f"{POSTMAN_API_BASE}/collections/{uid}",
                    headers=headers,
                    timeout=15,
                )
                if cr.status_code != 200:
                    result_collections.append({
                        "id": coll.get("id"),
                        "uid": uid,
                        "name": name,
                        "requests": [],
                        "error": f"Failed to load collection: {cr.status_code}",
                    })
                    continue
                cdata = cr.json()
                collection = cdata.get("collection") or cdata
                items = collection.get("item") or []
                requests_flat = _flatten_items(items)
                result_collections.append({
                    "id": coll.get("id"),
                    "uid": uid,
                    "name": name,
                    "requests": requests_flat,
                })
            except Exception as e:
                result_collections.append({
                    "id": coll.get("id"),
                    "uid": uid,
                    "name": name,
                    "requests": [],
                    "error": str(e),
                })
        return {"success": True, "collections": result_collections}
    except requests.RequestException as e:
        return {"success": False, "error": str(e)}
    except Exception as e:
        return {"success": False, "error": str(e)}
