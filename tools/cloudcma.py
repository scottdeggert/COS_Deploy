"""Cloud CMA Quick CMA client. Pure Python; no handler or core imports."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from app.config import CLOUDCMA_API_KEY, CLOUDCMA_WIDGET_URL
from tools.logger import log_event

_OUT_OF_MLS_MESSAGE = "No matching listings were found on the MLS."
_TIMEOUT_SECONDS = 15


@dataclass(frozen=True)
class CloudCmaResult:
    """Typed result from request_quick_cma."""

    ok: bool
    failure_kind: Literal["none", "out_of_mls", "config", "http", "network"] = "none"
    detail: str = ""


def _session() -> requests.Session:
    session = requests.Session()
    retry = Retry(
        total=3,
        backoff_factor=2,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=frozenset({"GET", "POST"}),
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session


def _parse_error_body(response: requests.Response) -> str:
    try:
        payload = response.json()
    except ValueError:
        return (response.text or "").strip()[:200]
    if isinstance(payload, dict):
        error = payload.get("error")
        if error:
            return str(error).strip()
    return (response.text or "").strip()[:200]


def _address_label(address: str) -> str:
    return f"CMA - {address.strip()}"


def _resolve_client_fields(
    address: str,
    name: str | None,
    title: str | None,
) -> tuple[str, str]:
    """Return non-blank name and title for Cloud CMA widget POST."""
    address_label = _address_label(address)
    contact_name = (name or "").strip()
    report_title = (title or "").strip()
    if contact_name:
        return contact_name, report_title or address_label
    return address_label, address_label


def request_quick_cma(
    address: str,
    job_id: str,
    callback_url: str,
    name: str | None = None,
    title: str | None = None,
) -> CloudCmaResult:
    """Request a Quick CMA. Omits email_to so Cloud CMA sends no email.

    When callback_url is valid and job_id is present and email_to is absent,
    Cloud CMA emails neither the lead nor the agent.
    """
    if not CLOUDCMA_API_KEY:
        log_event(
            "cloudcma",
            "request_quick_cma",
            "failure",
            detail=f"CLOUDCMA_API_KEY unset job_id={job_id}",
            file=__file__,
            function="request_quick_cma",
        )
        return CloudCmaResult(ok=False, failure_kind="config", detail="api_key unset")

    params: dict[str, str] = {
        "api_key": CLOUDCMA_API_KEY,
        "address": address,
        "job_id": job_id,
        "callback_url": callback_url,
    }
    client_name, report_title = _resolve_client_fields(address, name, title)
    params["name"] = client_name
    params["title"] = report_title

    log_event(
        "cloudcma",
        "request_quick_cma",
        "start",
        detail=f"job_id={job_id}",
        file=__file__,
        function="request_quick_cma",
    )

    try:
        response = _session().post(
            CLOUDCMA_WIDGET_URL,
            data=params,
            timeout=_TIMEOUT_SECONDS,
        )
    except requests.RequestException as exc:
        log_event(
            "cloudcma",
            "request_quick_cma",
            "failure",
            detail=f"network job_id={job_id}",
            exc_info=exc,
            file=__file__,
            function="request_quick_cma",
        )
        return CloudCmaResult(ok=False, failure_kind="network", detail="network error")

    if response.ok:
        log_event(
            "cloudcma",
            "request_quick_cma",
            "success",
            detail=f"job_id={job_id}",
            file=__file__,
            function="request_quick_cma",
        )
        return CloudCmaResult(ok=True)

    error_text = _parse_error_body(response)
    if _OUT_OF_MLS_MESSAGE.lower() in error_text.lower():
        log_event(
            "cloudcma",
            "request_quick_cma",
            "failure",
            detail=f"out_of_mls job_id={job_id}",
            file=__file__,
            function="request_quick_cma",
        )
        return CloudCmaResult(ok=False, failure_kind="out_of_mls", detail=error_text)

    body = (response.text or "").strip()
    log_event(
        "cloudcma",
        "request_quick_cma",
        "failure",
        detail=f"http {response.status_code} job_id={job_id} body={body[:300]}",
        file=__file__,
        function="request_quick_cma",
    )
    return CloudCmaResult(ok=False, failure_kind="http", detail=f"http {response.status_code}")
