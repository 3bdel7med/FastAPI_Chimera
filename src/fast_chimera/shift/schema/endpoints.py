"""HTTP part of the fingerprint: endpoints, guards, middleware."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class ParamInfo(BaseModel):
    name: str
    location: Literal["path", "query", "header", "cookie", "form", "file", "body"]
    type: str | None = None
    required: bool = True


class GuardInfo(BaseModel):
    """A dependency applied to a router group or one endpoint (Laravel calls this route middleware)."""

    name: str
    scope: Literal["router", "endpoint"]


class EndpointInfo(BaseModel):
    method: str
    path: str  # full path: router prefix + every include_router prefix + route path
    handler: str
    module: str
    tags: list[str] = Field(default_factory=list)
    guards: list[GuardInfo] = Field(default_factory=list)
    injects: list[str] = Field(default_factory=list)  # Depends(...) used as parameters (e.g. current user)
    params: list[ParamInfo] = Field(default_factory=list)
    request_body: str | None = None
    response_model: str | None = None
    status_code: int | None = None
    mounted: bool = True  # False when no include_router chain from an app reaches this router


class MiddlewareInfo(BaseModel):
    name: str
    kind: Literal["middleware", "http", "dependency"]
    scope: Literal["global"] = "global"
    options: list[str] = Field(default_factory=list)  # option NAMES only, never their values
