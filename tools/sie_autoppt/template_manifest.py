from dataclasses import dataclass


@dataclass(frozen=True)
class ShapeBounds:
    min_top: int | None = None
    max_top: int | None = None
    min_width: int | None = None
    max_width: int | None = None

    def matches(self, shape) -> bool:
        top = getattr(shape, "top", None)
        width = getattr(shape, "width", None)
        if top is None or width is None:
            return False
        if self.min_top is not None and top <= self.min_top:
            return False
        if self.max_top is not None and top >= self.max_top:
            return False
        if self.min_width is not None and width <= self.min_width:
            return False
        if self.max_width is not None and width >= self.max_width:
            return False
        return True


@dataclass(frozen=True)
class TextBoxGeometry:
    left: int
    top: int
    width: int
    height: int


THEME_TITLE_BOUNDS = ShapeBounds(
    min_top=1_500_000,
    max_top=2_300_000,
    min_width=5_000_000,
)

DIRECTORY_TITLE_BOUNDS = ShapeBounds(
    min_top=1_800_000,
    max_top=5_200_000,
    min_width=3_000_000,
)

BODY_TITLE_BOUNDS = ShapeBounds(
    max_top=300_000,
    min_width=7_000_000,
)

BODY_SUBTITLE_BOUNDS = ShapeBounds(
    min_top=300_000,
    max_top=1_600_000,
    min_width=7_000_000,
)

BODY_RENDER_AREA_BOUNDS = ShapeBounds(
    min_top=1_200_000,
    max_top=6_200_000,
)

BODY_TITLE_FALLBACK_BOX = TextBoxGeometry(
    left=166_370,
    top=36_830,
    width=10_034_086,
    height=480_060,
)
