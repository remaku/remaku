from dataclasses import dataclass, field
from typing import Any, Literal

LocalizedText = dict[str, str]


def normalize_language(language: str) -> str:
    language = language.replace("-", "_")

    if language in ("zh_TW", "zh_CN"):
        return language

    return "en_US"


def localized_text(value: LocalizedText, language: str) -> str:
    normalized = normalize_language(language)

    if value.get(normalized):
        return value[normalized]

    if value.get("en_US"):
        return value["en_US"]

    for text in value.values():
        if text:
            return text

    return ""


def parse_localized_text(value: Any) -> LocalizedText:
    if isinstance(value, dict):
        return {str(key).replace("-", "_"): str(text) for key, text in value.items() if text is not None}

    return {"en_US": str(value or "")}


@dataclass(slots=True)
class PackCompatibility:
    remaku_min: str = ""
    remaku_max: str = ""

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PackCompatibility":
        return cls(
            remaku_min=str(data.get("remaku_min", "")),
            remaku_max=str(data.get("remaku_max", "")),
        )

    def to_dict(self) -> dict[str, str]:
        return {
            "remaku_min": self.remaku_min,
            "remaku_max": self.remaku_max,
        }


@dataclass(slots=True)
class PackAssets:
    zip_url: str = ""
    preview_image_url: str = ""

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PackAssets":
        return cls(
            zip_url=str(data.get("zip_url", "")),
            preview_image_url=str(data.get("preview_image_url", "")),
        )

    def to_dict(self) -> dict[str, str]:
        return {
            "zip_url": self.zip_url,
            "preview_image_url": self.preview_image_url,
        }


@dataclass(slots=True)
class PackSource:
    repo_path: str = ""
    macro_json_path: str = ""

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PackSource":
        return cls(
            repo_path=str(data.get("repo_path", "")),
            macro_json_path=str(data.get("macro_json_path", "")),
        )

    def to_dict(self) -> dict[str, str]:
        return {
            "repo_path": self.repo_path,
            "macro_json_path": self.macro_json_path,
        }


@dataclass(slots=True)
class PackGame:
    id: str
    label: str

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PackGame":
        game = cls(
            id=str(data.get("id", "")),
            label=str(data.get("label", "")),
        )
        game.validate()
        return game

    def validate(self) -> None:
        if not self.id:
            raise ValueError("Game id is required")

    def display_label(self) -> str:
        return self.label or self.id

    def to_dict(self) -> dict[str, str]:
        return {
            "id": self.id,
            "label": self.label,
        }


@dataclass(slots=True)
class PackCatalogEntry:
    pack_id: str
    game: str
    label: LocalizedText
    description: LocalizedText
    author: str
    version: str
    release_tag: str
    source: PackSource = field(default_factory=PackSource)
    assets: PackAssets = field(default_factory=PackAssets)
    compatibility: PackCompatibility = field(default_factory=PackCompatibility)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PackCatalogEntry":
        assets_data = data.get("assets", {})
        if not isinstance(assets_data, dict):
            assets_data = {}

        source_data = data.get("source", {})
        if not isinstance(source_data, dict):
            source_data = {}

        compatibility_data = data.get("compatibility", {})
        if not isinstance(compatibility_data, dict):
            compatibility_data = {}

        entry = cls(
            pack_id=str(data.get("pack_id", "")),
            game=str(data.get("game", "")),
            label=parse_localized_text(data.get("label", "")),
            description=parse_localized_text(data.get("description", "")),
            author=str(data.get("author", "")),
            version=str(data.get("version", "")),
            release_tag=str(data.get("release_tag", "")),
            source=PackSource.from_dict(source_data),
            assets=PackAssets.from_dict(assets_data),
            compatibility=PackCompatibility.from_dict(compatibility_data),
        )
        entry.validate()
        return entry

    def validate(self) -> None:
        required_values = {
            "pack_id": self.pack_id,
            "game": self.game,
            "label": localized_text(self.label, "en_US"),
            "description": localized_text(self.description, "en_US"),
            "version": self.version,
            "release_tag": self.release_tag,
            "assets.zip_url": self.assets.zip_url,
        }

        missing = [key for key, value in required_values.items() if not value]
        if missing:
            raise ValueError(f"Missing pack fields: {', '.join(missing)}")

    def display_label(self, language: str) -> str:
        return localized_text(self.label, language)

    def display_description(self, language: str) -> str:
        return localized_text(self.description, language)

    def to_dict(self) -> dict[str, Any]:
        return {
            "pack_id": self.pack_id,
            "game": self.game,
            "label": self.label,
            "description": self.description,
            "author": self.author,
            "version": self.version,
            "release_tag": self.release_tag,
            "source": self.source.to_dict(),
            "assets": self.assets.to_dict(),
            "compatibility": self.compatibility.to_dict(),
        }


@dataclass(slots=True)
class PackCatalog:
    schema_version: int
    repo_url: str
    games: list[PackGame] = field(default_factory=list)
    packs: list[PackCatalogEntry] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PackCatalog":
        games_data = data.get("games", [])
        if not isinstance(games_data, list):
            raise ValueError("Pack catalog games must be a list")

        packs_data = data.get("packs", [])
        if not isinstance(packs_data, list):
            raise ValueError("Pack catalog packs must be a list")

        catalog = cls(
            schema_version=int(data.get("schema_version", 0)),
            repo_url=str(data.get("repo_url", "")),
            games=[PackGame.from_dict(item) for item in games_data if isinstance(item, dict)],
            packs=[PackCatalogEntry.from_dict(item) for item in packs_data if isinstance(item, dict)],
        )
        catalog.validate()
        return catalog

    def validate(self) -> None:
        if self.schema_version != 1:
            raise ValueError(f"Unsupported pack catalog schema: {self.schema_version}")

        if not self.repo_url:
            raise ValueError("Pack catalog repo_url is required")

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "repo_url": self.repo_url,
            "games": [game.to_dict() for game in self.games],
            "packs": [pack.to_dict() for pack in self.packs],
        }


PackStatus = Literal["available", "incompatible"]


@dataclass(slots=True)
class PackListItem:
    entry: PackCatalogEntry
    status: PackStatus
    game_label: str = ""
