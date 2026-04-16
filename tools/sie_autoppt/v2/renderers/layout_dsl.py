from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Box:
    left: float
    top: float
    width: float
    height: float

    def inset(self, *, left: float = 0.0, top: float = 0.0, right: float = 0.0, bottom: float = 0.0) -> "Box":
        return Box(
            left=self.left + left,
            top=self.top + top,
            width=max(0.0, self.width - left - right),
            height=max(0.0, self.height - top - bottom),
        )


@dataclass(frozen=True)
class Grid:
    columns: int
    rows: int
    gap_x: float
    gap_y: float

    def cells(self, container: Box) -> tuple[Box, ...]:
        cols = max(1, int(self.columns))
        rows = max(1, int(self.rows))
        cell_width = (container.width - self.gap_x * (cols - 1)) / cols
        cell_height = (container.height - self.gap_y * (rows - 1)) / rows
        items: list[Box] = []
        for row in range(rows):
            for col in range(cols):
                items.append(
                    Box(
                        left=container.left + col * (cell_width + self.gap_x),
                        top=container.top + row * (cell_height + self.gap_y),
                        width=cell_width,
                        height=cell_height,
                    )
                )
        return tuple(items)
