import argparse
import sys
from pathlib import Path


def _bootstrap():
    tools_dir = Path(__file__).resolve().parent
    if str(tools_dir) not in sys.path:
        sys.path.insert(0, str(tools_dir))


_bootstrap()

from sie_autoppt.powerpoint import open_powerpoint_application


def parse_mapping(items: list[str]) -> list[tuple[int, int]]:
    mappings = []
    for item in items:
        target, source = item.split("=", 1)
        mappings.append((int(target), int(source)))
    return mappings


def apply_reference_body_slides(target_pptx: Path, reference_pptx: Path, mappings: list[tuple[int, int]]) -> bool:
    app = open_powerpoint_application()
    pres = app.Presentations.Open(
        str(target_pptx.resolve()),
        ReadOnly=False,
        Untitled=False,
        WithWindow=False,
    )
    try:
        for target_slide, source_slide in sorted(mappings, reverse=True):
            pres.Slides(target_slide).Delete()
            pres.Slides.InsertFromFile(str(reference_pptx.resolve()), target_slide - 1, source_slide, source_slide)
        pres.Save()
        return True
    finally:
        pres.Close()
        app.Quit()


def main():
    parser = argparse.ArgumentParser(description="Replace placeholder body slides with reference slides via PowerPoint COM.")
    parser.add_argument("target_pptx", help="Target PPTX path.")
    parser.add_argument("reference_pptx", help="Reference body PPTX path.")
    parser.add_argument("--mapping", nargs="+", required=True, help="Pairs in target=source format, e.g. 4=5 6=16")
    args = parser.parse_args()

    ok = apply_reference_body_slides(
        Path(args.target_pptx),
        Path(args.reference_pptx),
        parse_mapping(args.mapping),
    )
    if not ok:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
