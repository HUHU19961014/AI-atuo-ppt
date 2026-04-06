from __future__ import annotations

import argparse
import re
from dataclasses import dataclass
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent
DEFAULT_REGRESSION_DIR = PROJECT_ROOT / "regression"
SCORE_LINE_PATTERN = re.compile(r"^-\s*评分：\s*([1-5])\s*$", re.MULTILINE)
TOTAL_LINE_PATTERN = re.compile(r"^-\s*总分：.*$", re.MULTILINE)
RATING_LINE_PATTERN = re.compile(r"^-\s*评级：.*$", re.MULTILINE)
CONCLUSION_LINE_PATTERN = re.compile(r"^-\s*结论：.*$", re.MULTILINE)


@dataclass(frozen=True)
class ReviewScore:
    review_path: Path
    scores: tuple[int, ...]
    total_score: int
    rating: str
    conclusion: str


def resolve_rating(total_score: int) -> tuple[str, str]:
    if 21 <= total_score <= 25:
        return "优秀", "可直接进入交付或仅需极少量润色。"
    if 16 <= total_score <= 20:
        return "合格", "可用于内部汇报，建议做少量调整。"
    if 11 <= total_score <= 15:
        return "可用初稿", "具备基础可用性，但需要针对性优化。"
    if 6 <= total_score <= 10:
        return "质量偏弱", "需要明显返工后再进入交付。"
    return "不合格", "建议重做。"


def parse_review_scores(review_text: str) -> tuple[int, ...]:
    return tuple(int(match) for match in SCORE_LINE_PATTERN.findall(review_text))


def evaluate_review(review_path: Path) -> ReviewScore:
    text = review_path.read_text(encoding="utf-8")
    scores = parse_review_scores(text)
    if len(scores) != 5:
        raise ValueError(f"{review_path} should contain exactly 5 score lines, found {len(scores)}.")
    total_score = sum(scores)
    rating, conclusion = resolve_rating(total_score)
    return ReviewScore(
        review_path=review_path,
        scores=scores,
        total_score=total_score,
        rating=rating,
        conclusion=conclusion,
    )


def update_review_file(score: ReviewScore) -> None:
    text = score.review_path.read_text(encoding="utf-8")
    updated = TOTAL_LINE_PATTERN.sub(f"- 总分：{score.total_score}", text)
    updated = RATING_LINE_PATTERN.sub(f"- 评级：{score.rating}", updated)
    updated = CONCLUSION_LINE_PATTERN.sub(f"- 结论：{score.conclusion}", updated, count=1)
    score.review_path.write_text(updated, encoding="utf-8")


def discover_review_files(path: Path) -> list[Path]:
    if path.is_file():
        return [path]
    if not path.exists():
        raise FileNotFoundError(f"Path not found: {path}")
    return sorted(
        review_path
        for review_path in path.rglob("review.md")
        if review_path.name == "review.md"
    )


def print_result(score: ReviewScore) -> None:
    print(f"[{score.review_path}]")
    print(f"scores: {list(score.scores)}")
    print(f"total_score: {score.total_score}")
    print(f"rating: {score.rating}")
    print(f"conclusion: {score.conclusion}")
    print("")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Calculate review scores from V2 PPT review.md files.")
    parser.add_argument(
        "path",
        nargs="?",
        default=str(DEFAULT_REGRESSION_DIR),
        help="Path to a review.md file or a directory containing review.md files.",
    )
    parser.add_argument(
        "--write",
        action="store_true",
        help="Write total score, rating, and conclusion back into review.md.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    target_path = Path(args.path)
    review_files = discover_review_files(target_path)
    if not review_files:
        print("No review.md files found.")
        return 1

    has_error = False
    for review_file in review_files:
        try:
            score = evaluate_review(review_file)
            if args.write:
                update_review_file(score)
            print_result(score)
        except Exception as exc:
            has_error = True
            print(f"[{review_file}]")
            print(f"error: {exc}")
            print("")

    return 1 if has_error else 0


if __name__ == "__main__":
    raise SystemExit(main())
