from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import streamlit as st


PROJECT_ROOT = Path(__file__).resolve().parents[1]
ENTRYPOINT = PROJECT_ROOT / "main.py"


def _run_command(args: list[str]) -> tuple[int, str, str]:
    result = subprocess.run(
        [sys.executable, str(ENTRYPOINT), *args],
        capture_output=True,
        text=True,
        cwd=str(PROJECT_ROOT),
        timeout=900,
    )
    return result.returncode, result.stdout.strip(), result.stderr.strip()


st.set_page_config(page_title="Enterprise-AI-PPT", page_icon="📊", layout="wide")
st.title("Enterprise-AI-PPT Web UI (Preview)")
st.caption("P3 lightweight UI preview built on Streamlit")

tab_generate, tab_patch = st.tabs(["Generate", "Patch Existing Deck"])

with tab_generate:
    st.subheader("One-shot Generation")
    topic = st.text_input("Topic", placeholder="Enterprise AI adoption roadmap")
    brief = st.text_area("Brief", placeholder="Audience, context, and expected output.")
    min_slides = st.number_input("Min slides", min_value=1, max_value=20, value=6)
    max_slides = st.number_input("Max slides", min_value=1, max_value=20, value=8)
    model = st.text_input("LLM model override (optional)")
    if st.button("Run make", type="primary"):
        if not topic.strip():
            st.error("Topic is required.")
        else:
            cmd = [
                "make",
                "--topic",
                topic.strip(),
                "--brief",
                brief.strip(),
                "--min-slides",
                str(min_slides),
                "--max-slides",
                str(max_slides),
                "--progress",
            ]
            if model.strip():
                cmd.extend(["--llm-model", model.strip()])
            with st.spinner("Running generation pipeline..."):
                code, out, err = _run_command(cmd)
            st.code("python main.py " + " ".join(cmd), language="bash")
            if code == 0:
                st.success("Generation finished.")
                st.text_area("Output", out, height=160)
            else:
                st.error(f"Generation failed (exit={code}).")
                st.text_area("Error", err or out, height=220)

with tab_patch:
    st.subheader("Incremental Deck Patch")
    deck_json = st.text_input("Deck JSON path", value=str(PROJECT_ROOT / "output" / "generated_deck.json"))
    patch_json = st.text_input("Patch JSON path", value=str(PROJECT_ROOT / "output" / "patches_round_1.json"))
    patch_output = st.text_input("Output path", value=str(PROJECT_ROOT / "output" / "generated_deck.patched.json"))
    if st.button("Run v2-patch"):
        cmd = [
            "v2-patch",
            "--deck-json",
            deck_json.strip(),
            "--patch-json",
            patch_json.strip(),
            "--plan-output",
            patch_output.strip(),
            "--progress",
        ]
        with st.spinner("Applying patch set..."):
            code, out, err = _run_command(cmd)
        st.code("python main.py " + " ".join(cmd), language="bash")
        if code == 0:
            st.success("Patch applied.")
            st.text_area("Output", out, height=120)
        else:
            st.error(f"Patch failed (exit={code}).")
            st.text_area("Error", err or out, height=220)
