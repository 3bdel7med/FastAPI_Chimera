"""What the finished product should be able to do: features grouped into modules."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

from fast_chimera.core.text import slugify

Priority = Literal["core", "recommended", "optional"]
_VALID_PRIORITIES = ("core", "recommended", "optional")


class Feature(BaseModel):
    name: str
    description: str = ""
    priority: Priority = "recommended"

    @field_validator("priority", mode="before")
    @classmethod
    def _normalize_priority(cls, value: Any) -> str:
        text = str(value).strip().lower()
        return text if text in _VALID_PRIORITIES else "recommended"


class FeatureModule(BaseModel):
    name: str
    description: str = ""
    features: list[Feature] = Field(default_factory=list)


class FeatureCatalog(BaseModel):
    project_name: str = Field(description="Short kebab-case project name, e.g. 'multi-vendor-marketplace'")
    summary: str = ""
    modules: list[FeatureModule] = Field(min_length=1)

    @field_validator("project_name")
    @classmethod
    def _to_slug(cls, value: str) -> str:
        return slugify(value) or "project"

    @property
    def total_features(self) -> int:
        return sum(len(module.features) for module in self.modules)

    @classmethod
    def from_request(cls, request: str) -> FeatureCatalog:
        """A one-module catalog, used by `add` where the request itself is the whole feature."""
        module = FeatureModule(name="Requested feature", description=request)
        return cls(project_name=slugify(request) or "feature", summary=request, modules=[module])

    def select(self, exclude_modules: Iterable[str] = (), include_optional: bool = True) -> FeatureCatalog:
        """A copy without the excluded modules and (optionally) without optional features."""
        excluded = {name.strip().lower() for name in exclude_modules}
        kept_modules = []
        for module in self.modules:
            if module.name.lower() in excluded:
                continue
            features = [f for f in module.features if include_optional or f.priority != "optional"]
            if features or not module.features:
                kept_modules.append(module.model_copy(update={"features": features}))

        if not kept_modules:
            raise ValueError("The selection removed every module.")
        return self.model_copy(update={"modules": kept_modules})
