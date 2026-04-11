from ..models import InputPayload


DEFAULT_EMPTY_OVERVIEW = "补充 phase-* 内容后，可自动生成项目概览页。"
DEFAULT_EMPTY_SCOPE = "补充 scenario 内容后，可自动生成场景分析页。"
DEFAULT_EMPTY_FOCUS = "补充 note 或 footer 内容后，可自动生成重点事项页。"


def format_phase_summary(phase: dict[str, str]) -> str:
    prefix = phase.get("name", "")
    if phase.get("time"):
        prefix = f"{prefix} ({phase['time']})" if prefix else phase["time"]
    detail = phase.get("func") or phase.get("code") or phase.get("owner") or ""
    return f"{prefix}: {detail}".strip(": ").strip()


def build_overview_bullets(payload: InputPayload) -> list[str]:
    bullets = [format_phase_summary(phase) for phase in payload.phases[:4] if format_phase_summary(phase)]
    if bullets:
        return bullets
    fallbacks = [item for item in (payload.subtitle, payload.footer) if item][:4]
    return fallbacks or [DEFAULT_EMPTY_OVERVIEW]


def build_scope_bullets(payload: InputPayload) -> list[str]:
    bullets = payload.scenarios[:4]
    if bullets:
        return bullets
    phase_names = [phase["name"] for phase in payload.phases if phase["name"]][:4]
    return phase_names or [DEFAULT_EMPTY_SCOPE]


def build_focus_bullets(payload: InputPayload) -> list[str]:
    bullets = payload.notes[:4]
    if payload.footer and payload.footer not in bullets:
        bullets.append(payload.footer)
    bullets = bullets[:4]
    return bullets or [DEFAULT_EMPTY_FOCUS]


def build_phase_detail_bullets(payload: InputPayload) -> list[str]:
    bullets = [format_phase_summary(phase) for phase in payload.phases if format_phase_summary(phase)]
    if bullets:
        return bullets[:5]
    fallback = payload.scenarios[:5]
    return fallback or [DEFAULT_EMPTY_SCOPE]


def build_note_detail_bullets(payload: InputPayload) -> list[str]:
    bullets = payload.notes[:5]
    if payload.footer and payload.footer not in bullets:
        bullets.append(payload.footer)
    bullets = bullets[:5]
    if bullets:
        return bullets
    fallback = payload.scenarios[4:9]
    return fallback or [DEFAULT_EMPTY_FOCUS]


def infer_legacy_requested_chapters(payload: InputPayload) -> int:
    weighted_chars = len(payload.title) + len(payload.subtitle) + len(payload.footer)
    weighted_chars += sum(len(item) for item in payload.scenarios)
    weighted_chars += sum(len(item) for item in payload.notes)
    weighted_chars += sum(
        len(phase.get("name", "")) + len(phase.get("func", "")) + len(phase.get("owner", ""))
        for phase in payload.phases
    )
    item_count = len(payload.phases) + len(payload.scenarios) + len(payload.notes)

    if item_count >= 10 or weighted_chars >= 260:
        return 5
    if item_count >= 6 or weighted_chars >= 140:
        return 4
    return 3


def choose_page_pattern(page_key: str, title: str, subtitle: str, bullets: list[str]) -> str:
    hint = f"{title} {subtitle}"
    if any(keyword in hint for keyword in ("风险矩阵", "概率", "影响", "Risk", "risk")):
        return "risk_matrix"
    if any(keyword in hint for keyword in ("索赔", "金额拆解", "成本拆解", "Claim", "claim")):
        return "claim_breakdown"
    if any(keyword in hint for keyword in ("KPI", "指标", "经营", "表现", "目标", "仪表盘")):
        return "kpi_dashboard"
    if any(keyword in hint for keyword in ("路线图", "里程碑", "时间轴", "Roadmap", "roadmap")):
        return "roadmap_timeline"
    if page_key == "overview" and any(keyword in hint for keyword in ("架构", "蓝图", "平台", "体系")):
        return "solution_architecture"
    if page_key == "scope" and any(keyword in hint for keyword in ("链路", "流程", "协同", "路径")):
        return "process_flow"
    if page_key == "focus" and any(keyword in hint for keyword in ("治理", "重点", "要求", "风险", "实施")):
        return "org_governance"
    return ""


__all__ = [
    "build_focus_bullets",
    "build_note_detail_bullets",
    "build_overview_bullets",
    "build_phase_detail_bullets",
    "build_scope_bullets",
    "choose_page_pattern",
    "format_phase_summary",
    "infer_legacy_requested_chapters",
]
