from tools.sie_autoppt.batch.contracts import RunSummary, SvgManifest


def test_svg_manifest_round_trip():
    manifest = SvgManifest(
        run_id="run-001",
        bundle_hash="sha256:" + ("a" * 64),
        svg_bundle_hash="sha256:" + ("b" * 64),
        project_root="bridge/svg_project",
        pages=[
            {
                "page_ref": "s-001",
                "svg_path": "bridge/svg_project/svg_final/slide_01.svg",
                "svg_hash": "sha256:" + ("c" * 64),
            }
        ],
    )
    assert manifest.pages[0].page_ref == "s-001"


def test_run_summary_tracks_final_state():
    summary = RunSummary(
        run_id="run-001",
        final_state="SUCCEEDED",
        final_pptx="final/final.pptx",
        bundle_hash="sha256:" + ("a" * 64),
        export_hash="sha256:" + ("b" * 64),
    )
    assert summary.final_state == "SUCCEEDED"
