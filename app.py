import html as _html
import json
import pathlib
import random
import re as _re
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime, timedelta, timezone
from urllib.parse import urlencode

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import requests
from requests.adapters import HTTPAdapter
import streamlit as st
import streamlit.components.v1 as components
import yfinance as yf

# ── Page config ───────────────────────────────────────────────────────────────
# Favicon: the INSIDER ✦ mark (white sparkle on black). Load the committed PNG
# by an absolute path so it resolves on Streamlit Cloud; fall back to the ✦ glyph
# if the file is ever missing.
_FAVICON = pathlib.Path(__file__).parent / "favicon.png"
try:
    from PIL import Image as _PILImage
    _page_icon = _PILImage.open(_FAVICON) if _FAVICON.exists() else "✦"
except Exception:
    _page_icon = "✦"

st.set_page_config(
    page_title="INSIDER — SEC Form 4 Intelligence",
    page_icon=_page_icon,
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── CSS ───────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;500;600;700&family=IBM+Plex+Mono:wght@400;500;600&family=Inter+Tight:wght@400;500;600&display=swap');

:root {
    --ink:        #000000;
    --paper:      #ffffff;
    --fog:        #8a8a8a;
    --ash:        #5f5f5f;
    --dim:        #3a3a3a;
    --line:       #1a1a1a;
    --line-2:     #2c2c2c;
    --buy:        #4ade80;
    --sell:       #f87171;
    --buy-solid:  #22c55e;
    --sell-solid: #ef4444;
    --font-display: 'Space Grotesk', 'Inter Tight', sans-serif;
    --font-mono:    'IBM Plex Mono', ui-monospace, 'SF Mono', monospace;
    --font-body:    'Inter Tight', -apple-system, BlinkMacSystemFont, sans-serif;
}

/* ── Global ── */
*, *::before, *::after {
    font-family: var(--font-body);
    box-sizing: border-box;
}

/* Scrollbar — thin, monochrome (matches the reference) */
::-webkit-scrollbar        { width: 8px; height: 8px; }
::-webkit-scrollbar-thumb  { background: #2a2a2a; }
::-webkit-scrollbar-thumb:hover { background: #3a3a3a; }
::-webkit-scrollbar-track  { background: #000; }

/* Inverted selection */
::selection { background: #fff; color: #000; }

/* ── Hide all Streamlit chrome ── */
#MainMenu,
header[data-testid="stHeader"],
footer,
[data-testid="stToolbar"],
[data-testid="stDecoration"],
[data-testid="stStatusWidget"] {
    display: none !important;
    visibility: hidden !important;
}

/* ── App background — pure black ── */
.stApp {
    background-color: #000;
    color: #e0e0e0;
}

/* ── Push content below fixed navbar ── */
.main .block-container {
    padding-top: 96px !important;
    padding-bottom: 104px !important;
    max-width: 1440px;
}

/* ── Sidebar ── */
section[data-testid="stSidebar"] {
    background-color: #000;
    border-right: 1px solid var(--line);
}
section[data-testid="stSidebar"] [data-testid="stWidgetLabel"] p,
section[data-testid="stSidebar"] label {
    font-family: var(--font-mono) !important;
    text-transform: uppercase !important;
    font-size: 10px !important;
    letter-spacing: 0.14em !important;
    color: var(--ash) !important;
    font-weight: 500 !important;
}
/* inputs + selects, both sidebar and main */
input, textarea,
div[data-baseweb="select"] > div,
div[data-baseweb="input"] > div {
    background-color: #0a0a0a !important;
    border-color: var(--line-2) !important;
    border-radius: 0 !important;
    color: #d0d0d0 !important;
}
div[data-baseweb="tag"] {
    background-color: #161616 !important;
    border-radius: 0 !important;
    font-family: var(--font-mono) !important;
}

/* ── Buttons — brutalist invert on hover ── */
.stButton > button,
.stDownloadButton > button {
    background: transparent !important;
    border: 1px solid var(--line-2) !important;
    color: #e8e8e8 !important;
    font-family: var(--font-mono) !important;
    font-weight: 500 !important;
    font-size: 11px !important;
    letter-spacing: 0.14em !important;
    text-transform: uppercase !important;
    padding: 11px 16px !important;
    border-radius: 0 !important;
    transition: background 0.18s ease, color 0.18s ease, border-color 0.18s ease !important;
    width: 100%;
}
.stButton > button:hover,
.stDownloadButton > button:hover {
    background: #fff !important;
    border-color: #fff !important;
    color: #000 !important;
}
.stButton > button:focus-visible,
.stDownloadButton > button:focus-visible {
    outline: 2px solid #fff !important;
    outline-offset: 2px !important;
}

/* ── KPI Grid — boxed hairline grid ── */
.kpi-grid {
    display: grid;
    grid-template-columns: repeat(7, 1fr);
    gap: 1px;
    background: var(--line);
    border: 1px solid var(--line);
    margin-bottom: 56px;
}
.kpi-card {
    position: relative;
    background: #000;
    padding: 26px 22px 24px;
    overflow: hidden;
    transition: background 0.2s ease;
}
.kpi-card::before {
    content: '';
    position: absolute;
    top: 0; left: 0; right: 0;
    height: 2px; background: #fff;
    transform: scaleX(0); transform-origin: left;
    transition: transform 0.3s cubic-bezier(0.22,1,0.36,1);
}
.kpi-card:hover           { background: #080808; }
.kpi-card:hover::before   { transform: scaleX(1); }

.kpi-label {
    font-family: var(--font-mono);
    color: var(--ash);
    font-size: 10px; font-weight: 500;
    text-transform: uppercase; letter-spacing: 0.12em;
    margin-bottom: 18px;
}
.kpi-value {
    font-family: var(--font-display);
    color: #fff;
    font-size: 2.4rem; font-weight: 500;
    font-variant-numeric: tabular-nums;
    line-height: 1; letter-spacing: -0.02em;
}
.kpi-desc {
    font-family: var(--font-mono);
    color: var(--dim);
    font-size: 9.5px; margin-top: 12px; line-height: 1.5;
    text-transform: uppercase; letter-spacing: 0.04em;
}
@media (max-width: 1200px) { .kpi-grid { grid-template-columns: repeat(4, 1fr); } }
@media (max-width: 720px)  { .kpi-grid { grid-template-columns: repeat(2, 1fr); } }

/* ── Live pulse ── */
@keyframes livePulse {
    0%, 100% { opacity: 1; box-shadow: 0 0 0 0 rgba(34,197,94,0.5); }
    50%       { opacity: 0.7; box-shadow: 0 0 0 6px rgba(34,197,94,0); }
}
.live-dot {
    display: inline-block; width: 7px; height: 7px;
    background: #22c55e; border-radius: 50%;
    margin-right: 4px; vertical-align: middle;
    animation: livePulse 2s ease-in-out infinite;
}

/* ── Skeleton shimmer ── */
@keyframes shimmer {
    0%   { background-position: -800px 0; }
    100% { background-position:  800px 0; }
}
.shimmer {
    background: linear-gradient(90deg, #080808 25%, #171717 50%, #080808 75%);
    background-size: 1600px 100%;
    animation: shimmer 1.8s ease-in-out infinite;
}
.skel-kpi-grid { display: flex; gap: 1px; margin-bottom: 56px; }
.skel-kpi      { flex: 1; height: 116px; }
.skel-charts   { display: flex; gap: 24px; margin: 0 0 24px; }
.skel-chart    { flex: 1; height: 280px; }
.skel-table    { width: 100%; height: 420px; }

/* ── Chart fade-in ── */
@keyframes chartFadeIn {
    from { opacity: 0; transform: translateY(12px); }
    to   { opacity: 1; transform: translateY(0); }
}
.stPlotlyChart { animation: chartFadeIn 0.5s ease-out both; }

/* ── Cursor glow — faint monochrome ── */
#cursor-glow {
    position: fixed; width: 460px; height: 460px; border-radius: 50%;
    background: radial-gradient(circle, rgba(255,255,255,0.028) 0%, transparent 66%);
    pointer-events: none;
    transform: translate(-50%, -50%);
    z-index: 0; will-change: left, top;
    transition: left 0.07s linear, top 0.07s linear;
}

/* ── Navbar (injected into parent frame) ── */
#top-navbar {
    position: fixed; top: 0; left: 0; right: 0; z-index: 999999;
    height: 60px;
    background: #000;
    border-bottom: 1px solid var(--line);
    display: flex; align-items: center;
    padding: 0 28px;
    justify-content: space-between;
}
#top-navbar .nav-brand {
    display: flex; align-items: baseline; gap: 3px;
    text-decoration: none; cursor: default;
}
#top-navbar .nav-wordmark {
    font-family: var(--font-display);
    font-size: 15px; font-weight: 700; letter-spacing: 0.26em;
    color: #fff;
}
#top-navbar .nav-mark {
    font-family: var(--font-display);
    color: #fff; font-size: 12px; margin-left: 2px;
}
#top-navbar .nav-tag {
    font-family: var(--font-mono);
    font-size: 10px; letter-spacing: 0.16em; text-transform: uppercase;
    color: var(--ash);
}
#top-navbar .nav-right {
    display: flex; align-items: center; gap: 22px;
}
#top-navbar .nav-pill-live {
    display: flex; align-items: center; gap: 7px;
    font-family: var(--font-mono);
    font-size: 10px; letter-spacing: 0.16em; text-transform: uppercase;
    color: #e8e8e8;
}
#top-navbar .nav-right a {
    font-family: var(--font-mono);
    font-size: 11px; letter-spacing: 0.12em; text-transform: uppercase;
    color: var(--fog); text-decoration: none;
    transition: color 0.15s ease;
}
#top-navbar .nav-right a:hover { color: #fff; }
@media (max-width: 720px) { #top-navbar .nav-tag { display: none; } }

/* ── Hero section — editorial, oversized ── */
.hero-section {
    padding: 8px 0 40px;
    border-bottom: 1px solid var(--line);
    margin-bottom: 52px;
}
.hero-topline {
    display: flex; justify-content: space-between; align-items: flex-start;
    border-top: 1px solid var(--line);
    padding-top: 16px; margin-bottom: 54px;
    font-family: var(--font-mono);
    font-size: 10.5px; letter-spacing: 0.14em; text-transform: uppercase;
    color: var(--ash); line-height: 1.9;
}
.hero-topline .right { text-align: right; }
.hero-headline {
    font-family: var(--font-display);
    font-weight: 700;
    font-size: clamp(42px, 8.6vw, 116px);
    line-height: 0.9; letter-spacing: -0.035em;
    color: #fff; margin: 0; text-transform: uppercase;
}
.hero-foot {
    display: flex; justify-content: space-between; align-items: flex-end;
    margin-top: 40px; gap: 28px; flex-wrap: wrap;
}
.hero-sub {
    font-family: var(--font-body);
    font-size: 15px; color: var(--fog); line-height: 1.6;
    max-width: 460px; margin: 0;
}
.hero-meta {
    display: flex; align-items: center; gap: 14px; flex-wrap: wrap;
    font-family: var(--font-mono);
    font-size: 10.5px; letter-spacing: 0.1em; text-transform: uppercase;
    color: var(--ash);
}
.hero-live { display: flex; align-items: center; gap: 6px; color: #e8e8e8; }
.hero-meta-sep { color: var(--line-2); }

/* ── Section label ── */
.section-label {
    font-family: var(--font-mono);
    font-size: 10.5px; font-weight: 500; letter-spacing: 0.14em;
    text-transform: uppercase; color: var(--fog);
    margin-bottom: 20px; padding-bottom: 12px;
    border-bottom: 1px solid var(--line);
}

/* ── Sidebar chrome ── */
.sidebar-brand {
    padding: 26px 0 14px;
    border-bottom: 1px solid var(--line);
    margin-bottom: 6px;
}
.sidebar-brand-label {
    font-family: var(--font-mono);
    font-size: 9px; letter-spacing: 0.22em;
    text-transform: uppercase; color: var(--dim); margin-bottom: 8px;
}
.sidebar-brand-title {
    font-family: var(--font-display);
    font-size: 18px; font-weight: 600; color: #fff;
    letter-spacing: 0.04em; text-transform: uppercase;
}
.sidebar-div {
    height: 1px; background: var(--line); margin: 16px 0;
}
.sidebar-footer {
    font-family: var(--font-mono);
    font-size: 9px; color: var(--dim); line-height: 1.9; padding-top: 6px;
    text-transform: uppercase; letter-spacing: 0.06em;
}

/* ── Table ── */
.filing-table {
    width: 100%; border-collapse: collapse;
    font-size: 12.5px; table-layout: fixed;
}
.filing-table th {
    background-color: #000;
    color: var(--ash);
    padding: 13px 12px;
    text-align: left;
    border-bottom: 1px solid var(--line-2);
    font-family: var(--font-mono);
    font-size: 9.5px; font-weight: 500;
    text-transform: uppercase; letter-spacing: 0.12em;
    white-space: nowrap; overflow: hidden;
    position: sticky; top: 0; z-index: 1;
}
.filing-table td {
    padding: 11px 12px;
    border-bottom: 1px solid #101010;
    vertical-align: middle; overflow: hidden; text-overflow: ellipsis;
    transition: background-color 0.12s ease;
    color: #c4c4c4;
}
.filing-table .col-date   { width: 90px;  white-space: nowrap; }
.filing-table .col-txn    { width: 78px;  white-space: nowrap; }
.filing-table .col-exec   { width: 150px; }
.filing-table .col-title  { width: 130px; }
.filing-table .col-co     { width: 185px; }
.filing-table .col-sector { width: 110px; }
.filing-table .col-shares { width: 80px;  white-space: nowrap; text-align: right; }
.filing-table .col-value  { width: 82px;  white-space: nowrap; text-align: right; }
.filing-table .col-ret    { width: 155px; white-space: nowrap; }
.filing-table .col-link   { width: 60px;  white-space: nowrap; }

.filing-table tbody tr td { background-color: #000; }
.filing-table tr:hover td              { background-color: #0b0b0b !important; }
.filing-table tr:hover td:first-child  { box-shadow: inset 2px 0 0 #fff; }
.filing-table tr.notable td              { background-color: #050805 !important; }
.filing-table tr.notable td:first-child  { box-shadow: inset 2px 0 0 var(--buy-solid); }
.filing-table a { color: #e8e8e8; text-decoration: none; font-weight: 500; }
.filing-table a:hover { color: #fff; text-decoration: underline; }
.exec-name { font-family: var(--font-body); font-weight: 600; color: #fff; }
.co-name   { font-family: var(--font-mono); color: var(--ash); font-size: 11px; letter-spacing: 0.02em; }
.notable-flag { color: var(--buy-solid); font-size: 8px; margin-right: 6px; vertical-align: middle; }

/* ── Transaction tags ── */
.txn-pill {
    display: inline-flex; align-items: center; justify-content: center;
    padding: 3px 9px; border-radius: 0;
    font-family: var(--font-mono);
    font-size: 9.5px; font-weight: 500; letter-spacing: 0.1em;
    text-transform: uppercase; white-space: nowrap; border: 1px solid;
}
.txn-buy   { color: var(--buy);  border-color: rgba(74,222,128,0.35);  background: rgba(74,222,128,0.06); }
.txn-sell  { color: var(--sell); border-color: rgba(248,113,113,0.35); background: rgba(248,113,113,0.06); }
.txn-award { color: #e8e8e8;     border-color: var(--line-2);          background: transparent; }
.txn-other { color: var(--ash);  border-color: var(--line);            background: transparent; }

/* ── Ticker tag ── */
.ticker-pill {
    display: inline-block;
    font-family: var(--font-mono);
    color: #e8e8e8; border: 1px solid var(--line-2);
    border-radius: 0; padding: 1px 5px; font-size: 9.5px;
    font-weight: 500; letter-spacing: 0.08em;
    margin-left: 6px; vertical-align: middle;
}

/* ── Badges ── */
.badge {
    display: inline-block;
    font-family: var(--font-mono);
    color: #e8e8e8; border: 1px solid var(--line-2);
    border-radius: 0; padding: 3px 10px;
    font-size: 10px; font-weight: 500;
    letter-spacing: 0.08em; text-transform: uppercase;
}
.badge-alert {
    color: var(--buy); border-color: rgba(74,222,128,0.4);
}

/* ── SEC link button ── */
.filing-link-btn {
    display: inline-block;
    padding: 3px 9px;
    border: 1px solid var(--line-2);
    border-radius: 0;
    color: #e8e8e8 !important;
    font-family: var(--font-mono);
    font-size: 9.5px; font-weight: 500; letter-spacing: 0.08em;
    text-transform: uppercase;
    text-decoration: none !important;
    transition: background 0.15s ease, color 0.15s ease, border-color 0.15s ease;
    white-space: nowrap;
}
.filing-link-btn:hover {
    border-color: #fff;
    background: #fff;
    color: #000 !important;
    text-decoration: none !important;
}
.filing-link-btn:active { transform: scale(0.95); }

/* ── Toast ── */
#toast-container {
    position: fixed; bottom: 28px; right: 28px;
    z-index: 99999; display: flex; flex-direction: column;
    gap: 8px; pointer-events: none;
}
.st-toast {
    background: #000; border: 1px solid var(--line-2);
    border-left: 2px solid #fff; border-radius: 0;
    padding: 14px 20px;
    font-family: var(--font-mono);
    font-size: 11px; letter-spacing: 0.06em; text-transform: uppercase;
    color: #e8e8e8;
    box-shadow: 0 20px 60px rgba(0,0,0,0.8); min-width: 240px;
    opacity: 0; transform: translateX(16px);
    transition: opacity 0.3s ease, transform 0.3s ease;
}
.st-toast.toast-show { opacity: 1; transform: translateX(0); }

@media (prefers-reduced-motion: reduce) {
    .stPlotlyChart    { animation: none !important; }
    .shimmer          { animation: none !important; }
    #cursor-glow      { display: none !important; }
    .st-toast         { transition: none !important; }
    .live-dot         { animation: none !important; }
    .kpi-card::before { transition: none !important; }
}

hr { border: none; border-top: 1px solid var(--line); margin: 36px 0; }
h2 { color: #e0e0e0 !important; font-family: var(--font-mono) !important;
     font-size: 12px !important; font-weight: 500 !important;
     letter-spacing: 0.12em !important; text-transform: uppercase !important; }

/* ── About section ── */
.about-section { margin-top: 8px; }
.about-grid {
    display: grid; grid-template-columns: 1.7fr 1fr; gap: 56px;
    border-top: 1px solid var(--line); padding-top: 32px;
}
.about-h {
    font-family: var(--font-mono);
    font-size: 10px; font-weight: 600; letter-spacing: 0.14em;
    text-transform: uppercase; color: #e8e8e8;
    margin: 0 0 12px 0;
}
.about-p {
    font-family: var(--font-body);
    font-size: 14px; line-height: 1.7; color: var(--fog);
    margin: 0 0 28px 0; max-width: 640px;
}
.about-p em { font-style: italic; color: #dde6f0; }
.about-col.about-side { border-left: 1px solid var(--line); padding-left: 40px; }
.about-name {
    font-family: var(--font-display);
    font-size: 22px; font-weight: 600; color: #fff;
    margin: 0 0 6px 0; letter-spacing: -0.01em;
}
.about-meta {
    font-family: var(--font-mono);
    font-size: 11px; line-height: 1.7; color: var(--ash);
    text-transform: uppercase; letter-spacing: 0.08em; margin: 0 0 24px 0;
}
.about-link {
    display: inline-block;
    font-family: var(--font-mono);
    font-size: 11px; letter-spacing: 0.08em; text-transform: uppercase;
    color: #fff; text-decoration: none;
    border: 1px solid var(--line-2); padding: 10px 16px;
    transition: background 0.18s ease, color 0.18s ease, border-color 0.18s ease;
}
.about-link:hover { background: #fff; color: #000; border-color: #fff; }
.about-disclaimer {
    font-family: var(--font-mono);
    font-size: 9px; color: var(--dim); letter-spacing: 0.06em;
    text-transform: uppercase; margin: 22px 0 0 0; line-height: 1.7;
}
@media (max-width: 820px) {
    .about-grid { grid-template-columns: 1fr; gap: 32px; }
    .about-col.about-side { border-left: none; padding-left: 0;
        border-top: 1px solid var(--line); padding-top: 28px; }
}

/* ── Search bar ── */
.st-key-search_query input {
    width: 100% !important;
    background: #0a0a0a url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='18' height='18' viewBox='0 0 24 24' fill='none' stroke='%238a8a8a' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'%3E%3Ccircle cx='11' cy='11' r='7'/%3E%3Cline x1='21' y1='21' x2='16.65' y2='16.65'/%3E%3C/svg%3E") no-repeat 20px center !important;
    border: 1px solid var(--line-2) !important;
    border-radius: 0 !important;
    height: 60px !important;
    font-family: var(--font-body) !important;
    font-size: 15px !important;
    color: #f1f5f9 !important;
    padding: 0 20px 0 54px !important;
    letter-spacing: 0.01em;
    transition: border-color 0.18s ease !important;
}
.st-key-search_query input::placeholder { color: var(--ash) !important; }
.st-key-search_query input:focus {
    border-color: #ffffff !important;
    box-shadow: none !important;
}
.st-key-clear_search button {
    height: 60px !important;
    border-radius: 0 !important;
    border: 1px solid var(--line-2) !important;
    color: var(--fog) !important;
    font-size: 15px !important;
    letter-spacing: 0 !important;
    padding: 0 !important;
}
.st-key-clear_search button:hover {
    background: #fff !important; color: #000 !important; border-color: #fff !important;
}
.search-meta {
    font-family: var(--font-mono);
    font-size: 11px; letter-spacing: 0.1em; text-transform: uppercase;
    color: var(--ash); margin: 14px 2px 44px;
}
.search-meta .q { color: #e8e8e8; text-transform: none; letter-spacing: 0; }

/* ── Date preset pills ── */
.preset-label {
    font-family: var(--font-mono);
    font-size: 10px; font-weight: 500; letter-spacing: 0.14em;
    text-transform: uppercase; color: var(--ash); margin: 2px 0 8px;
}
div[class*="st-key-preset_"] button {
    height: 30px !important;
    min-height: 0 !important;
    padding: 0 !important;
    font-size: 10px !important;
    letter-spacing: 0.06em !important;
    border-radius: 0 !important;
}
div[class*="st-key-preset_"] button[kind="primary"],
div[class*="st-key-preset_"] button[data-testid*="rimary"] {
    background: #fff !important;
    color: #000 !important;
    border-color: #fff !important;
}

/* ── Cluster badge (table) ── */
.cluster-badge {
    display: inline-block;
    font-family: var(--font-mono);
    font-size: 8px; font-weight: 600; letter-spacing: 0.1em;
    color: #f59e0b; text-transform: uppercase;
    border: 1px solid rgba(245,158,11,0.45);
    border-radius: 0; padding: 1px 5px; margin-left: 6px;
    vertical-align: middle;
}

/* ── Watchlist star (table) ── */
.star-btn {
    display: inline-block; width: 16px; text-align: center;
    font-size: 14px; line-height: 1; margin-right: 8px;
    text-decoration: none !important; vertical-align: middle;
    transition: color 0.15s ease, transform 0.1s ease;
}
.star-btn.star-on  { color: #ffffff; }
.star-btn.star-off { color: #333333; }
.star-btn.star-off:hover { color: #8a8a8a; }
.star-btn.star-on:hover  { color: #cbd5e1; }
.star-btn:active { transform: scale(0.85); }
.star-btn.star-disabled { color: #161616; }
.wl-clear {
    display: inline-block; margin-top: 8px;
    font-family: var(--font-mono); font-size: 9px; letter-spacing: 0.1em;
    text-transform: uppercase; color: var(--ash); text-decoration: none !important;
}
.wl-clear:hover { color: #f87171; }

/* ── Signal tables (clusters, insider scores) ── */
.signal-wrap { border: 1px solid var(--line); width: 100%; overflow-x: auto; }
.signal-table { width: 100%; border-collapse: collapse; font-size: 12.5px; }
.signal-table th {
    text-align: left; padding: 12px 16px;
    font-family: var(--font-mono); font-size: 9.5px; font-weight: 500;
    text-transform: uppercase; letter-spacing: 0.12em; color: var(--ash);
    border-bottom: 1px solid var(--line-2); white-space: nowrap;
    background: #000;
}
.signal-table td {
    padding: 13px 16px; border-bottom: 1px solid #101010;
    color: #c4c4c4; vertical-align: middle;
}
.signal-table tbody tr:last-child td { border-bottom: none; }
.signal-table tr:hover td { background: #0b0b0b; }
.signal-table .rank {
    font-family: var(--font-display); font-size: 15px; color: var(--ash);
    width: 44px; font-variant-numeric: tabular-nums;
}
.signal-table td.num { text-align: right; font-variant-numeric: tabular-nums; white-space: nowrap; }
.signal-table th.num { text-align: right; }
.signal-co   { color: #fff; font-weight: 600; }
.signal-sub  { color: var(--ash); font-family: var(--font-mono); font-size: 10px;
               letter-spacing: 0.04em; margin-top: 2px; }
.signal-dates{ font-family: var(--font-mono); font-size: 11px; color: var(--fog); white-space: nowrap; }
.ret-pos { color: #4ade80; font-weight: 600; font-variant-numeric: tabular-nums; }
.ret-neg { color: #f87171; font-weight: 600; font-variant-numeric: tabular-nums; }
.signal-empty {
    font-family: var(--font-mono); font-size: 11px; color: var(--dim);
    text-transform: uppercase; letter-spacing: 0.08em;
    padding: 24px 16px; border: 1px solid var(--line);
}

/* ── Research Findings panel ── */
.research-panel { border: 1px solid var(--line); padding: 32px; margin-bottom: 52px; }
.stat-grid {
    display: grid; grid-template-columns: repeat(5, 1fr);
    gap: 1px; background: var(--line); border: 1px solid var(--line); margin-bottom: 24px;
}
.stat-card { background: #000; padding: 22px 20px; }
.stat-label {
    font-family: var(--font-mono); color: var(--ash);
    font-size: 9.5px; font-weight: 500; letter-spacing: 0.12em;
    text-transform: uppercase; margin-bottom: 14px;
}
.stat-value {
    font-family: var(--font-display); font-size: 2rem; font-weight: 500;
    line-height: 1; letter-spacing: -0.02em; font-variant-numeric: tabular-nums;
    color: #fff;
}
.stat-value.pos { color: #4ade80; }
.stat-value.neg { color: #f87171; }
.stat-sub {
    font-family: var(--font-mono); color: var(--dim);
    font-size: 9px; margin-top: 10px; text-transform: uppercase; letter-spacing: 0.06em;
}
.research-takeaway {
    font-family: var(--font-body); font-size: 15px; line-height: 1.6;
    color: #dde6f0; border-left: 2px solid #4ade80; padding: 4px 0 4px 18px;
    margin: 4px 0 8px;
}
.research-takeaway.neg { border-left-color: #f87171; }
.research-empty {
    font-family: var(--font-mono); font-size: 11px; color: var(--dim);
    text-transform: uppercase; letter-spacing: 0.08em; padding: 8px 0;
}

/* ── Empty state ── */
.empty-state {
    display: flex; flex-direction: column; align-items: center; justify-content: center;
    text-align: center; padding: 90px 24px; border: 1px solid var(--line); margin: 24px 0;
}
.empty-icon {
    font-family: var(--font-display); font-size: 44px; color: #2c2c2c;
    line-height: 1; margin-bottom: 22px;
}
.empty-title {
    font-family: var(--font-display); font-size: 24px; font-weight: 600; color: #fff;
    letter-spacing: -0.01em; margin-bottom: 12px;
}
.empty-sub {
    font-family: var(--font-body); font-size: 14px; color: var(--fog);
    max-width: 420px; line-height: 1.6; margin-bottom: 28px;
}
.empty-btn {
    font-family: var(--font-mono); font-size: 11px; letter-spacing: 0.12em;
    text-transform: uppercase; color: #e8e8e8; text-decoration: none;
    border: 1px solid var(--line-2); padding: 12px 22px;
    transition: background 0.18s ease, color 0.18s ease, border-color 0.18s ease;
}
.empty-btn:hover { background: #fff; color: #000; border-color: #fff; }

/* ── Mobile (≤768px) ── */
@media (max-width: 768px) {
    .main .block-container { padding: 84px 16px 72px !important; }
    /* KPI + stat + research grids collapse */
    .kpi-grid  { grid-template-columns: repeat(2, 1fr); }
    .stat-grid { grid-template-columns: repeat(2, 1fr); }
    /* Streamlit column rows stack vertically */
    [data-testid="stHorizontalBlock"] { flex-direction: column !important; gap: 20px !important; }
    [data-testid="stColumn"] { width: 100% !important; flex: 1 1 100% !important; min-width: 0 !important; }
    /* hero scales down */
    .hero-section { margin-bottom: 36px; }
    .hero-foot { flex-direction: column; align-items: flex-start; gap: 16px; }
    .hero-sub { font-size: 14px; }
    .research-panel { padding: 20px 16px; }
    .about-grid { gap: 28px; }
    .empty-state { padding: 60px 16px; }
    .empty-title { font-size: 20px; }
    /* nav tightens */
    #top-navbar { padding: 0 16px; }
    #top-navbar .nav-right { gap: 14px; }
}
@media (max-width: 480px) {
    .kpi-grid  { grid-template-columns: 1fr; }
    .stat-grid { grid-template-columns: 1fr; }
    .hero-headline { line-height: 0.94; }
}
</style>
""", unsafe_allow_html=True)

# ── Constants ─────────────────────────────────────────────────────────────────
HEADERS     = {"User-Agent": "Jayal insider-monitor jayal@email.com"}
BASE_URL    = "https://efts.sec.gov/LATEST/search-index"
MAX_RESULTS = 200

TRANSACTION_LABELS = {"P": "🟢 Buy", "S": "🔴 Sell", "A": "🔵 Award"}
TRANSACTION_ORDER  = ["🟢 Buy", "🔴 Sell", "🔵 Award", "⚪ Other"]
TXN_CLEAN_LABELS   = {"🟢 Buy": "Buy", "🔴 Sell": "Sell", "🔵 Award": "Award", "⚪ Other": "Other"}
PIE_COLORS = {
    "🟢 Buy": "#22c55e", "🔴 Sell": "#ef4444",
    "🔵 Award": "#3b82f6", "⚪ Other": "#6b7280",
}
TXN_PILL_HTML = {
    "🟢 Buy":   "<span class='txn-pill txn-buy'>Buy</span>",
    "🔴 Sell":  "<span class='txn-pill txn-sell'>Sell</span>",
    "🔵 Award": "<span class='txn-pill txn-award'>Award</span>",
    "⚪ Other": "<span class='txn-pill txn-other'>Other</span>",
}
NOTABLE_RE  = _re.compile(r"\b(Chief|CEO|CFO|President)\b", _re.IGNORECASE)
SEE_RMKS_RE = _re.compile(r"see\s+remarks", _re.IGNORECASE)

# ── Persistent filing cache ────────────────────────────────────────────────────
_CACHE_FILE = pathlib.Path("filing_cache.json")
_cache_lock = threading.Lock()


def _load_filing_cache() -> dict:
    try:
        if _CACHE_FILE.exists():
            return json.loads(_CACHE_FILE.read_text(encoding="utf-8"))
    except Exception:
        pass
    return {}


def _save_filing_cache(cache: dict) -> None:
    with _cache_lock:
        try:
            _CACHE_FILE.write_text(
                json.dumps(cache, ensure_ascii=False), encoding="utf-8"
            )
        except Exception:
            pass


_filing_cache: dict = _load_filing_cache()

# ── Shared HTTP session (connection-pool reuse across 50 threads) ─────────────
_session = requests.Session()
_session.headers.update(HEADERS)
_session.mount("https://", HTTPAdapter(pool_connections=50, pool_maxsize=50))
_session.mount("http://",  HTTPAdapter(pool_connections=10, pool_maxsize=10))

# ── Regex for SEC .txt parsing ────────────────────────────────────────────────
_CIK_RE    = _re.compile(r"\s*\(CIK\s+\d+\)\s*$", _re.IGNORECASE)
_CODE_RE   = _re.compile(r"<transactionCode>([^<]+)</transactionCode>", _re.I)
_TITLE_RE  = _re.compile(r"<officerTitle>([^<]*)</officerTitle>", _re.I)
_SHARES_RE = _re.compile(r"<transactionShares>\s*<value>([^<]+)</value>", _re.I | _re.S)
_PRICE_RE  = _re.compile(r"<transactionPricePerShare>\s*<value>([^<]+)</value>", _re.I | _re.S)
_TDATE_RE  = _re.compile(r"<transactionDate>\s*<value>([^<]+)</value>", _re.I | _re.S)


# ── Formatters ────────────────────────────────────────────────────────────────
def _fmt_ret_single(r) -> str:
    if r is None:
        return "<span style='color:#4b5563'>—</span>"
    color = "#22c55e" if r >= 0 else "#ef4444"
    sign  = "+" if r >= 0 else ""
    return f"<span style='color:{color};font-weight:600'>{sign}{r:.1f}%</span>"


def _fmt_returns(r7, r30, r90) -> str:
    return " / ".join([_fmt_ret_single(r7), _fmt_ret_single(r30), _fmt_ret_single(r90)])


def _fmt_value(shares, price) -> str:
    try:
        v = float(shares) * float(price)
        return "—" if v == 0 else f"${v:,.0f}"
    except Exception:
        return "—"


def _fmt_shares(s) -> str:
    try:
        return f"{float(s):,.0f}"
    except Exception:
        return "—"


def _strip_cik(s: str) -> str:
    return _CIK_RE.sub("", s).strip()


def _build_filing_url(adsh: str, cik: str) -> str:
    clean = adsh.replace("-", "")
    return f"https://www.sec.gov/Archives/edgar/data/{cik}/{clean}/{adsh}-index.htm"


def _build_txt_url(adsh: str, cik: str) -> str:
    clean = adsh.replace("-", "")
    return f"https://www.sec.gov/Archives/edgar/data/{cik}/{clean}/{adsh}.txt"


def _resolve_title(raw: str) -> str:
    raw = raw.strip()
    if not raw or SEE_RMKS_RE.search(raw):
        return "Director"
    return raw


# ── SEC .txt fetch (TTL 10 min) ───────────────────────────────────────────────
@st.cache_data(ttl=600, show_spinner=False)
def _fetch_filing_data(adsh: str, cik: str) -> dict:
    default = {
        "transaction_type": "⚪ Other",
        "exec_title":       "Director",
        "shares":           None,
        "price_per_share":  None,
        "transaction_date": None,
    }
    try:
        resp = _session.get(_build_txt_url(adsh, cik), timeout=5)
        if resp.status_code != 200:
            return default
        text = resp.text

        raw_codes = [c.strip() for c in _CODE_RE.findall(text)]
        for priority in ("P", "S", "A"):
            if priority in raw_codes:
                default["transaction_type"] = TRANSACTION_LABELS[priority]
                break

        m = _TITLE_RE.search(text)
        default["exec_title"] = _resolve_title(m.group(1) if m else "")

        m = _SHARES_RE.search(text)
        if m:
            try:
                default["shares"] = float(m.group(1).strip())
            except ValueError:
                pass

        m = _PRICE_RE.search(text)
        if m:
            try:
                default["price_per_share"] = float(m.group(1).strip())
            except ValueError:
                pass

        m = _TDATE_RE.search(text)
        if m:
            default["transaction_date"] = m.group(1).strip()

        return default
    except Exception:
        return default


# ── Ticker + sector via Yahoo Finance (TTL 1 hr) ──────────────────────────────
@st.cache_data(ttl=3600, show_spinner=False)
def _get_yf_sector(symbol: str) -> str:
    """Get sector from yfinance .info with a hard 10-second timeout."""
    try:
        with ThreadPoolExecutor(max_workers=1) as ex:
            info = ex.submit(lambda: yf.Ticker(symbol).info).result(timeout=10)
        return info.get("sector", "") or "Unknown"
    except Exception:
        return "Unknown"


@st.cache_data(ttl=3600, show_spinner=False)
def _lookup_ticker_and_sector(company_name: str) -> tuple[str, str]:
    try:
        url = (
            "https://query2.finance.yahoo.com/v1/finance/search"
            f"?q={requests.utils.quote(company_name)}&quotesCount=1&newsCount=0"
        )
        resp   = _session.get(url, timeout=8)
        quotes = resp.json().get("quotes", [])
        if quotes and quotes[0].get("quoteType") == "EQUITY":
            q      = quotes[0]
            symbol = q.get("symbol", "")
            sector = q.get("sectorDisp", q.get("sector", "")) or ""
            if not sector and symbol:
                sector = _get_yf_sector(symbol)
            return symbol, sector or "Unknown"
    except Exception:
        pass
    return "", "Unknown"


# ── yfinance helpers ──────────────────────────────────────────────────────────
def _yahoo_chart(ticker: str, start: str, end: str) -> pd.DataFrame:
    """Daily closes from Yahoo's chart API via the shared SEC-style session.

    We deliberately do NOT use yfinance here: yfinance sends a browser-like
    User-Agent that Yahoo rate-limits to HTTP 429 (empty history -> blank
    returns), whereas the app's session UA returns HTTP 200 with full data.
    Returns a DataFrame with a tz-aware "Date" index and a "Close" column,
    matching the shape the callers expect.
    """
    try:
        p1 = int(datetime.strptime(start, "%Y-%m-%d").replace(tzinfo=timezone.utc).timestamp())
        p2 = int(datetime.strptime(end,   "%Y-%m-%d").replace(tzinfo=timezone.utc).timestamp()) + 86400
        time.sleep(random.uniform(0.03, 0.09))  # gentle pacing to avoid rate limits
        resp = _session.get(
            f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}",
            params={"period1": p1, "period2": p2, "interval": "1d"}, timeout=10,
        )
        if resp.status_code != 200:
            return pd.DataFrame()
        result = resp.json().get("chart", {}).get("result")
        if not result:
            return pd.DataFrame()
        ts     = result[0].get("timestamp") or []
        closes = (result[0].get("indicators", {}).get("quote", [{}])[0].get("close")) or []
        pairs  = [(t, c) for t, c in zip(ts, closes) if c is not None]
        if not pairs:
            return pd.DataFrame()
        out = pd.DataFrame(
            {"Close": [c for _, c in pairs]},
            index=pd.to_datetime([t for t, _ in pairs], unit="s", utc=True),
        )
        out.index.name = "Date"
        return out
    except Exception:
        return pd.DataFrame()


def _history_with_fallback(ticker: str, start: str, end: str):
    # Retry foreign/suffixed tickers (e.g. "AGN.MX", "SHOP.TO") with the base symbol.
    hist = _yahoo_chart(ticker, start, end)
    if hist.empty and "." in ticker:
        hist = _yahoo_chart(ticker.split(".")[0], start, end)
    return hist


@st.cache_data(ttl=3600, show_spinner=False)
def _get_returns(ticker: str, base_date_str: str) -> tuple:
    try:
        base = pd.to_datetime(base_date_str).date()
        end  = min(base + timedelta(days=100), date.today())
        hist = _history_with_fallback(ticker, str(base), str(end))
        if hist.empty:
            return None, None, None
        base_price = hist["Close"].iloc[0]

        def _ret(days: int):
            target = base + timedelta(days=days)
            if target >= date.today():
                return None
            future = hist[hist.index.date >= target]
            if future.empty:
                return None
            return round((future["Close"].iloc[0] / base_price - 1) * 100, 2)

        return _ret(7), _ret(30), _ret(90)
    except Exception:
        return None, None, None


@st.cache_data(ttl=21600, show_spinner=False)
def _get_spy_returns(base_date_str: str) -> tuple:
    """S&P 500 (SPY) 7/30/90-day return from a given date — the market benchmark.
    Cached 6h and keyed only on the date, so it's fetched once per distinct
    transaction date and reused across every insider buy on that day."""
    return _get_returns("SPY", base_date_str)


@st.cache_data(ttl=3600, show_spinner=False)
def _get_stock_chart_data(ticker: str, base_date_str: str) -> pd.DataFrame:
    try:
        base = pd.to_datetime(base_date_str).date()
        end  = min(base + timedelta(days=35), date.today())
        hist = _history_with_fallback(ticker, str(base), str(end))
        if hist.empty:
            return pd.DataFrame()
        hist = hist.reset_index()[["Date", "Close"]]
        hist["Date"] = pd.to_datetime(hist["Date"]).dt.tz_localize(None)
        return hist
    except Exception:
        return pd.DataFrame()


@st.cache_data(ttl=3600, show_spinner=False)
def _get_sparkline_prices(ticker: str, ref_date_str: str) -> list:
    """Last ≤30 closes ending at ref_date for the hover sparkline tooltip."""
    try:
        ref   = pd.to_datetime(ref_date_str).date()
        start = ref - timedelta(days=50)
        hist  = _history_with_fallback(ticker, str(start), str(ref + timedelta(days=1)))
        if hist.empty:
            return []
        return [round(float(c), 2) for c in hist["Close"].tail(30).tolist()]
    except Exception:
        return []


# ── EDGAR filing fetch (TTL 5 min) ────────────────────────────────────────────
# The EDGAR full-text search API returns up to 100 hits per request. A single
# page is fetched by the cached helper below (kept pure — no Streamlit calls, so
# st.cache_data can memoize/replay it safely). The uncached fetch_filings wrapper
# owns the pagination loop and the progress bar; calling a progress widget inside
# a cached function raises CacheReplayClosureError, which is why they're split.
@st.cache_data(ttl=300, show_spinner=False)
def _fetch_page(start_dt: str, end_dt: str, page: int) -> list:
    params = {
        "q": '"form 4"', "forms": "4", "dateRange": "custom",
        "startdt": start_dt, "enddt": end_dt, "from": page * 100,
    }
    try:
        resp = _session.get(BASE_URL, params=params, timeout=15)
        resp.raise_for_status()
        return resp.json().get("hits", {}).get("hits", [])
    except Exception:
        return None  # signals a fetch error to the caller


def fetch_filings(start_dt: str, end_dt: str, limit: int = MAX_RESULTS, status=None) -> pd.DataFrame:
    hits, seen, per_page = [], set(), 100
    # EDGAR caps the `from` offset at 10,000 (100 pages of 100)
    for page in range(100):
        if len(hits) >= limit:
            break
        batch = _fetch_page(start_dt, end_dt, page)
        if batch is None:
            st.error("EDGAR API error — showing whatever loaded so far.")
            break
        if not batch:
            break
        for h in batch:
            adsh = h.get("_source", {}).get("adsh", "")
            if adsh and adsh in seen:
                continue
            seen.add(adsh)
            hits.append(h)
        if status is not None:
            loaded = min(len(hits), limit)
            status.progress(min(loaded / limit, 1.0), text=f"Loading filings… {loaded}/{limit}")
        if len(batch) < per_page:
            break
    return _parse_hits(hits[:limit])


def _parse_hits(hits: list) -> pd.DataFrame:
    rows = []
    for h in hits:
        s     = h.get("_source", {})
        adsh  = s.get("adsh", "")
        names = s.get("display_names", [])

        exec_name = _strip_cik(names[0]) if len(names) > 0 else "—"
        company   = _strip_cik(names[1]) if len(names) > 1 else "—"

        locs     = [l for l in s.get("biz_locations", []) if l]
        location = locs[0] if locs else (", ".join(s.get("biz_states", [])) or "—")

        cik_list = s.get("ciks", [])
        cik = str(int(cik_list[1])) if len(cik_list) > 1 else (
              str(int(cik_list[0])) if cik_list else "")

        rows.append({
            "Filed":             s.get("file_date", ""),
            "Executive / Filer": exec_name or "—",
            "Company":           company or "—",
            "Location":          location,
            "Accession No":      adsh,
            "CIK":               cik,
            "Filing URL":        _build_filing_url(adsh, cik) if adsh and cik else "",
        })

    df = pd.DataFrame(rows)
    if df.empty:
        return df
    df["Filed"] = pd.to_datetime(df["Filed"], errors="coerce")
    df.sort_values("Filed", ascending=False, inplace=True)
    df.reset_index(drop=True, inplace=True)
    return df


# ── Phase 1: SEC .txt enrichment (parallel, file-cached) ─────────────────────
def enrich_with_filing_data(
    df: pd.DataFrame, progress_bar=None
) -> tuple[pd.DataFrame, int]:
    """Enrich df with SEC .txt data. Returns (enriched_df, cache_hits)."""
    results: dict[str, dict] = {}
    pairs = [(r["Accession No"], r["CIK"]) for _, r in df.iterrows()
             if r["Accession No"] and r["CIK"]]

    # Serve hits from persistent file cache without any HTTP requests
    need_fetch = []
    for adsh, cik in pairs:
        if adsh in _filing_cache:
            results[adsh] = _filing_cache[adsh]
        else:
            need_fetch.append((adsh, cik))

    cache_hits = len(pairs) - len(need_fetch)
    total      = len(pairs)

    if need_fetch:
        new_data: dict[str, dict] = {}
        done = cache_hits

        if progress_bar:
            progress_bar.progress(
                done / total if total else 1.0,
                text=f"⚡ {cache_hits} cached · Fetching {len(need_fetch)} from SEC…",
            )

        with ThreadPoolExecutor(max_workers=50) as ex:
            fmap = {ex.submit(_fetch_filing_data, adsh, cik): adsh
                    for adsh, cik in need_fetch}
            for fut in as_completed(fmap):
                adsh   = fmap[fut]
                result = fut.result()
                results[adsh]  = result
                new_data[adsh] = result
                done += 1
                if progress_bar:
                    pct  = done / total if total else 1.0
                    fetched = done - cache_hits
                    progress_bar.progress(
                        pct,
                        text=f"Fetching from SEC… {fetched}/{len(need_fetch)}",
                    )

        # Persist new entries to the JSON file cache
        _filing_cache.update(new_data)
        _save_filing_cache(_filing_cache)

    elif progress_bar:
        progress_bar.progress(1.0, text=f"⚡ All {cache_hits} filings loaded from cache")

    df = df.copy()
    get = lambda a, k, d: results.get(a, {}).get(k, d)
    df["Transaction Type"] = df["Accession No"].map(
        lambda a: get(a, "transaction_type", "⚪ Other"))
    df["Exec Title"]       = df["Accession No"].map(
        lambda a: get(a, "exec_title",       "Director"))
    df["Shares"]           = df["Accession No"].map(
        lambda a: get(a, "shares",           None))
    df["Price Per Share"]  = df["Accession No"].map(
        lambda a: get(a, "price_per_share",  None))
    df["Transaction Date"] = df["Accession No"].map(
        lambda a: get(a, "transaction_date", None))
    return df, cache_hits


# ── Phase 2: Market data enrichment (parallel) ────────────────────────────────
def enrich_with_market_data(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    unique_cos  = df["Company"].dropna().unique().tolist()
    ticker_map: dict[str, str] = {}
    sector_map: dict[str, str] = {}

    with ThreadPoolExecutor(max_workers=10) as ex:
        fmap = {ex.submit(_lookup_ticker_and_sector, co): co for co in unique_cos}
        for fut in as_completed(fmap):
            co = fmap[fut]
            t, s = fut.result()
            ticker_map[co] = t
            sector_map[co] = s

    df["Ticker"] = df["Company"].map(ticker_map).fillna("")
    df["Sector"] = df["Company"].map(sector_map).fillna("Unknown")

    df["7d Return"] = df["30d Return"] = df["90d Return"] = None

    # Compute post-transaction returns for EVERY ticker'd filing (not just buys):
    # ~90% of Form 4s are sells/awards, and their price data is just as available,
    # so restricting to buys is why most rows showed "—". Returns are only left
    # blank when the window hasn't elapsed yet or the ticker has no price data.
    ret_rows = df[df["Ticker"].astype(bool)]

    if not ret_rows.empty:
        pairs = list(dict.fromkeys(
            (row["Ticker"], row["Transaction Date"] or str(row["Filed"].date()))
            for _, row in ret_rows.iterrows() if row["Ticker"]
        ))
        ret_results: dict[tuple, tuple] = {}
        with ThreadPoolExecutor(max_workers=6) as ex:  # modest concurrency = fewer 429s
            fmap2 = {ex.submit(_get_returns, t, d): (t, d) for t, d in pairs}
            for fut in as_completed(fmap2):
                ret_results[fmap2[fut]] = fut.result()

        for idx, row in ret_rows.iterrows():
            key = (row["Ticker"], row["Transaction Date"] or str(row["Filed"].date()))
            r7, r30, r90 = ret_results.get(key, (None, None, None))
            df.at[idx, "7d Return"]  = r7
            df.at[idx, "30d Return"] = r30
            df.at[idx, "90d Return"] = r90

    return df


# ── Navbar + cursor glow (injected once per page session) ─────────────────────
components.html("""
<script>
(function() {
  var p = window.parent;
  if (!p || p === window) return;
  var pd = p.document;

  // ── Navbar ──
  if (!pd.getElementById('top-navbar')) {
    var nav = pd.createElement('div');
    nav.id = 'top-navbar';
    nav.innerHTML =
      '<div class="nav-brand">'
      + '<span class="nav-wordmark">INSIDER</span>'
      + '<span class="nav-mark">&#10022;</span>'
      + '</div>'
      + '<div class="nav-tag">SEC EDGAR / Form 4</div>'
      + '<div class="nav-right">'
      + '<div class="nav-pill-live"><span class="live-dot"></span>Live</div>'
      + '<a href="https://github.com/jayalqqq/insider-moniter" target="_blank" rel="noopener">GitHub</a>'
      + '<a href="https://www.sec.gov/about/forms/form4data.pdf" target="_blank" rel="noopener">About</a>'
      + '</div>';
    pd.body.prepend(nav);
  }

  // ── Cursor glow ──
  if (!pd.getElementById('cursor-glow')) {
    var g = pd.createElement('div');
    g.id = 'cursor-glow';
    pd.body.appendChild(g);
    if (!(p.matchMedia && p.matchMedia('(prefers-reduced-motion: reduce)').matches)) {
      pd.addEventListener('mousemove', function(e) {
        g.style.left = e.clientX + 'px';
        g.style.top  = e.clientY + 'px';
      });
    }
  }
})();
</script>
""", height=0)

# ── Sidebar divider helper ─────────────────────────────────────────────────────
_GRAD_DIV = '<div class="sidebar-div"></div>'

# ── Date range presets ─────────────────────────────────────────────────────────
DATE_PRESETS = ["7D", "30D", "90D", "YTD", "1Y"]


def _preset_range(preset: str):
    """Return (start, end) dates for a named preset."""
    today = date.today()
    if preset == "7D":
        return today - timedelta(days=7), today
    if preset == "30D":
        return today - timedelta(days=30), today
    if preset == "90D":
        return today - timedelta(days=90), today
    if preset == "YTD":
        return date(today.year, 1, 1), today
    if preset == "1Y":
        return today - timedelta(days=365), today
    return None, None


def _apply_preset(preset: str):
    """on_click callback: set the date pickers to the preset and refresh."""
    s, e = _preset_range(preset)
    if s is not None:
        st.session_state["start_date"] = s
        st.session_state["end_date"] = e
        _fetch_page.clear()


def _active_preset(start, end):
    """Which preset (if any) exactly matches the current start/end dates."""
    for p in DATE_PRESETS:
        if (start, end) == _preset_range(p):
            return p
    return None


# ── Cluster-buy detection ──────────────────────────────────────────────────────
def detect_cluster_buys(fdf: pd.DataFrame, window_days: int = 7):
    """Find same-company Buy clusters: 2+ distinct insiders buying within a
    rolling `window_days` window. Returns (clusters, accession-number set)."""
    clusters: list = []
    cluster_adsh: set = set()
    buys = fdf[fdf["Transaction Type"] == "🟢 Buy"].copy()
    if buys.empty:
        return clusters, cluster_adsh

    def _cluster_date(r):
        td = r.get("Transaction Date")
        if td:
            try:
                return pd.to_datetime(td).date()
            except Exception:
                pass
        f = r.get("Filed")
        return f.date() if pd.notna(f) else None

    buys["_cd"] = buys.apply(_cluster_date, axis=1)
    buys = buys[buys["_cd"].notna()]

    def _flush(company, window):
        insiders = {r["Executive / Filer"] for r in window}
        if len(insiders) >= 2:
            clusters.append({
                "company":  company,
                "insiders": len(insiders),
                "shares":   sum(float(r["Shares"]) for r in window if pd.notna(r.get("Shares"))),
                "start":    min(r["_cd"] for r in window),
                "end":      max(r["_cd"] for r in window),
                "buys":     len(window),
            })
            for r in window:
                if r.get("Accession No"):
                    cluster_adsh.add(r["Accession No"])

    for company, grp in buys.groupby("Company"):
        grp = grp.sort_values("_cd")
        window, start_d = [], None
        for _, row in grp.iterrows():
            d = row["_cd"]
            if start_d is None or (d - start_d).days > window_days:
                _flush(company, window)
                window, start_d = [row], d
            else:
                window.append(row)
        _flush(company, window)

    clusters.sort(key=lambda c: (c["insiders"], c["shares"]), reverse=True)
    return clusters, cluster_adsh


# ── Watchlist + URL-backed view state ─────────────────────────────────────────
# The filings table is custom HTML, so the star toggle is a query-param link.
# A link click reloads the app (new session), so the essential view state lives
# in the URL and is re-seeded into session_state on load — this keeps the
# starred set, dates, limit and search intact across star clicks. session_state
# remains the store the rest of the app reads from.
_qp = st.query_params


def _seed_state(key, value):
    if key not in st.session_state:
        st.session_state[key] = value


def _qp_date(name, default):
    v = _qp.get(name)
    if v:
        try:
            return date.fromisoformat(v)
        except Exception:
            pass
    return default


_seed_state("start_date", _qp_date("sd", date(2025, 1, 1)))
_seed_state("end_date",   _qp_date("ed", date.today()))
try:
    _lim = int(_qp.get("lim", 200))
except Exception:
    _lim = 200
_seed_state("filing_limit", _lim if _lim in (200, 500, 1000) else 200)
_seed_state("search_query", _qp.get("q", ""))
_seed_state("watchlist_only", _qp.get("wlo", "") == "1")

# Watchlist (set of tickers): the URL is the durable source of truth.
watchlist = {t for t in _qp.get("wl", "").split(",") if t}
st.session_state["watchlist"] = watchlist


def _star_href(new_wl):
    """Build a query string that preserves the current view + a new watchlist."""
    params = {
        "sd":  str(st.session_state["start_date"]),
        "ed":  str(st.session_state["end_date"]),
        "lim": str(st.session_state.get("filing_limit", 200)),
    }
    if st.session_state.get("search_query"):
        params["q"] = st.session_state["search_query"]
    if st.session_state.get("watchlist_only"):
        params["wlo"] = "1"
    if new_wl:
        params["wl"] = ",".join(sorted(new_wl))
    return "?" + urlencode(params)


def _clear_filters_href():
    """Reset every narrowing filter (type/ticker/company/location/search/watchlist)
    while keeping the data window (dates + limit). Reloading with only sd/ed/lim
    drops the URL-backed filters and resets the keyless sidebar widgets."""
    return "?" + urlencode({
        "sd":  str(st.session_state["start_date"]),
        "ed":  str(st.session_state["end_date"]),
        "lim": str(st.session_state.get("filing_limit", 200)),
    })


# ══════════════════════════════════════════════════════════════════════════════
# ── Sidebar part 1 ────────────────────────────────────────────────────────────
# ══════════════════════════════════════════════════════════════════════════════
with st.sidebar:
    st.markdown(
        "<div class='sidebar-brand'>"
        "<div class='sidebar-brand-label'>Control Panel</div>"
        "<div class='sidebar-brand-title'>Filters</div>"
        "</div>",
        unsafe_allow_html=True,
    )
    st.markdown(_GRAD_DIV, unsafe_allow_html=True)

    # seed date state once, so preset buttons and pickers share it
    st.session_state.setdefault("start_date", date(2025, 1, 1))
    st.session_state.setdefault("end_date", date.today())

    st.markdown("<div class='preset-label'>Quick Range</div>", unsafe_allow_html=True)
    _active = _active_preset(st.session_state["start_date"], st.session_state["end_date"])
    _pcols = st.columns(len(DATE_PRESETS))
    for _i, _p in enumerate(DATE_PRESETS):
        with _pcols[_i]:
            st.button(
                _p, key=f"preset_{_p}",
                type="primary" if _active == _p else "secondary",
                on_click=_apply_preset, args=(_p,),
                use_container_width=True,
            )

    col_s, col_e = st.columns(2)
    with col_s:
        start_date = st.date_input(
            "Start",
            max_value=date.today(),
            key="start_date",
            on_change=_fetch_page.clear,
        )
    with col_e:
        end_date = st.date_input(
            "End",
            max_value=date.today(),
            key="end_date",
            on_change=_fetch_page.clear,
        )
    st.markdown(_GRAD_DIV, unsafe_allow_html=True)
    filing_limit = st.radio(
        "Filing Limit",
        options=[200, 500, 1000],
        horizontal=True,
        key="filing_limit",
        on_change=_fetch_page.clear,
    )
    st.markdown(_GRAD_DIV, unsafe_allow_html=True)
    refresh = st.button("Refresh Data", use_container_width=True)
    if refresh:
        st.cache_data.clear()
        st.session_state["_refreshed"] = True

# ── Hero ──────────────────────────────────────────────────────────────────────
st.markdown(
    f"""
<div class="hero-section">
  <div class="hero-topline">
    <div class="left">SEC EDGAR<br>Form 4 Filings</div>
    <div class="right">Insider<br>Intelligence</div>
  </div>
  <h1 class="hero-headline">Track What<br>Insiders Know</h1>
  <div class="hero-foot">
    <p class="hero-sub">Real-time SEC Form 4 filings — see exactly when executives buy and sell shares in their own companies, and what the stock did next.</p>
    <div class="hero-meta">
      <span class="hero-live"><span class="live-dot"></span>Live</span>
      <span class="hero-meta-sep">/</span>
      <span>{start_date.strftime('%b %d, %Y')} — {end_date.strftime('%b %d, %Y')}</span>
    </div>
  </div>
</div>
""",
    unsafe_allow_html=True,
)

# ── Search bar ────────────────────────────────────────────────────────────────
def _clear_search():
    st.session_state["search_query"] = ""

_sc_input, _sc_clear = st.columns([13, 1], gap="small")
with _sc_input:
    search_query = st.text_input(
        "Search filings",
        key="search_query",
        placeholder="Search by company, ticker, or executive...",
        label_visibility="collapsed",
    )
with _sc_clear:
    st.button("✕", key="clear_search", on_click=_clear_search,
              help="Clear search", use_container_width=True)
search_meta_ph = st.empty()

# ── Skeleton placeholders ─────────────────────────────────────────────────────
_SKEL_KPI = """
<div class="skel-kpi-grid">
  <div class="skel-kpi shimmer"></div><div class="skel-kpi shimmer"></div>
  <div class="skel-kpi shimmer"></div><div class="skel-kpi shimmer"></div>
  <div class="skel-kpi shimmer"></div><div class="skel-kpi shimmer"></div>
  <div class="skel-kpi shimmer"></div>
</div>"""

_SKEL_CHARTS = """
<div class="skel-charts">
  <div class="skel-chart shimmer"></div>
  <div class="skel-chart shimmer"></div>
  <div class="skel-chart shimmer"></div>
</div>"""

_SKEL_TABLE = '<div style="margin-top:16px;"><div class="skel-table shimmer"></div></div>'

kpi_placeholder    = st.empty()
charts_placeholder = st.empty()
table_placeholder  = st.empty()

kpi_placeholder.markdown(_SKEL_KPI,      unsafe_allow_html=True)
charts_placeholder.markdown(_SKEL_CHARTS, unsafe_allow_html=True)
table_placeholder.markdown(_SKEL_TABLE,   unsafe_allow_html=True)

# ── Fetch & enrich ────────────────────────────────────────────────────────────
_fetch_prog = st.progress(0.0, text=f"Loading filings… 0/{filing_limit}")
df = fetch_filings(str(start_date), str(end_date), filing_limit, status=_fetch_prog)
_fetch_prog.empty()

if df.empty:
    kpi_placeholder.empty()
    charts_placeholder.empty()
    table_placeholder.empty()
    st.markdown(
        "<div class='empty-state'>"
        "<div class='empty-icon'>&#10022;</div>"
        "<div class='empty-title'>No filings found</div>"
        "<div class='empty-sub'>No SEC Form 4 filings were found for this date range. "
        "Try widening the dates in the sidebar.</div>"
        "</div>",
        unsafe_allow_html=True,
    )
    st.stop()

_enrich_prog = st.progress(0, text="Checking filing cache…")
df, _cache_hits = enrich_with_filing_data(df, progress_bar=_enrich_prog)
_enrich_prog.empty()

with st.spinner("Fetching market data (tickers, sectors, returns)…"):
    df = enrich_with_market_data(df)

# ── Sidebar part 2 ────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown(_GRAD_DIV, unsafe_allow_html=True)
    txn_filter = st.multiselect(
        "Transaction Type", options=TRANSACTION_ORDER,
        default=[], placeholder="All types",
        format_func=lambda x: TXN_CLEAN_LABELS.get(x, x),
    )

    all_tickers = sorted(t for t in df["Ticker"].dropna().unique() if t)
    ticker_label_map = {
        t: f"{t} — {df[df['Ticker'] == t]['Company'].iloc[0][:28]}"
        for t in all_tickers
    }
    ticker_sel = st.selectbox(
        "Ticker",
        options=[""] + all_tickers,
        format_func=lambda x: "All tickers" if x == "" else ticker_label_map.get(x, x),
    )
    ticker_filter = ticker_sel or ""

    all_companies = sorted(df["Company"].dropna().unique().tolist())
    company_sel = st.selectbox(
        "Company",
        options=[""] + all_companies,
        format_func=lambda x: "All companies" if x == "" else x,
    )
    company_filter = company_sel or ""

    location_filter = st.text_input("Location", placeholder="e.g. CA, NY, TX")

    st.markdown(_GRAD_DIV, unsafe_allow_html=True)
    _wl_n = len(watchlist)
    st.toggle(
        f"Watchlist Only ({_wl_n})",
        key="watchlist_only",
        disabled=(_wl_n == 0),
        help="Show only filings from your starred companies",
    )
    if _wl_n:
        st.markdown(
            f"<a class='wl-clear' href='{_star_href(set())}' target='_self'>Clear watchlist</a>",
            unsafe_allow_html=True,
        )

    st.markdown(_GRAD_DIV, unsafe_allow_html=True)
    st.markdown(
        "<div class='sidebar-footer'>"
        "Data: SEC EDGAR &amp; Yahoo Finance<br>"
        "Filings · 5 min cache<br>"
        "Filing detail · 10 min cache<br>"
        "Market data · 1 hr cache"
        "</div>",
        unsafe_allow_html=True,
    )

# ── Apply filters ─────────────────────────────────────────────────────────────
filtered = df.copy()
if txn_filter:
    filtered = filtered[filtered["Transaction Type"].isin(txn_filter)]
if ticker_filter:
    filtered = filtered[filtered["Ticker"] == ticker_filter]
if company_filter:
    filtered = filtered[filtered["Company"] == company_filter]
if location_filter.strip():
    filtered = filtered[
        filtered["Location"].str.contains(location_filter.strip(), case=False, na=False)
    ]
# Search filter: an empty/blank query is a no-op (keeps ALL rows). Only when the
# user has actually typed something do we narrow to matching company / ticker /
# executive. This must never filter to zero rows when the box is empty.
_q = (search_query or "").strip().lower()
if _q:
    _co = filtered["Company"].fillna("").str.lower()
    _tk = filtered["Ticker"].fillna("").str.lower()
    _ex = filtered["Executive / Filer"].fillna("").str.lower()
    filtered = filtered[
        _co.str.contains(_q, na=False, regex=False)
        | _tk.str.contains(_q, na=False, regex=False)
        | _ex.str.contains(_q, na=False, regex=False)
    ]
if st.session_state.get("watchlist_only") and watchlist:
    filtered = filtered[filtered["Ticker"].isin(watchlist)]

filtered = filtered.copy()

# ── Empty state: filters matched nothing (df has data, but this view is empty) ─
if filtered.empty:
    kpi_placeholder.empty()
    charts_placeholder.empty()
    table_placeholder.empty()
    st.markdown(
        "<div class='empty-state'>"
        "<div class='empty-icon'>&#10022;</div>"
        "<div class='empty-title'>No filings match your filters</div>"
        "<div class='empty-sub'>Nothing matched your current search, transaction type, ticker, "
        "company, location, or watchlist. Try loosening one of them.</div>"
        f"<a class='empty-btn' href='{_clear_filters_href()}' target='_self'>Clear all filters</a>"
        "</div>",
        unsafe_allow_html=True,
    )
    st.stop()

filtered["Notable"] = (
    (filtered["Transaction Type"] == "🟢 Buy") &
    filtered["Exec Title"].apply(lambda t: bool(NOTABLE_RE.search(str(t))))
)

# ── Cluster-buy detection (respects all active filters) ───────────────────────
cluster_list, cluster_adsh = detect_cluster_buys(filtered)
cluster_count = len(cluster_list)

# ── KPI values ────────────────────────────────────────────────────────────────
total        = len(filtered)
companies    = filtered["Company"].nunique()
latest       = filtered["Filed"].max()
latest_str   = latest.strftime("%b %d, %Y") if pd.notna(latest) else "—"
buys         = (filtered["Transaction Type"] == "🟢 Buy").sum()
sells        = (filtered["Transaction Type"] == "🔴 Sell").sum()
notable_buys = filtered["Notable"].sum()
sectors_n    = filtered[
    filtered["Sector"].notna() &
    (filtered["Sector"] != "") &
    (filtered["Sector"] != "Unknown")
]["Sector"].nunique()

_ratio_num     = round(buys / sells, 1) if sells > 0 else None
_ratio_display = (
    f"{_ratio_num}:1" if _ratio_num is not None else ("∞" if buys > 0 else "—")
)

# ── Search result count ───────────────────────────────────────────────────────
_noun = "matching filing" if _q else "filing"
_meta = f"{total:,} {_noun}{'' if total == 1 else 's'}"
if _q:
    _meta += f" &nbsp;·&nbsp; <span class='q'>“{_html.escape((search_query or '').strip())}”</span>"
search_meta_ph.markdown(f"<div class='search-meta'>{_meta}</div>", unsafe_allow_html=True)

# ── Sparkline pre-fetch for hover tooltips ────────────────────────────────────
# Cap the rendered table at 500 rows for DOM performance; KPIs, charts and the
# CSV export still use the full fetched set.
display = filtered.head(min(filing_limit, 500)).copy()
display["Filed_str"] = display["Filed"].dt.strftime("%Y-%m-%d").fillna("—")

_spark_pairs = list(dict.fromkeys(
    (r["Ticker"], r["Transaction Date"] or str(r["Filed"].date()))
    for _, r in display.iterrows()
    if r.get("Ticker")
))[:60]

spark_map: dict = {}
if _spark_pairs:
    with ThreadPoolExecutor(max_workers=8) as _sex:
        _sfmap = {_sex.submit(_get_sparkline_prices, t, d): (t, d) for t, d in _spark_pairs}
        for _sfut in as_completed(_sfmap):
            spark_map[_sfmap[_sfut]] = _sfut.result()

# ── Replace KPI skeleton ──────────────────────────────────────────────────────
# KPI values are rendered directly into the HTML (server-side) so they are
# always correct and never depend on client-side JS. A one-time count-up
# animation enhances the first page load; it re-uses the data-target attrs but
# never resets the displayed number to 0 on Streamlit reruns (e.g. while typing
# in the search box), which previously left the cards stuck at 0.
_kpi_html = f"""
<div class="kpi-grid">
  <div class="kpi-card">
    <div class="kpi-label">Total Filings</div>
    <div class="kpi-value" data-target="{total}" data-type="int">{total:,}</div>
    <div class="kpi-desc">Form 4 filings tracked</div>
  </div>
  <div class="kpi-card">
    <div class="kpi-label">Unique Companies</div>
    <div class="kpi-value" data-target="{companies}" data-type="int">{companies:,}</div>
    <div class="kpi-desc">Distinct issuers</div>
  </div>
  <div class="kpi-card">
    <div class="kpi-label">Buy / Sell Ratio</div>
    <div class="kpi-value" data-target="{_ratio_num or 0}" data-final="{_html.escape(_ratio_display)}" data-type="ratio">{_ratio_display}</div>
    <div class="kpi-desc">{buys} buys / {sells} sells</div>
  </div>
  <div class="kpi-card">
    <div class="kpi-label">Notable Buys</div>
    <div class="kpi-value" data-target="{notable_buys}" data-type="int">{notable_buys:,}</div>
    <div class="kpi-desc">CEO / CFO / President buying</div>
  </div>
  <div class="kpi-card">
    <div class="kpi-label">Cluster Buys</div>
    <div class="kpi-value" data-target="{cluster_count}" data-type="int">{cluster_count:,}</div>
    <div class="kpi-desc">Coordinated insider buying</div>
  </div>
  <div class="kpi-card">
    <div class="kpi-label">Latest Filing</div>
    <div class="kpi-value" data-type="date" style="font-size:1.5rem;">{latest_str}</div>
    <div class="kpi-desc">Most recent submission</div>
  </div>
  <div class="kpi-card">
    <div class="kpi-label">Sectors Covered</div>
    <div class="kpi-value" data-target="{sectors_n}" data-type="int">{sectors_n:,}</div>
    <div class="kpi-desc">Industries represented</div>
  </div>
</div>
"""
kpi_placeholder.markdown(_kpi_html, unsafe_allow_html=True)

# ── Counter animation (first load only; values already correct in HTML) ───────
components.html("""
<script>
(function() {
  var p  = window.parent ? window.parent : window;
  var pd = p.document;
  // Numbers are already server-rendered. Animate a count-up once per page load;
  // on later reruns leave the real values untouched (no reset to 0).
  if (p.__kpiAnimated) return;
  if (p.matchMedia && p.matchMedia('(prefers-reduced-motion: reduce)').matches) return;
  p.__kpiAnimated = true;
  var DUR = 1400;
  function easeOut(t) { return 1 - Math.pow(1 - t, 3); }
  setTimeout(function() {
    pd.querySelectorAll('.kpi-value[data-type="int"]').forEach(function(el) {
      var target = parseInt(el.dataset.target, 10);
      if (isNaN(target) || target <= 0) return;
      var t0 = p.performance.now();
      (function tick(now) {
        var prog = Math.min((now - t0) / DUR, 1);
        el.textContent = Math.round(easeOut(prog) * target).toLocaleString();
        if (prog < 1) p.requestAnimationFrame(tick);
      })(p.performance.now());
    });
    pd.querySelectorAll('.kpi-value[data-type="ratio"]').forEach(function(el) {
      var target = parseFloat(el.dataset.target);
      var final  = el.dataset.final;
      if (!target || isNaN(target)) return;
      var t0 = p.performance.now();
      (function tick(now) {
        var prog = Math.min((now - t0) / DUR, 1);
        el.textContent = prog < 1 ? (easeOut(prog) * target).toFixed(1) + ':1' : final;
        if (prog < 1) p.requestAnimationFrame(tick);
      })(p.performance.now());
    });
  }, 120);
})();
</script>
""", height=0)

# ── Replace charts skeleton ───────────────────────────────────────────────────
_CHART_FONT   = dict(family="IBM Plex Mono, monospace", color="#8a8a8a", size=11)
_GRID_COLOR   = "#1a1a1a"
_TICK_COLOR   = "#8a8a8a"
_TRANSPARENT  = "rgba(0,0,0,0)"
_AXIS_BASE    = dict(
    color=_TICK_COLOR, tickfont=dict(color=_TICK_COLOR, size=10, family="IBM Plex Mono, monospace"),
    linecolor=_GRID_COLOR, showline=False, zeroline=False,
    gridcolor=_GRID_COLOR, gridwidth=1,
)
_BASE_LAYOUT  = dict(
    margin=dict(l=0, r=0, t=14, b=0),
    plot_bgcolor=_TRANSPARENT, paper_bgcolor=_TRANSPARENT,
    height=268,
    font=_CHART_FONT,
    hoverlabel=dict(bgcolor="#000", bordercolor="#2c2c2c",
                    font=dict(color="#e8e8e8", size=11, family="IBM Plex Mono, monospace")),
)

_CHART_CONFIG = dict(displayModeBar=False, responsive=True)

# label mapping without emoji for chart legends
_TXN_LABEL_CLEAN = {
    "🟢 Buy":   "Buy",
    "🔴 Sell":  "Sell",
    "🔵 Award": "Award",
    "⚪ Other": "Other",
}
_SECTOR_COLORS = {
    "Buy":  "#22c55e",
    "Sell": "#ef4444",
}

with charts_placeholder.container():
    col_area, col_pie, col_bar = st.columns(3)

    # ── Filings Over Time — filled area chart ─────────────────────────────────
    with col_area:
        st.markdown("<div class='section-label'>Filings Over Time</div>", unsafe_allow_html=True)
        daily = (
            filtered.set_index("Filed").resample("D")["Accession No"]
            .count().reset_index()
            .rename(columns={"Filed": "Date", "Accession No": "Filings"})
        )
        avg_filings = daily["Filings"].mean()
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=daily["Date"], y=daily["Filings"],
            mode="lines",
            line=dict(color="#ffffff", width=1.5),
            fill="tozeroy",
            fillcolor="rgba(255,255,255,0.05)",
            hovertemplate="%{x|%b %d}<br><b>%{y} filings</b><extra></extra>",
            name="Filings",
        ))
        fig.add_hline(
            y=avg_filings, line_dash="dot", line_color="#333333", line_width=1,
            annotation_text=f"AVG {avg_filings:.0f}",
            annotation_font=dict(color="#5f5f5f", size=9, family="IBM Plex Mono, monospace"),
            annotation_position="bottom right",
        )
        fig.update_layout(
            **_BASE_LAYOUT,
            xaxis=dict(**_AXIS_BASE, showgrid=False,
                       tickformat="%b %d", nticks=6, tickangle=0),
            yaxis=dict(**_AXIS_BASE, showgrid=True),
            showlegend=False,
        )
        st.plotly_chart(fig, use_container_width=True, config=_CHART_CONFIG)

    # ── Transaction Breakdown — donut chart ───────────────────────────────────
    with col_pie:
        st.markdown("<div class='section-label'>Transaction Breakdown</div>", unsafe_allow_html=True)
        txn_counts = (
            filtered["Transaction Type"].value_counts()
            .reindex(TRANSACTION_ORDER, fill_value=0).reset_index()
        )
        txn_counts.columns = ["Type", "Count"]
        txn_counts = txn_counts[txn_counts["Count"] > 0]
        txn_counts["Label"] = txn_counts["Type"].map(_TXN_LABEL_CLEAN).fillna(txn_counts["Type"])
        _donut_colors = {
            "🟢 Buy":   "#22c55e",
            "🔴 Sell":  "#ef4444",
            "🔵 Award": "#e8e8e8",
            "⚪ Other": "#3f3f3f",
        }
        _total_txn = int(txn_counts["Count"].sum())
        fig = go.Figure(go.Pie(
            labels=txn_counts["Label"],
            values=txn_counts["Count"],
            marker=dict(colors=[_donut_colors.get(t, "#3f3f3f") for t in txn_counts["Type"]],
                        line=dict(color="#000", width=2)),
            hole=0.68,
            textinfo="none",
            hovertemplate="<b>%{label}</b><br>%{value} transactions<br>%{percent}<extra></extra>",
        ))
        fig.add_annotation(
            text=f"<b>{_total_txn:,}</b><br><span style='font-size:9px;letter-spacing:2px'>TOTAL</span>",
            x=0.5, y=0.5, showarrow=False,
            font=dict(color="#ffffff", size=22, family="Space Grotesk"),
            align="center",
        )
        fig.update_layout(
            **_BASE_LAYOUT,
            showlegend=True,
            legend=dict(
                orientation="v", x=1.02, y=0.5,
                xanchor="left", yanchor="middle",
                bgcolor=_TRANSPARENT,
                font=dict(color="#e8e8e8", size=11, family="IBM Plex Mono, monospace"),
                itemsizing="constant",
                traceorder="normal",
            ),
        )
        fig.update_layout(margin_r=80)
        st.plotly_chart(fig, use_container_width=True, config=_CHART_CONFIG)

    # ── Top 10 Locations — horizontal bar chart ───────────────────────────────
    with col_bar:
        st.markdown("<div class='section-label'>Top 10 Locations</div>", unsafe_allow_html=True)
        top_locs = filtered["Location"].value_counts().head(10).reset_index()
        top_locs.columns = ["Location", "Filings"]
        top_locs = top_locs.sort_values("Filings", ascending=True)
        _n = len(top_locs)
        # blue -> cyan gradient (#2563eb -> #06b6d4); largest bar (top) = cyan
        def _lerp(a, b, t):
            return int(round(a + (b - a) * t))
        _bar_colors = [
            f"rgb({_lerp(37, 6, t)},{_lerp(99, 182, t)},{_lerp(235, 212, t)})"
            for t in (i / max(_n - 1, 1) for i in range(_n))
        ]
        fig = go.Figure(go.Bar(
            x=top_locs["Filings"],
            y=top_locs["Location"],
            orientation="h",
            marker=dict(color=_bar_colors, line=dict(width=0)),
            text=top_locs["Filings"],
            textposition="outside",
            textfont=dict(color="#cbd5e1", size=11, family="IBM Plex Mono, monospace"),
            hovertemplate="<b>%{y}</b><br>%{x} filings<extra></extra>",
            cliponaxis=False,
        ))
        fig.update_layout(
            **_BASE_LAYOUT,
            yaxis=dict(**_AXIS_BASE, showgrid=False),
            xaxis=dict(**_AXIS_BASE, showgrid=True, showticklabels=False),
            bargap=0.35,
        )
        st.plotly_chart(fig, use_container_width=True, config=_CHART_CONFIG)

    # ── Insider Activity by Sector — grouped bar chart ────────────────────────
    sector_df = filtered[
        filtered["Sector"].notna() &
        (filtered["Sector"] != "Unknown") &
        filtered["Transaction Type"].isin(["🟢 Buy", "🔴 Sell"])
    ]
    if not sector_df.empty:
        st.markdown("<div class='section-label'>Insider Activity by Sector</div>", unsafe_allow_html=True)
        sc = sector_df.copy()
        sc["TxnLabel"] = sc["Transaction Type"].map(_TXN_LABEL_CLEAN)
        sc = sc.groupby(["Sector", "TxnLabel"]).size().reset_index(name="Count")
        fig = go.Figure()
        for txn_label, color in [("Buy", "#22c55e"), ("Sell", "#ef4444")]:
            sub = sc[sc["TxnLabel"] == txn_label]
            if sub.empty:
                continue
            fig.add_trace(go.Bar(
                x=sub["Sector"], y=sub["Count"],
                name=txn_label,
                marker=dict(color=color, opacity=0.85, line=dict(width=0)),
                hovertemplate="<b>%{x}</b><br>" + txn_label + ": %{y}<extra></extra>",
            ))
        fig.update_layout(
            **_BASE_LAYOUT,
            barmode="group",
            bargap=0.28,
            bargroupgap=0.08,
            xaxis=dict(**_AXIS_BASE, showgrid=False, tickangle=-30),
            yaxis=dict(**_AXIS_BASE, showgrid=True),
            legend=dict(
                orientation="h", x=1, y=1,
                xanchor="right", yanchor="bottom",
                bgcolor=_TRANSPARENT,
                font=dict(color="#8a8a8a", size=10, family="IBM Plex Mono, monospace"),
                itemsizing="constant",
            ),
        )
        fig.update_layout(height=280)
        st.plotly_chart(fig, use_container_width=True, config=_CHART_CONFIG)

    st.markdown("---")

# ══════════════════════════════════════════════════════════════════════════════
# ── Research Findings — do insider buys beat the market? ──────────────────────
# ══════════════════════════════════════════════════════════════════════════════
st.markdown(
    "<div class='section-label'>Research Findings — Do Insider Buys Beat the Market?</div>",
    unsafe_allow_html=True,
)

_rf_buys = filtered[filtered["Transaction Type"] == "🟢 Buy"].copy()
for _c in ("7d Return", "30d Return", "90d Return"):
    _rf_buys[_c] = pd.to_numeric(_rf_buys[_c], errors="coerce")

# S&P 500 benchmark over the same transaction dates (cached per date)
_rf_dates = sorted({(r["Transaction Date"] or str(r["Filed"].date())) for _, r in _rf_buys.iterrows()})
_spy_map: dict = {}
if _rf_dates:
    with st.spinner("Benchmarking insider buys against the S&P 500…"):
        with ThreadPoolExecutor(max_workers=6) as _sx:
            _sfm = {_sx.submit(_get_spy_returns, d): d for d in _rf_dates}
            for _sf in as_completed(_sfm):
                _spy_map[_sfm[_sf]] = _sf.result()

# Paired averages over the SAME buys (insider vs S&P 500) for each horizon
_HZ = [("7d", "7d Return", 0), ("30d", "30d Return", 1), ("90d", "90d Return", 2)]
avg_ins: dict = {}
avg_spy: dict = {}
n_hz: dict = {}
for _h, _col, _i in _HZ:
    _ins, _spy = [], []
    for _, r in _rf_buys.iterrows():
        iv = r[_col]
        if pd.notna(iv):
            _ins.append(float(iv))
            sv = _spy_map.get(r["Transaction Date"] or str(r["Filed"].date()), (None, None, None))[_i]
            if sv is not None:
                _spy.append(float(sv))
    avg_ins[_h] = (sum(_ins) / len(_ins)) if _ins else None
    avg_spy[_h] = (sum(_spy) / len(_spy)) if _spy else None
    n_hz[_h] = len(_ins)

_r30 = _rf_buys["30d Return"].dropna()
hit_rate = (100.0 * (_r30 > 0).mean()) if len(_r30) else None
N = int(len(_r30))

if N == 0 and not any(v is not None for v in avg_ins.values()):
    st.markdown(
        "<div class='research-empty'>Not enough insider buys with elapsed return windows in "
        "the current view to compute findings. Widen the date range or clear filters.</div>",
        unsafe_allow_html=True,
    )
else:
    def _sv(v):
        if v is None:
            return "<div class='stat-value'>—</div>"
        return f"<div class='stat-value {'pos' if v >= 0 else 'neg'}'>{'+' if v >= 0 else ''}{v:.1f}%</div>"

    def _spy_sub(h):
        return f"S&amp;P {avg_spy[h]:+.1f}%" if avg_spy[h] is not None else "S&amp;P —"

    _stat_html = (
        "<div class='stat-grid'>"
        f"<div class='stat-card'><div class='stat-label'>Avg 7-Day Return</div>{_sv(avg_ins['7d'])}"
        f"<div class='stat-sub'>{n_hz['7d']} buys · {_spy_sub('7d')}</div></div>"
        f"<div class='stat-card'><div class='stat-label'>Avg 30-Day Return</div>{_sv(avg_ins['30d'])}"
        f"<div class='stat-sub'>{n_hz['30d']} buys · {_spy_sub('30d')}</div></div>"
        f"<div class='stat-card'><div class='stat-label'>Avg 90-Day Return</div>{_sv(avg_ins['90d'])}"
        f"<div class='stat-sub'>{n_hz['90d']} buys · {_spy_sub('90d')}</div></div>"
        f"<div class='stat-card'><div class='stat-label'>30-Day Hit Rate</div>"
        f"<div class='stat-value'>{('%.0f%%' % hit_rate) if hit_rate is not None else '—'}</div>"
        f"<div class='stat-sub'>buys positive after 30d</div></div>"
        f"<div class='stat-card'><div class='stat-label'>Sample Size</div>"
        f"<div class='stat-value'>{N:,}</div><div class='stat-sub'>buys with 30d data</div></div>"
        "</div>"
    )
    st.markdown(_stat_html, unsafe_allow_html=True)

    # Dynamic plain-English takeaway
    if avg_ins["30d"] is not None and N > 0:
        _verb = "rose" if avg_ins["30d"] >= 0 else "fell"
        _tk = (f"On average, stocks {_verb} {abs(avg_ins['30d']):.1f}% in the 30 days after an "
               f"insider purchase (based on {N:,} buys).")
        if avg_spy["30d"] is not None:
            _diff = avg_ins["30d"] - avg_spy["30d"]
            _rel = "ahead of" if _diff >= 0 else "behind"
            _tk += (f" That is {abs(_diff):.1f} points {_rel} the S&amp;P 500's "
                    f"{avg_spy['30d']:+.1f}% over the same window.")
        _tk_cls = "" if avg_ins["30d"] >= 0 else " neg"
        st.markdown(f"<div class='research-takeaway{_tk_cls}'>{_tk}</div>", unsafe_allow_html=True)

    # Insider Buys vs S&P 500 — grouped bar chart
    st.markdown(
        "<div style='font-family:var(--font-mono);font-size:9.5px;color:#3a3a3a;"
        "text-transform:uppercase;letter-spacing:0.1em;margin:20px 0 8px;'>"
        "Insider Buys vs S&amp;P 500 · average return by horizon</div>",
        unsafe_allow_html=True,
    )
    _bm = go.Figure()
    _bm.add_trace(go.Bar(
        name="Insider Buys", x=["7D", "30D", "90D"],
        y=[avg_ins["7d"], avg_ins["30d"], avg_ins["90d"]],
        marker=dict(color="#e8e8e8"),
        hovertemplate="Insider %{x}: %{y:.2f}%<extra></extra>",
    ))
    _bm.add_trace(go.Bar(
        name="S&P 500", x=["7D", "30D", "90D"],
        y=[avg_spy["7d"], avg_spy["30d"], avg_spy["90d"]],
        marker=dict(color="#43506b"),
        hovertemplate="S&P 500 %{x}: %{y:.2f}%<extra></extra>",
    ))
    _bm.update_layout(
        **_BASE_LAYOUT,
        barmode="group", bargap=0.4, bargroupgap=0.12,
        xaxis=dict(**_AXIS_BASE, showgrid=False),
        yaxis=dict(**_AXIS_BASE, showgrid=True, ticksuffix="%", zeroline=True, zerolinecolor="#2c2c2c"),
        legend=dict(orientation="h", x=0, y=1.14, xanchor="left", yanchor="bottom",
                    bgcolor=_TRANSPARENT,
                    font=dict(color="#8a8a8a", size=10, family="IBM Plex Mono, monospace")),
    )
    _bm.update_layout(height=300)
    st.plotly_chart(_bm, use_container_width=True, config=_CHART_CONFIG)

st.markdown("---")

# ── Build table HTML ──────────────────────────────────────────────────────────
rows_html = ""
for _, row in display.iterrows():
    notable    = row.get("Notable", False)
    tr_class   = "notable" if notable else ""
    flag       = "<span class='notable-flag'>&#9670;</span>" if notable else ""
    url        = row["Filing URL"]
    link       = f'<a href="{url}" target="_blank" rel="noopener noreferrer" class="filing-link-btn">SEC</a>' if url else "—"
    ticker     = row.get("Ticker", "") or ""
    ticker_html = f"<span class='ticker-pill'>{_html.escape(ticker)}</span>" if ticker else ""
    sector     = row.get("Sector", "Unknown") or "Unknown"
    sector_lbl = sector if sector != "Unknown" else "—"

    is_cluster   = row.get("Accession No") in cluster_adsh
    cluster_html = "<span class='cluster-badge'>Cluster</span>" if is_cluster else ""

    # Watchlist star (keyed by ticker). Clicking toggles it via a query-param link.
    if ticker:
        if ticker in watchlist:
            _star_html = (f"<a class='star-btn star-on' href='{_star_href(watchlist - {ticker})}' "
                          f"target='_self' title='Remove from watchlist'>&#9733;</a>")
        else:
            _star_html = (f"<a class='star-btn star-off' href='{_star_href(watchlist | {ticker})}' "
                          f"target='_self' title='Add to watchlist'>&#9734;</a>")
    else:
        _star_html = "<span class='star-btn star-disabled' title='No ticker to watch'>&#9734;</span>"

    txn_type   = row["Transaction Type"]
    txn_cell   = TXN_PILL_HTML.get(
        txn_type,
        f"<span class='txn-pill txn-other'>{_html.escape(txn_type)}</span>"
    )
    co_cell    = (f"{_star_html}<span class='co-name'>{_html.escape(row['Company'])}</span>"
                  f"{ticker_html}{cluster_html}")

    _spark_key  = (ticker, row.get("Transaction Date") or str(row["Filed"].date())) if ticker else None
    _spark_json = json.dumps(spark_map.get(_spark_key, []))
    _est_val    = _fmt_value(row["Shares"], row["Price Per Share"])

    rows_html += (
        f'<tr class="{tr_class}"'
        f' data-spark=\'{_spark_json}\''
        f' data-ticker="{_html.escape(ticker)}"'
        f' data-exec-title="{_html.escape(str(row["Exec Title"]))}"'
        f' data-est-value="{_html.escape(_est_val)}"'
        f' data-sec-url="{_html.escape(url)}">'
        f"<td class='col-date'>{row['Filed_str']}</td>"
        f"<td class='col-txn'>{txn_cell}</td>"
        f"<td class='col-exec'>{flag}<span class='exec-name'>{_html.escape(str(row['Executive / Filer']))}</span></td>"
        f"<td class='col-title'>{_html.escape(str(row['Exec Title']))}</td>"
        f"<td class='col-co'>{co_cell}</td>"
        f"<td class='col-sector'>{_html.escape(sector_lbl)}</td>"
        f"<td class='col-shares'>{_fmt_shares(row['Shares'])}</td>"
        f"<td class='col-value'>{_est_val}</td>"
        f"<td class='col-ret'>{_fmt_returns(row['7d Return'], row['30d Return'], row['90d Return'])}</td>"
        f"<td class='col-link'>{link}</td>"
        f"</tr>"
    )

table_html = f"""
<div style="overflow-x:auto; max-height:560px; overflow-y:auto;
            border:1px solid #1a1a1a; border-radius:0; width:100%;">
  <table class="filing-table" style="min-width:1080px;">
    <colgroup>
      <col class="col-date">  <col class="col-txn">   <col class="col-exec">
      <col class="col-title"> <col class="col-co">    <col class="col-sector">
      <col class="col-shares"><col class="col-value"> <col class="col-ret">
      <col class="col-link">
    </colgroup>
    <thead><tr>
      <th class="col-date">Date</th>
      <th class="col-txn">Type</th>
      <th class="col-exec">Executive</th>
      <th class="col-title">Title</th>
      <th class="col-co">Company</th>
      <th class="col-sector">Sector</th>
      <th class="col-shares">Shares</th>
      <th class="col-value">Est. Value</th>
      <th class="col-ret">7d / 30d / 90d Returns</th>
      <th class="col-link">Link</th>
    </tr></thead>
    <tbody>{rows_html}</tbody>
  </table>
</div>
"""

# ── Replace table skeleton ────────────────────────────────────────────────────
with table_placeholder.container():
    tbl_left, tbl_right = st.columns([3, 1])
    with tbl_left:
        badge_html = f"<span class='badge'>{total} results</span>"
        if notable_buys:
            badge_html += f" &nbsp;<span class='badge badge-alert'>{notable_buys} notable</span>"
        st.markdown(
            f"<div class='section-label' style='display:flex;align-items:center;gap:14px;"
            f"justify-content:space-between;'>"
            f"<span>Recent Form 4 Filings</span><span>{badge_html}</span></div>",
            unsafe_allow_html=True,
        )

    with tbl_right:
        # Export exactly the current filtered view (all filters incl. watchlist).
        _exp = filtered.copy()
        _exp["Date"] = _exp["Filed"].dt.strftime("%Y-%m-%d")
        _exp["Transaction Type"] = (
            _exp["Transaction Type"].map(TXN_CLEAN_LABELS).fillna(_exp["Transaction Type"])
        )
        _exp["Estimated Value"] = (
            pd.to_numeric(_exp["Shares"], errors="coerce")
            * pd.to_numeric(_exp["Price Per Share"], errors="coerce")
        ).round(2)
        export_df = _exp[[
            "Date", "Transaction Type", "Executive / Filer", "Exec Title", "Company",
            "Ticker", "Sector", "Shares", "Price Per Share", "Estimated Value",
            "7d Return", "30d Return", "90d Return", "Location", "Filing URL",
        ]].rename(columns={
            "Executive / Filer": "Executive",
            "Exec Title": "Title",
            "Price Per Share": "Price Per Share ($)",
            "7d Return": "7d Return (%)",
            "30d Return": "30d Return (%)",
            "90d Return": "90d Return (%)",
        })
        st.download_button(
            "Download CSV", export_df.to_csv(index=False),
            file_name="insider_filings_export.csv", mime="text/csv",
            use_container_width=True,
        )

    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown(table_html, unsafe_allow_html=True)
    st.markdown("<br>", unsafe_allow_html=True)
    _cache_note = (
        f" &nbsp;/&nbsp; <span style='color:#5f5f5f;'>{_cache_hits}/{len(df)} from cache</span>"
        if _cache_hits > 0 else ""
    )
    st.markdown(
        f"<div style='font-family:var(--font-mono);font-size:9.5px;color:#3a3a3a;"
        f"text-transform:uppercase;letter-spacing:0.08em;'>Returns from transaction date &nbsp;/&nbsp; "
        f"Last fetched {datetime.now().strftime('%H:%M:%S')}{_cache_note}</div>",
        unsafe_allow_html=True,
    )

    # (Buy-return averages now live in the prominent "Research Findings" panel
    #  above, benchmarked against the S&P 500.)

    # ── Stock Price Explorer ──────────────────────────────────────────────────
    st.markdown("---")
    st.markdown("<div class='section-label'>Stock Price Explorer — 30 Days Post-Transaction</div>", unsafe_allow_html=True)

    chart_df = filtered[filtered["Ticker"].astype(bool)][
        ["Company", "Ticker", "Transaction Date", "Filed"]
    ].copy()
    chart_df["Label"] = (
        chart_df["Company"].str[:32] + " (" + chart_df["Ticker"] + ") — " +
        chart_df["Transaction Date"].fillna(chart_df["Filed"].dt.strftime("%Y-%m-%d"))
    )

    if chart_df.empty:
        st.info("No tickers resolved for the current filter — try a broader date range.")
    else:
        selected = st.selectbox("Select a filing", options=chart_df["Label"].tolist(), index=0)
        sel      = chart_df[chart_df["Label"] == selected].iloc[0]
        sel_ticker = sel["Ticker"]
        sel_date   = sel["Transaction Date"] or str(sel["Filed"].date())

        with st.spinner(f"Loading {sel_ticker} chart…"):
            chart_data = _get_stock_chart_data(sel_ticker, sel_date)

        if chart_data.empty:
            st.warning(f"No price data for {sel_ticker} from {sel_date}.")
        else:
            base_price = chart_data["Close"].iloc[0]
            end_price  = chart_data["Close"].iloc[-1]
            up         = end_price >= base_price
            line_color = "#22c55e" if up else "#ef4444"
            fill_color = "rgba(34,197,94,0.10)" if up else "rgba(239,68,68,0.10)"
            fig_chart  = go.Figure()
            fig_chart.add_trace(go.Scatter(
                x=chart_data["Date"], y=chart_data["Close"],
                mode="lines",
                line=dict(color=line_color, width=2),
                fill="tozeroy",
                fillcolor=fill_color,
                hovertemplate="%{x|%b %d}<br><b>$%{y:.2f}</b><extra></extra>",
                name=sel_ticker,
            ))
            fig_chart.add_vline(
                x=int(pd.to_datetime(sel_date).timestamp() * 1000),
                line_dash="dash", line_color="#ffffff", line_width=1,
                annotation_text="TRANSACTION",
                annotation_font=dict(color="#e8e8e8", size=9, family="IBM Plex Mono, monospace"),
                annotation_position="top right",
            )
            fig_chart.add_hline(
                y=base_price, line_dash="dot", line_color="#333333", line_width=1,
                annotation_text=f"ENTRY ${base_price:.2f}",
                annotation_font=dict(color="#5f5f5f", size=9, family="IBM Plex Mono, monospace"),
                annotation_position="bottom right",
            )
            fig_chart.update_layout(
                **_BASE_LAYOUT,
                title=dict(
                    text=f"{sel_ticker} / 30 DAYS POST-TRANSACTION",
                    font=dict(size=11, color="#8a8a8a", family="IBM Plex Mono, monospace"),
                    x=0, pad=dict(l=0),
                ),
                xaxis=dict(**_AXIS_BASE, showgrid=False, tickformat="%b %d", nticks=8),
                yaxis=dict(**_AXIS_BASE, showgrid=True, tickprefix="$"),
                showlegend=False,
            )
            fig_chart.update_layout(height=320, margin_t=36)
            st.plotly_chart(fig_chart, use_container_width=True, config=_CHART_CONFIG)

# ── Cluster Buy Signals ───────────────────────────────────────────────────────
st.markdown("---")
st.markdown("<div class='section-label'>Cluster Buy Signals</div>", unsafe_allow_html=True)
if cluster_list:
    _crows = ""
    for _i, _c in enumerate(cluster_list, 1):
        _dr = _c["start"].strftime("%b %d, %Y")
        if _c["end"] != _c["start"]:
            _dr += " – " + _c["end"].strftime("%b %d, %Y")
        _crows += (
            f"<tr><td class='rank'>{_i:02d}</td>"
            f"<td><span class='signal-co'>{_html.escape(_c['company'])}</span></td>"
            f"<td class='num'>{_c['insiders']}</td>"
            f"<td class='num'>{_c['buys']}</td>"
            f"<td class='num'>{_c['shares']:,.0f}</td>"
            f"<td class='signal-dates'>{_dr}</td></tr>"
        )
    st.markdown(
        "<div class='signal-wrap'><table class='signal-table'>"
        "<thead><tr><th>#</th><th>Company</th>"
        "<th class='num'>Insiders</th><th class='num'>Buys</th>"
        "<th class='num'>Total Shares</th><th>Window</th></tr></thead>"
        f"<tbody>{_crows}</tbody></table></div>",
        unsafe_allow_html=True,
    )
    st.markdown(
        "<div style='font-family:var(--font-mono);font-size:9.5px;color:#3a3a3a;"
        "text-transform:uppercase;letter-spacing:0.06em;margin-top:12px;'>"
        "A cluster is 2 or more different insiders buying the same company's stock within "
        "7 days — a stronger bullish signal than any single purchase.</div>",
        unsafe_allow_html=True,
    )
else:
    st.markdown(
        "<div class='signal-empty'>No cluster buys detected in the current view.</div>",
        unsafe_allow_html=True,
    )

# ── Top Performing Insiders (Insider Score) ───────────────────────────────────
st.markdown("---")
st.markdown("<div class='section-label'>Top Performing Insiders</div>", unsafe_allow_html=True)
_perf = filtered[(filtered["Transaction Type"] == "🟢 Buy") & filtered["30d Return"].notna()]
_score = (
    _perf.groupby(["Executive / Filer", "Company"])
    .agg(n=("30d Return", "size"), avg=("30d Return", "mean"))
    .reset_index()
) if not _perf.empty else pd.DataFrame()
if not _score.empty:
    _score = _score[_score["n"] >= 2].sort_values("avg", ascending=False).head(15)
if not _score.empty:
    _srows = ""
    for _i, (_, _r) in enumerate(_score.iterrows(), 1):
        _av   = float(_r["avg"])
        _cls  = "ret-pos" if _av >= 0 else "ret-neg"
        _sign = "+" if _av >= 0 else ""
        _srows += (
            f"<tr><td class='rank'>{_i:02d}</td>"
            f"<td><span class='signal-co'>{_html.escape(str(_r['Executive / Filer']))}</span>"
            f"<div class='signal-sub'>{_html.escape(str(_r['Company']))}</div></td>"
            f"<td class='num'>{int(_r['n'])}</td>"
            f"<td class='num {_cls}'>{_sign}{_av:.1f}%</td></tr>"
        )
    st.markdown(
        "<div class='signal-wrap'><table class='signal-table'>"
        "<thead><tr><th>#</th><th>Insider</th>"
        "<th class='num'>Buys Tracked</th><th class='num'>Avg 30D Return</th></tr></thead>"
        f"<tbody>{_srows}</tbody></table></div>",
        unsafe_allow_html=True,
    )
    st.markdown(
        "<div style='font-family:var(--font-mono);font-size:9.5px;color:#3a3a3a;"
        "text-transform:uppercase;letter-spacing:0.06em;margin-top:12px;'>"
        "Average 30-day stock return following each insider's buys · minimum 2 tracked "
        "buys · ranked by average gain.</div>",
        unsafe_allow_html=True,
    )
else:
    st.markdown(
        "<div class='signal-empty'>Not enough tracked buys yet — insiders need at least "
        "2 buys with 30-day return data in the current view.</div>",
        unsafe_allow_html=True,
    )

# ── About section ─────────────────────────────────────────────────────────────
st.markdown("---")
st.markdown(
    """
<div class="about-section">
  <div class="section-label">About This Project</div>
  <div class="about-grid">
    <div class="about-col">
      <div class="about-h">What it does</div>
      <p class="about-p">Insider monitors SEC Form 4 filings — the disclosures corporate executives,
      directors, and 10% owners must file within two business days of trading their own company's
      stock — and analyzes the core research question: do insider <em>buys</em> actually predict
      future returns? It measures what each stock did over the 7, 30, and 90 days after a purchase
      and benchmarks that against the S&amp;P 500.</p>
      <div class="about-h">How it works</div>
      <p class="about-p">Filings are pulled live from the SEC EDGAR full-text search API and parsed
      for transaction type, insider role, share count, and price. Tickers, sectors, and forward
      returns are enriched with Yahoo Finance data, then cached and rendered in Streamlit — no
      database and no paid data feed. The full result set is available as a CSV download above.</p>
    </div>
    <div class="about-col about-side">
      <div class="about-h">Built by</div>
      <p class="about-name">Jayal Neema</p>
      <p class="about-meta">Class of 2027<br>California High School</p>
      <a class="about-link" href="https://github.com/jayalqqq/insider-moniter" target="_blank" rel="noopener">View source on GitHub &#8599;</a>
      <p class="about-disclaimer">For research and educational use only. Not investment advice.</p>
    </div>
  </div>
</div>
""",
    unsafe_allow_html=True,
)

# ── Hover sparkline tooltip JS (fixed: delayed hide + pointer-events + above row) ──
components.html("""
<script>
(function() {
  var p  = window.parent ? window.parent : window;
  var pd = p.document;
  var hideTimer = null;

  // Build or reuse tooltip
  var tt = pd.getElementById('spark-tooltip');
  if (!tt) {
    tt = pd.createElement('div');
    tt.id = 'spark-tooltip';
    Object.assign(tt.style, {
      position:     'fixed',
      background:   '#000',
      border:       '1px solid #2c2c2c',
      borderLeft:   '2px solid #fff',
      borderRadius: '0',
      padding:      '10px 14px',
      fontFamily:   "'IBM Plex Mono', monospace",
      fontSize:     '11px',
      color:        '#e8e8e8',
      zIndex:       '99998',
      pointerEvents:'auto',
      opacity:      '0',
      transition:   'opacity 0.15s ease',
      boxShadow:    '0 12px 40px rgba(0,0,0,0.85)',
      minWidth:     '190px',
      maxWidth:     '240px'
    });
    pd.body.appendChild(tt);
  }

  // Tooltip stays open when hovered — cancel pending hide
  tt.addEventListener('mouseenter', function() { clearTimeout(hideTimer); });
  tt.addEventListener('mouseleave', function() {
    hideTimer = setTimeout(function() { tt.style.opacity = '0'; }, 150);
  });

  function makeSpark(prices, w, h) {
    if (!prices || prices.length < 3) return '';
    var mn = Math.min.apply(null, prices), mx = Math.max.apply(null, prices);
    var rng = mx - mn || 1;
    var pts = prices.map(function(v, i) {
      var x = (i / (prices.length - 1)) * w;
      var y = h - 4 - ((v - mn) / rng) * (h - 8);
      return x.toFixed(1) + ',' + y.toFixed(1);
    }).join(' ');
    var clr = prices[prices.length - 1] >= prices[0] ? '#4ade80' : '#f87171';
    return '<svg width="' + w + '" height="' + h + '" viewBox="0 0 ' + w + ' ' + h +
           '" style="display:block;margin-bottom:8px;">' +
           '<polyline points="' + pts + '" fill="none" stroke="' + clr +
           '" stroke-width="1.5" stroke-linejoin="round" stroke-linecap="round"/></svg>';
  }

  function positionAboveRow(tr) {
    var rect  = tr.getBoundingClientRect();
    var vw    = p.innerWidth;
    var ttH   = tt.offsetHeight || 165;
    var top   = rect.top - ttH - 6;
    if (top < 6) top = rect.bottom + 6;   // fallback: below row
    var left  = rect.right - 220;
    if (left < 6) left = 6;
    if (left + 250 > vw) left = vw - 256;
    tt.style.left = left + 'px';
    tt.style.top  = top  + 'px';
  }

  setTimeout(function() {
    pd.querySelectorAll('.filing-table tr[data-spark]').forEach(function(tr) {
      tr.addEventListener('mouseenter', function() {
        clearTimeout(hideTimer);

        var prices;
        try { prices = JSON.parse(tr.getAttribute('data-spark')); } catch(e) { prices = []; }
        var ticker    = tr.getAttribute('data-ticker')     || '';
        var execTitle = tr.getAttribute('data-exec-title') || '—';
        var estValue  = tr.getAttribute('data-est-value')  || '—';

        var h = '';
        if (ticker) h += '<div style="font-weight:700;color:#a78bfa;margin-bottom:8px;font-size:13px;">' + ticker + ' — 30d</div>';
        h += makeSpark(prices, 180, 44);
        h += '<div style="color:#9ca3af;font-size:11px;line-height:1.9;">' +
             'Title:&nbsp;<span style="color:#e5e7eb;">' + execTitle + '</span><br>' +
             'Value:&nbsp;<span style="color:#e5e7eb;">' + estValue  + '</span></div>';

        tt.innerHTML = h;
        tt.style.opacity = '0';          // reset before measuring
        tt.style.display = 'block';
        positionAboveRow(tr);
        tt.style.opacity = '1';
      });

      tr.addEventListener('mouseleave', function() {
        hideTimer = setTimeout(function() { tt.style.opacity = '0'; }, 150);
      });
    });
  }, 350);
})();
</script>
""", height=0)

# ── Toast: data refreshed ─────────────────────────────────────────────────────
if st.session_state.get("_refreshed"):
    del st.session_state["_refreshed"]
    components.html("""
<script>
(function() {
  var p  = window.parent ? window.parent : window;
  var pd = p.document;
  if (p.matchMedia && p.matchMedia('(prefers-reduced-motion: reduce)').matches) return;

  var container = pd.getElementById('toast-container');
  if (!container) {
    container = pd.createElement('div');
    container.id = 'toast-container';
    pd.body.appendChild(container);
  }

  var t = pd.createElement('div');
  t.className = 'st-toast';
  t.style.borderLeftColor = '#22c55e';
  t.textContent = '✅ Data refreshed!';
  container.appendChild(t);

  p.requestAnimationFrame(function() {
    p.requestAnimationFrame(function() { t.classList.add('toast-show'); });
  });

  setTimeout(function() {
    t.classList.remove('toast-show');
    setTimeout(function() {
      if (container.contains(t)) container.removeChild(t);
    }, 400);
  }, 3500);
})();
</script>
""", height=0)
