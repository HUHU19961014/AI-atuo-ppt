import argparse
import sys
from pathlib import Path


def _bootstrap():
    tools_dir = Path(__file__).resolve().parent
    if str(tools_dir) not in sys.path:
        sys.path.insert(0, str(tools_dir))


_bootstrap()

from sie_autoppt.powerpoint import open_powerpoint_application


def repair_directory_slides_with_com(pptx_path: Path, source_idx: int, target_indices: list[int]) -> bool:
    app = open_powerpoint_application()
    pres = app.Presentations.Open(str(pptx_path.resolve()), WithWindow=False)
    try:
        for target in sorted(target_indices, reverse=True):
            pres.Slides(target).Delete()
            duplicate = pres.Slides(source_idx).Duplicate()
            duplicate.Item(1).MoveTo(target)
        pres.Save()
        return True
    finally:
        pres.Close()
        app.Quit()


def main():
    parser = argparse.ArgumentParser(description="Repair duplicated directory slides via PowerPoint COM.")
    parser.add_argument("pptx_path", help="Path to target PPTX.")
    parser.add_argument("--source-idx", type=int, required=True, help="1-based source slide index.")
    parser.add_argument("--targets", type=int, nargs="+", required=True, help="1-based target slide indices.")
    args = parser.parse_args()

    ok = repair_directory_slides_with_com(Path(args.pptx_path), args.source_idx, args.targets)
    if not ok:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
