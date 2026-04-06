import tempfile
import unittest
from pathlib import Path

from score_review import evaluate_review, resolve_rating, update_review_file


class ScoreReviewTests(unittest.TestCase):
    def test_resolve_rating(self):
        self.assertEqual(resolve_rating(23)[0], "优秀")
        self.assertEqual(resolve_rating(18)[0], "合格")
        self.assertEqual(resolve_rating(13)[0], "可用初稿")
        self.assertEqual(resolve_rating(8)[0], "质量偏弱")
        self.assertEqual(resolve_rating(5)[0], "不合格")

    def test_evaluate_review_and_write_back(self):
        content = """# V2 PPT 人工验收表

## 评分项

### 1. 结构与页数合理性（1~5分）
- 评分：4
- 说明：

### 2. 标题自然度（1~5分）
- 评分：4
- 说明：

### 3. 内容密度与表达质量（1~5分）
- 评分：3
- 说明：

### 4. 版式稳定性与溢出风险（1~5分）
- 评分：5
- 说明：

### 5. 可交付水平（1~5分）
- 评分：4
- 说明：

## 总分

- 总分：
- 评级：
- 结论：
"""
        with tempfile.TemporaryDirectory() as temp_dir:
            review_path = Path(temp_dir) / "review.md"
            review_path.write_text(content, encoding="utf-8")
            score = evaluate_review(review_path)
            self.assertEqual(score.total_score, 20)
            self.assertEqual(score.rating, "合格")

            update_review_file(score)
            updated = review_path.read_text(encoding="utf-8")
            self.assertIn("- 总分：20", updated)
            self.assertIn("- 评级：合格", updated)
