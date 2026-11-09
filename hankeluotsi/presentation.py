"""Local presentation assets and escaped display helpers; no workflow writes."""

import base64
from html import escape
from pathlib import Path

import streamlit as st


PROJECT_ROOT = Path(__file__).resolve().parents[1]
ASSET_DIRECTORY = PROJECT_ROOT / "assets"


def apply_styles() -> None:
    css = (ASSET_DIRECTORY / "styles.css").read_text(encoding="utf-8")
    st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)


def render_brand() -> None:
    mark = base64.b64encode((ASSET_DIRECTORY / "hankeluotsi-mark.svg").read_bytes()).decode("ascii")
    with st.container(key="brand_header"):
        icon, name, context = st.columns([0.075, 0.69, 0.235], vertical_alignment="center", gap="small")
        with icon:
            st.markdown(f'<img class="brand-mark" src="data:image/svg+xml;base64,{mark}" alt="HankeLuotsi compass: guidance and direction" width="52" height="52">', unsafe_allow_html=True)
        with name:
            st.title("HankeLuotsi AI")
            st.markdown('<p class="app-subtitle">From project idea to structured concept</p>', unsafe_allow_html=True)
        with context:
            st.markdown('<div class="workspace-label"><span class="status-dot"></span> Personal workspace<span class="workspace-mode">Local-first · Academic prototype</span></div>', unsafe_allow_html=True)


def render_intro() -> None:
    st.markdown(
        '<div class="page-intro"><p class="eyebrow">A CLEARER START FOR YOUR NEXT PROJECT</p>'
        '<h2>Ideas with direction.</h2><p>Shape a project concept, find the gaps and explore official funding sources.</p></div>'
        '<div class="disclaimer-note" role="note"><span class="disclaimer-symbol" aria-hidden="true">i</span>'
        '<div><strong>AI-generated draft.</strong> Not a funding eligibility assessment. '
        'Verify requirements against the relevant funding programme.</div></div>',
        unsafe_allow_html=True,
    )
    has_project = bool(st.session_state.get("open_project_id") or st.session_state.get("pr5_pending_project_id"))
    concept_target = "#concept-paper" if has_project else "#project-workspace"
    funding_target = "#funding-opportunities" if has_project else "#project-workspace"
    steps = (
        ("01", "Shape the idea", "A focused starting point", "#project-workspace", "available"),
        ("02", "Build the concept", "A structured working draft", concept_target, "available"),
        ("03", "Check & explore", "Consistency and official sources", funding_target, "available"),
        ("04", "Draft & review", "Planned · not available yet", None, "planned"),
    )
    cards = []
    for number, title, subtitle, target, state in steps:
        content = f'<span class="workflow-number">{number}</span><span><strong>{title}</strong><small>{subtitle}</small></span>'
        cards.append(f'<a class="workflow-step {state}" href="{target}">{content}</a>' if target else f'<div class="workflow-step {state}" aria-disabled="true">{content}</div>')
    st.markdown('<nav class="workflow-strip" aria-label="Planning workflow">' + "".join(cards) + '</nav>', unsafe_allow_html=True)


def anchor(name: str) -> None:
    st.markdown(f'<div id="{escape(name, quote=True)}" class="section-anchor"></div>', unsafe_allow_html=True)


def status_badge(label: str, *, tone: str = "neutral") -> None:
    safe_tone = tone if tone in ("neutral", "teal", "warning", "error") else "neutral"
    st.markdown(f'<span class="status-badge {safe_tone}">{escape(label)}</span>', unsafe_allow_html=True)
