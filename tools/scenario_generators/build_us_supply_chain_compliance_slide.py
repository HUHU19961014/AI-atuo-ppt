from __future__ import annotations

import argparse
from pathlib import Path

try:
    from .sie_onepage_designer import BulletItem, LawRow, OnePageBrief, TextFragment, build_onepage_slide, self_check_layout as shared_self_check_layout
except ImportError:
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from scenario_generators.sie_onepage_designer import BulletItem, LawRow, OnePageBrief, TextFragment, build_onepage_slide, self_check_layout as shared_self_check_layout


PROJECT_ROOT = Path(__file__).resolve().parents[2]
OUTPUT_PPT = PROJECT_ROOT / "output" / "us_supply_chain_compliance_sie_template_onepage.pptx"

US_BRIEF = OnePageBrief(
    title="对美出口供应链合规追溯要求：UFLPA 高门槛与企业体系化举证",
    kicker="U.S. COMPLIANCE TRACEABILITY",
    summary_fragments=(
        TextFragment("美国虽然没有统一供应链法，但已通过海关执法、贸易法与制裁工具形成事实上的强制追溯框架。"),
        TextFragment("企业真正被审查的不是单票文件，而是能否持续拿出覆盖关键节点的全链条举证体系。", bold=True, color=(173, 5, 61), new_paragraph=True),
    ),
    law_rows=(
        LawRow(
            number="01",
            title="UFLPA 与 CBP 让“完全无涉”成为默认举证责任",
            badge="核心高门槛",
            badge_red=True,
            runs=(
                TextFragment("UFLPA：", bold=True, color=(15, 23, 42)),
                TextFragment("对全部或部分涉及新疆及实体清单的产品适用可反驳推定。"),
                TextFragment(" CBP：", bold=True, color=(15, 23, 42)),
                TextFragment("要求进口商提交从原材料到成品的完整追溯链报告。"),
            ),
        ),
        LawRow(
            number="02",
            title="307 条与 WRO 把全球供应链纳入强迫劳动执法工具",
            badge="全球执法基础",
            badge_red=False,
            runs=(
                TextFragment("307 条：", bold=True, color=(15, 23, 42)),
                TextFragment("禁止全部或部分以强迫劳动生产的产品进入美国。"),
                TextFragment(" WRO：", bold=True, color=(15, 23, 42)),
                TextFragment("触发扣押时，企业必须拿出覆盖来源、生产过程与关键供应商节点的证据链。"),
            ),
        ),
        LawRow(
            number="03",
            title="301 调查与 1502 要求把追溯体系本身纳入审查范围",
            badge="体系延伸",
            badge_red=False,
            runs=(
                TextFragment("301 调查：", bold=True, color=(15, 23, 42)),
                TextFragment("把是否建立反强迫劳动溯源体系纳入贸易执法与谈判评价。"),
                TextFragment(" 1502：", bold=True, color=(15, 23, 42)),
                TextFragment("要求 3TG 追到来源国、冶炼厂和制造环节，并依 OECD 5 步框架披露。"),
            ),
        ),
    ),
    right_kicker="EXECUTION FOCUS",
    right_title="企业不能只补单票材料，而要建立持续可审查的举证操作系统",
    process_steps=("原材料", "零部件", "制造工厂", "物流报关", "美国进口"),
    right_bullets=(
        BulletItem("全链条材料：", "必须保留供应商清单、原料来源、生产地点、合同、发票、生产记录与运输记录。"),
        BulletItem("体系化治理：", "除单票证明外，还要有供应商风险评估、内部审计、第三方审计与数字化追溯系统。"),
        BulletItem("对美交付含义：", "美国审查的是企业是否有能力长期证明整套供应链不涉强迫劳动或高风险来源。"),
    ),
    strategy_title="建设建议：以 UFLPA 为主线，把 307 / 301 / 1502 并入同一举证底座",
    strategy_fragments=(
        TextFragment("建议以 UFLPA 为核心，先把原料来源、生产地点、供应商清单、运输记录与审计证据连成主链；"),
        TextFragment("再叠加 307 条、WRO、301 调查与 1502 的专项字段，", new_paragraph=True),
        TextFragment("形成面向美国执法与客户尽调的统一举证操作系统。", bold=True, color=(255, 255, 255)),
    ),
    footer="STRICTLY CONFIDENTIAL | © 2026 SeiTech (赛意) 供应链与合规数字化平台",
    page_no="04",
    required_terms=("UFLPA", "CBP", "307", "WRO", "301", "1502", "OECD"),
    variant="balanced_dual_panel",
)


def build_slide(output_path: Path, *, export_review: bool = True):
    return build_onepage_slide(US_BRIEF, output_path=output_path, export_review=export_review)


def self_check_layout(prs):
    return shared_self_check_layout(prs, US_BRIEF)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a SIE-template one-page PPT for U.S. supply-chain compliance traceability requirements.")
    parser.add_argument("--output", default=str(OUTPUT_PPT), help="Output PPTX path.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    output, review_path, score_path, _ = build_slide(Path(args.output).resolve())
    print(output)
    print(review_path)
    print(score_path)


__all__ = ["US_BRIEF", "build_slide", "self_check_layout"]


if __name__ == "__main__":
    main()
