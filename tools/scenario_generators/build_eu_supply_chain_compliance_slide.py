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
OUTPUT_PPT = PROJECT_ROOT / "output" / "eu_supply_chain_compliance_sie_template_onepage.pptx"

EU_BRIEF = OnePageBrief(
    title="对欧出口供应链合规追溯要求：欧盟法律强制与光伏 SSI 双层约束",
    kicker="EU COMPLIANCE TRACEABILITY",
    summary_fragments=(
        TextFragment("欧洲正通过欧盟法、国家法、行业标准与绿色采购压力，形成多层叠加的供应链追溯门槛。"),
        TextFragment("对光伏企业而言，真正的进入门槛已经从“能否出货”升级为“能否持续举证并对接 SSI 数据体系”。", bold=True, color=(173, 5, 61), new_paragraph=True),
    ),
    law_rows=(
        LawRow(
            number="01",
            title="欧盟顶层法律把追溯义务上升为刚性合规要求",
            badge="核心强约束",
            badge_red=True,
            runs=(
                TextFragment("CSDDD：", bold=True, color=(15, 23, 42)),
                TextFragment("要求企业建立供应链地图、识别高风险节点并保留合同、生产记录与审计证据。"),
                TextFragment(" EUFLR：", bold=True, color=(15, 23, 42)),
                TextFragment("一旦被抽查，进口商必须举证产品全链条不存在强迫劳动风险。"),
            ),
        ),
        LawRow(
            number="02",
            title="国家法与专项规例把责任链继续向上游穿透",
            badge="先行落地",
            badge_red=False,
            runs=(
                TextFragment("德国 LkSG：", bold=True, color=(15, 23, 42)),
                TextFragment("要求 Tier-1 及高风险 Tier-2 做尽调与审计，形成可追溯责任链。"),
                TextFragment(" CMR：", bold=True, color=(15, 23, 42)),
                TextFragment("要求 3TG 依 OECD 5 步框架追到来源国、冶炼厂与制造环节。"),
            ),
        ),
        LawRow(
            number="03",
            title="市场端已经把“可查询、可验证”变成事实准入门槛",
            badge="事实门槛",
            badge_red=False,
            runs=(
                TextFragment("客户、投资者与绿色采购方", bold=True, color=(15, 23, 42)),
                TextFragment("不仅看供应商名单，更看批次级数据、审计链路与是否能按 SSI 结构稳定输出。"),
            ),
        ),
    ),
    right_kicker="INDUSTRY FOCUS",
    right_title="光伏行业的关键差异在于：SSI 提供了法律合规的技术落地路径",
    process_steps=("石英矿", "多晶硅", "硅片", "电池片", "组件"),
    right_bullets=(
        BulletItem("批次级追溯：", "SSI 要求从石英矿到组件实现每批次可追溯，覆盖供应商、原料类型、数量、批次与生产日期。"),
        BulletItem("系统化验证：", "企业需要用 MES、ERP 或追溯平台让信息可查询、可验证，并与 ISO 22095 等监管链思路对接。"),
        BulletItem("对欧交付含义：", "先用 SSI 搭建字段、系统与流程，再以同一底座响应 CSDDD / EUFLR 的尽调与抽查要求。"),
    ),
    strategy_title="建设建议：先搭 SSI 底座，再向欧盟法规义务映射",
    strategy_fragments=(
        TextFragment("建议把 SSI 作为光伏行业的主数据骨架，先固化批次、供应商、生产日期、审计证据等关键字段；"),
        TextFragment("再映射到 CSDDD、EUFLR 与欧洲客户尽调要求，", new_paragraph=True),
        TextFragment("实现“一次建设、欧盟法规与行业标准双重覆盖”。", bold=True, color=(255, 255, 255)),
    ),
    footer="STRICTLY CONFIDENTIAL | © 2026 SeiTech (赛意) 供应链与合规数字化平台",
    page_no="03",
    required_terms=("CSDDD", "EUFLR", "LkSG", "SSI", "ISO 22095", "SEIA 101"),
    variant="signal_band",
)


def build_slide(output_path: Path, *, export_review: bool = True):
    return build_onepage_slide(EU_BRIEF, output_path=output_path, export_review=export_review)


def self_check_layout(prs):
    return shared_self_check_layout(prs, EU_BRIEF)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a SIE-template one-page PPT for EU supply-chain compliance traceability requirements.")
    parser.add_argument("--output", default=str(OUTPUT_PPT), help="Output PPTX path.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    output, review_path, score_path, _ = build_slide(Path(args.output).resolve())
    print(output)
    print(review_path)
    print(score_path)


__all__ = ["EU_BRIEF", "build_slide", "self_check_layout"]


if __name__ == "__main__":
    main()
