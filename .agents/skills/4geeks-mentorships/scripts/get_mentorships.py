#!/usr/bin/env python3
"""Read 4Geeks public mentors or the authenticated student's mentorship sessions."""

import argparse
import json
import os
import unicodedata
from datetime import datetime, timezone
from urllib.error import HTTPError
from urllib.request import HTTPSHandler, HTTPRedirectHandler, Request, build_opener

BASE_URL = "https://breathecode.herokuapp.com"
MENTORS_PATH = "/v1/mentorship/public/mentor"
SESSIONS_PATH = "/v1/mentorship/user/me/session"
TIMEOUT_SECONDS = 20
MAX_RESPONSE_BYTES = 64 * 1024


class NoRedirect(HTTPRedirectHandler):
    """Reject redirects so the authorization header cannot leave the host."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def emit(payload):
    rendered = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    token = os.environ.get("TOKEN_4GEEKS")
    if token:
        rendered = rendered.replace(token, "[REDACTED]")
    print(rendered)


def request_json(path):
    token = os.environ.get("TOKEN_4GEEKS")
    if not token:
        return None, {"error": "token_missing"}

    request = Request(
        BASE_URL + path,
        headers={"Authorization": f"Token {token}", "Accept": "application/json"},
        method="GET",
    )
    response = None
    try:
        opener = build_opener(NoRedirect, HTTPSHandler)
        try:
            response = opener.open(request, timeout=TIMEOUT_SECONDS)
        except HTTPError as http_response:
            response = http_response

        if response.code != 200:
            return None, {"error": "http_error", "http_status": response.code}

        body = response.read(MAX_RESPONSE_BYTES)
        if len(body) >= MAX_RESPONSE_BYTES:
            return None, {"error": "response_limit_reached", "http_status": 200}
        try:
            return json.loads(body), None
        except (ValueError, UnicodeDecodeError):
            return None, {"error": "invalid_json", "http_status": 200}
    except Exception:
        # Exception details may contain request data; never expose them.
        return None, {"error": "connection_error"}
    finally:
        if response is not None:
            try:
                response.close()
            except Exception:
                pass


def scalar(value):
    return value if isinstance(value, (str, int, float, bool)) or value is None else None


def mentor_name(row):
    user = row.get("user")
    if not isinstance(user, dict):
        user = row.get("mentor")
    if not isinstance(user, dict):
        return None
    parts = [user.get(key, "") for key in ("first_name", "last_name")]
    name = " ".join(part.strip() for part in parts if isinstance(part, str) and part.strip())
    return name or None


def get_services(row):
    services = row.get("services")
    if not isinstance(services, list):
        services = row.get("service")
        services = [services] if isinstance(services, dict) else []
    result = []
    for service in services:
        if not isinstance(service, dict):
            continue
        item = {key: scalar(service.get(key)) for key in ("name", "slug", "specialty")}
        item = {key: value for key, value in item.items() if value not in (None, "")}
        if item:
            result.append(item)
    return result


def normalize(text):
    text = unicodedata.normalize("NFKD", text.casefold())
    return "".join(char for char in text if not unicodedata.combining(char))


def fetch_mentors(query=None):
    payload, error = request_json(MENTORS_PATH)
    if error:
        return error
    rows = payload if isinstance(payload, list) else (
        payload.get("results") if isinstance(payload, dict) else None
    )
    if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
        return {"error": "unexpected_structure", "http_status": 200}

    mentors = []
    needle = normalize(query) if query else None
    for row in rows:
        name = mentor_name(row)
        services = get_services(row)
        slug = scalar(row.get("slug"))
        if slug is None and isinstance(row.get("mentor"), dict):
            slug = scalar(row["mentor"].get("slug"))
        if not isinstance(slug, str):
            slug = None
        if needle:
            searchable = " ".join(
                [name or ""]
                + [str(value) for service in services for value in service.values()]
            )
            if needle not in normalize(searchable):
                continue
        mentors.append({"name": name, "mentor_slug": slug, "services": services})

    return {"http_status": 200, "count": len(mentors), "results": mentors}


def parse_datetime(value):
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(timezone.utc)


def fetch_sessions():
    payload, error = request_json(SESSIONS_PATH)
    if error:
        return error
    rows = payload if isinstance(payload, list) else (
        payload.get("results") if isinstance(payload, dict) else None
    )
    if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
        return {"error": "unexpected_structure", "http_status": 200}

    now = datetime.now(timezone.utc)
    sessions = []
    for row in rows:
        mentor = row.get("mentor")
        if not isinstance(mentor, dict):
            mentor = {}
        user = mentor.get("user")
        mentor_data = {"name": mentor_name({"user": user}) if isinstance(user, dict) else None}
        if isinstance(mentor.get("slug"), str):
            mentor_data["mentor_slug"] = mentor["slug"]
        service = row.get("service")
        service_data = None
        if isinstance(service, dict):
            service_data = {
                key: scalar(service.get(key))
                for key in ("name", "slug")
                if scalar(service.get(key)) not in (None, "")
            }
        item = {
            "id": scalar(row.get("id")),
            "status": scalar(row.get("status")),
            "mentor": mentor_data,
            "service": service_data,
        }
        for field in ("starts_at", "ends_at", "started_at", "ended_at"):
            value = scalar(row.get(field))
            if isinstance(value, str) and value:
                item[field] = value
        start = parse_datetime(item.get("starts_at"))
        item["upcoming"] = bool(
            start is not None
            and start >= now
            and isinstance(item.get("status"), str)
            and item["status"].upper() == "PENDING"
        )
        sessions.append(item)

    return {"http_status": 200, "count": len(sessions), "results": sessions}


def main():
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    mentors_parser = subparsers.add_parser("mentors")
    mentors_parser.add_argument("--query")
    subparsers.add_parser("sessions")
    args = parser.parse_args()

    if args.command == "mentors":
        emit(fetch_mentors(args.query))
    else:
        emit(fetch_sessions())


if __name__ == "__main__":
    main()
