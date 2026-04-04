from dataclasses import asdict, dataclass, field


@dataclass(frozen=True)
class QaChecks:
    ending_last: str
    theme_title_font_40: str
    directory_title_font_24: str
    directory_assets_preserved: str


@dataclass(frozen=True)
class QaMetrics:
    overflow_risk_boxes: int


@dataclass(frozen=True)
class QaResult:
    file: str
    slides: int
    expected_directory_pages: list[int]
    actual_directory_pages: list[int]
    checks: QaChecks
    metrics: QaMetrics
    semantic_patterns: list[str] = field(default_factory=list)
    chapter_lines: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    schema_version: str = "1.0"

    def to_dict(self) -> dict[str, object]:
        return asdict(self)
