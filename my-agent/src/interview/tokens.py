"""Issuing the token a candidate joins their interview room with."""

from datetime import timedelta

from livekit import api

DEFAULT_TOKEN_TTL = timedelta(hours=2)
CANDIDATE_IDENTITY = "candidate"


def room_name_for(interview_id: str) -> str:
    return f"interview-{interview_id}"


def build_candidate_token(
    *,
    room_name: str,
    api_key: str,
    api_secret: str,
    identity: str = CANDIDATE_IDENTITY,
    ttl: timedelta = DEFAULT_TOKEN_TTL,
) -> str:
    return (
        api.AccessToken(api_key, api_secret)
        .with_identity(identity)
        .with_grants(api.VideoGrants(room_join=True, room=room_name))
        .with_ttl(ttl)
        .to_jwt()
    )
