"""Source discovery and local catalogue API. Python 3.11+; no dependencies."""
import argparse
import hashlib
import json
import os
import re
import sys
import tempfile
import time
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, parse_qsl, urlencode, urlsplit, urlunsplit
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parent
API = "https://api.search.brave.com/res/v1/web/search"


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def canonical_url(value):
    """Normalize safe public links; preserve meaningful query params such as p."""
    parts = urlsplit(value.strip())
    if parts.scheme.lower() not in ("http", "https") or not parts.hostname:
        raise ValueError("Expected HTTP(S) source URL")
    if parts.username or parts.password:
        raise ValueError("Credentials must not be present in source URLs")
    host = parts.hostname.lower()
    port = parts.port
    netloc = f"[{host}]" if ":" in host else host
    if port and (parts.scheme.lower(), port) not in (("https", 443), ("http", 80)):
        netloc += f":{port}"
    query = [(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True)
             if not k.lower().startswith("utm_") and k.lower() not in
             {"spm_id_from", "fbclid", "gclid", "trackid"}]
    return urlunsplit((parts.scheme.lower(), netloc, parts.path or "/",
                       urlencode(sorted(query)), ""))


def source_id(url):
    return hashlib.sha256(canonical_url(url).encode()).hexdigest()[:20]


def read_json(path, default=None):
    if not Path(path).exists() and default is not None:
        return default
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", dir=path.parent, encoding="utf-8", delete=False) as f:
        temp = Path(f.name)
        json.dump(value, f, ensure_ascii=False, indent=2)
        f.write("\n")
    os.replace(temp, path)


def merge_sources(existing, discoveries, stamp):
    merged = {}
    for item in existing:
        item = dict(item)
        item["url"] = canonical_url(item["url"])
        item["id"] = source_id(item["url"])
        merged[item["url"]] = item
    for found in discoveries:
        url = canonical_url(found["url"])
        old = merged.get(url)
        if old is None:
            old = {"id": source_id(url), "url": url,
                   "title": found.get("title", url), "topics": [],
                   "queries": [], "first_discovered_at": stamp,
                   "review_status": "candidate", "rights_status": "not_assessed",
                   "school": "unclassified", "editorial_note": "",
                   "content_ingested": False}
            merged[url] = old
        # Discovery does not overwrite human-reviewed title, rights, notes or status.
        old["last_seen_at"] = stamp
        old["topics"] = sorted(set(old.get("topics", []) + found.get("topics", [])))
        old["queries"] = sorted(set(old.get("queries", []) + found.get("queries", [])))
        if found.get("provider_age"):
            old["provider_age"] = str(found["provider_age"])[:200]
        old["discovery_method"] = old.get("discovery_method", "brave_web_search")
    return sorted(merged.values(), key=lambda x: x["url"])


def brave_search(query, key, freshness=None, count=10, opener=urlopen):
    params = {"q": query, "count": count, "search_lang": "zh-hans"}
    if freshness:
        params["freshness"] = freshness
    request = Request(API + "?" + urlencode(params), headers={
        "Accept": "application/json", "X-Subscription-Token": key,
        "User-Agent": "BaziResourceDiscovery/0.1"})
    with opener(request, timeout=30) as response:
        payload = json.load(response)
    if not isinstance(payload, dict) or not isinstance(payload.get("web", {}), dict):
        raise ValueError("Unexpected search response")
    # Deliberately do not retain snippets, full pages, videos or transcripts.
    return payload.get("web", {}).get("results", [])


