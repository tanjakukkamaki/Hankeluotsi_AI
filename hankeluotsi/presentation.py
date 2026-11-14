"""Local presentation assets and escaped display helpers; no workflow writes."""

import base64
from html import escape
from pathlib import Path

import streamlit as st
from hankeluotsi.i18n import LANGUAGES, localize


PROJECT_ROOT = Path(__file__).resolve().parents[1]
ASSET_DIRECTORY = PROJECT_ROOT / "assets"


def apply_styles() -> None:
    css = (ASSET_DIRECTORY / "styles.css").read_text(encoding="utf-8")
    st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)


def _ui(message: str) -> str:
    return localize(message, st.session_state.get("ui_language", "en"))


def _change_language() -> None:
    """Refresh translated option labels while keeping canonical selections."""
    previous = st.session_state.get("_rendered_language", "en")
    current = st.session_state["ui_language"]
    for key, value in list(st.session_state.items()):
        if not key.startswith(("open_project_id", "live-relevance-", "live-status-", "ranked-live-call-selection-")):
            continue
        if key.endswith("_fi") != (previous == "fi"):
            continue
        base = key[:-3] if previous == "fi" else key
        target = base + ("_fi" if current == "fi" else "")
        st.session_state[target] = value


def render_brand() -> None:
    if st.session_state.get("ui_language") not in LANGUAGES:
        st.session_state["ui_language"] = "en"
    # Streamlit's static shell defaults to English. Only these fixed locale
    # literals enter this script; never include project/model/source content.
    language = "fi" if st.session_state["ui_language"] == "fi" else "en"
    st.html(f'<script>document.documentElement.lang = "{language}";</script>',
            unsafe_allow_javascript=True)
    mark = base64.b64encode((ASSET_DIRECTORY / "hankeluotsi-mark.svg").read_bytes()).decode("ascii")
    with st.container(key="brand_header"):
        icon, name, context = st.columns([0.075, 0.69, 0.235], vertical_alignment="center", gap="small")
        with icon:
            st.markdown(f'<img class="brand-mark" src="data:image/svg+xml;base64,{mark}" alt="{escape(_ui("HankeLuotsi compass: guidance and direction"), quote=True)}" width="52" height="52">', unsafe_allow_html=True)
        with name:
            st.title("HankeLuotsi AI")
            st.markdown('<p class="app-subtitle">' + _ui('From project idea to structured concept') + '</p>', unsafe_allow_html=True)
        with context:
            st.selectbox("Kieli / Language", options=("fi", "en"), format_func=LANGUAGES.get,
                         key="ui_language", label_visibility="collapsed", on_change=_change_language)
            st.session_state["_rendered_language"] = st.session_state["ui_language"]
            st.markdown('<div class="workspace-label"><span class="status-dot"></span> ' + _ui('Personal workspace') + '<span class="workspace-mode">' + _ui('Local-first · Academic prototype') + '</span></div>', unsafe_allow_html=True)


def render_intro() -> None:
    st.markdown(
        '<div class="page-intro"><p class="eyebrow">' + _ui('A CLEARER START FOR YOUR NEXT PROJECT') + '</p>'
        '<h2>' + _ui('Ideas with direction.') + '</h2><p>' + _ui('Shape a project concept, find the gaps and explore official funding sources.') + '</p></div>'
        '<div class="disclaimer-note" role="note"><span class="disclaimer-symbol" aria-hidden="true">i</span>'
        '<div><strong>' + _ui('AI-generated draft.') + '</strong> ' + _ui('Not a funding eligibility assessment. Verify requirements against the relevant funding programme.') + '</div></div>',
        unsafe_allow_html=True,
    )


def anchor(name: str) -> None:
    st.markdown(f'<div id="{escape(name, quote=True)}" class="section-anchor"></div>', unsafe_allow_html=True)


def status_badge(label: str, *, tone: str = "neutral") -> None:
    safe_tone = tone if tone in ("neutral", "teal", "warning", "error") else "neutral"
    st.markdown(f'<span class="status-badge {safe_tone}">{escape(label)}</span>', unsafe_allow_html=True)
