from __future__ import annotations

from typing import Iterable, List, Sequence, Set

import google.auth
from google.auth.credentials import Credentials
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials as OAuthCredentials
from googleapiclient.discovery import Resource, build

DEFAULT_GMAIL_SCOPES: Sequence[str] = (
    "https://www.googleapis.com/auth/gmail.readonly",
)


def build_credentials_from_oauth(
    client_id: str,
    client_secret: str,
    refresh_token: str,
    scopes: Iterable[str] = DEFAULT_GMAIL_SCOPES,
) -> OAuthCredentials:
    return OAuthCredentials(
        token=None,
        refresh_token=refresh_token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=client_id,
        client_secret=client_secret,
        scopes=list(scopes),
    )


def build_gmail_service(
    credentials: Credentials | None = None,
    scopes: Iterable[str] = DEFAULT_GMAIL_SCOPES,
    *,
    cache_discovery: bool = False,
    user_agent: str | None = None,
) -> Resource:
    scopes_list = list(scopes)

    if credentials is None:
        scoped = scopes_list or None
        credentials, _ = google.auth.default(scopes=scoped)

    requires_scopes = getattr(credentials, "requires_scopes", False)
    if requires_scopes and scopes_list:
        credentials = credentials.with_scopes(scopes_list)

    if not credentials.valid:
        request = Request()
        credentials.refresh(request)

    discovery_kwargs = {"cache_discovery": cache_discovery}
    if user_agent:
        discovery_kwargs["client_options"] = {"user_agent": user_agent}

    return build("gmail", "v1", credentials=credentials, **discovery_kwargs)


def fetch_messages_by_history(
    gmail_service: Resource,
    start_history_id: str,
    *,
    user_id: str = "me",
    history_types: Sequence[str] | None = ("messageAdded",),
) -> List[str]:
    history_resource = gmail_service.users().history()
    request = history_resource.list(
        userId=user_id,
        startHistoryId=start_history_id,
        historyTypes=list(history_types) if history_types else None,
    )

    message_ids: List[str] = []
    seen: Set[str] = set()

    while request is not None:
        response = request.execute()
        for record in response.get("history", []):
            for added in record.get("messagesAdded", []):
                message = added.get("message") or {}
                message_id = message.get("id")
                if message_id and message_id not in seen:
                    seen.add(message_id)
                    message_ids.append(message_id)

        request = history_resource.list_next(request, response)

    return message_ids


def fetch_message(
    gmail_service: Resource,
    message_id: str,
    *,
    user_id: str = "me",
    format: str = "full",
) -> dict:
    messages_resource = gmail_service.users().messages()
    return messages_resource.get(userId=user_id, id=message_id, format=format).execute()


def extract_message_snippet(message: dict) -> str:
    return message.get("snippet", "")


def register_watch(
    gmail_service: Resource,
    topic_name: str,
    *,
    user_id: str = "me",
    label_ids: list | None = None,
) -> dict:
    body = {"topicName": topic_name}
    if label_ids:
        body["labelIds"] = label_ids
    return gmail_service.users().watch(userId=user_id, body=body).execute()