def collect(args):
    key = os.environ.get("BRAVE_SEARCH_API_KEY", "").strip()
    if not key:
        raise ValueError("Set BRAVE_SEARCH_API_KEY in environment or GitHub Actions secrets")
    config = read_json(args.config)
    queries = config["queries"]
    if not isinstance(queries, list) or not 1 <= len(queries) <= 20:
        raise ValueError("Use 1 to 20 configured queries")
    count = config.get("results_per_query", 10)
    if not isinstance(count, int) or not 1 <= count <= 20:
        raise ValueError("results_per_query must be 1 to 20")
    stamp, discoveries, errors = now(), [], []
    for entry in queries:
        label = entry.get("topic", "other")
        query = entry["query"]
        try:
            rows = brave_search(query, key, "pm" if args.mode == "latest" else None, count)
            for row in rows:
                try:
                    url = canonical_url(row["url"])
                except (ValueError, KeyError, TypeError):
                    continue
                discoveries.append({"url": url, "title": str(row.get("title", url))[:500],
                                    "topics": [label], "queries": [query],
                                    "provider_age": row.get("age")})
        except HTTPError as exc:
            errors.append({"topic": label, "error": f"HTTP {exc.code}"})
            if exc.code in (401, 403, 429):
                # Stop instead of repeatedly charging or hammering a denied API.
                break
        except (URLError, TimeoutError, ValueError) as exc:
            errors.append({"topic": label, "error": type(exc).__name__})
        time.sleep(1.1)
    existing = read_json(args.catalog, [])
    merged = merge_sources(existing, discoveries, stamp)
    write_json(args.catalog, merged)
    report = {"ran_at": stamp, "mode": args.mode, "new_sources": len(merged) - len(existing),
              "total_sources": len(merged), "errors": errors,
              "note": "Latest means search-provider page-age filtering; not truth or full coverage."}
    write_json(Path(args.catalog).with_name("last_run.json"), report)
    print(json.dumps(report, ensure_ascii=False))
    return 1 if errors else 0


def search_sources(catalog, q="", topic=None, status=None, limit=20):
    if status and status not in {"candidate", "reviewed", "rejected"}:
        raise ValueError("Invalid review status")
    terms = [s for s in re.split(r"\s+", q.casefold().strip()) if s]
    hits = []
    for row in catalog:
        if topic and topic not in row.get("topics", []):
            continue
        if status and row.get("review_status") != status:
            continue
        text = " ".join([row.get("title", ""), row.get("editorial_note", ""),
                         row["url"], *row.get("topics", [])]).casefold()
        if not terms or all(term in text for term in terms):
            hits.append(row)
    return {"total": len(hits), "results": hits[:max(1, min(limit, 100))],
            "kind": "source_catalogue", "approved_knowledge_rules": 0,
            "notice": "Source discovery only. No verified divination rules or predictions."}


def make_handler(catalog_path):
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            parsed = urlsplit(self.path)
            if parsed.path not in {"/search", "/health"}:
                self.respond(404, {"error": "Use /search?q=... or /health"})
                return
            try:
                if parsed.path == "/health":
                    value = {"status": "ok", "kind": "source_catalogue"}
                else:
                    p = parse_qs(parsed.query)
                    value = search_sources(read_json(catalog_path, []), p.get("q", [""])[0],
                                           p.get("topic", [None])[0],
                                           p.get("status", [None])[0],
                                           int(p.get("limit", ["20"])[0]))
                self.respond(200, value)
            except ValueError:
                self.respond(400, {"error": "Invalid filter or catalogue"})

        def respond(self, status, value):
            body = json.dumps(value, ensure_ascii=False).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *_args):
            pass  # Do not log user search strings.
    return Handler


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--catalog", type=Path, default=ROOT / "data/sources.json")
    sub = parser.add_subparsers(dest="command", required=True)
    discovery = sub.add_parser("collect")
    discovery.add_argument("--config", type=Path, default=ROOT / "config/queries.json")
    discovery.add_argument("--mode", choices=["evergreen", "latest"], default="latest")
    search = sub.add_parser("search")
    search.add_argument("query")
    search.add_argument("--topic")
    search.add_argument("--status", choices=["candidate", "reviewed", "rejected"])
    server = sub.add_parser("serve")
    server.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    try:
        if args.command == "collect":
            return collect(args)
        if args.command == "search":
            print(json.dumps(search_sources(read_json(args.catalog, []), args.query,
                                            args.topic, args.status), ensure_ascii=False, indent=2))
            return 0
        # Intentionally local-only. Deployment needs authentication and TLS separately.
        print(f"Source API listening on http://127.0.0.1:{args.port}/search", flush=True)
        ThreadingHTTPServer(("127.0.0.1", args.port), make_handler(args.catalog)).serve_forever()
    except (ValueError, OSError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
