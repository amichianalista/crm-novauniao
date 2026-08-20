from __future__ import annotations

import base64
import html
import os
import re
from pathlib import Path
from typing import Any
from urllib.parse import quote

import pandas as pd
import psycopg
import streamlit as st
from dotenv import load_dotenv
from psycopg import sql


APP_DIR = Path(__file__).resolve().parent
BACKGROUND_PATH = APP_DIR / "assets" / "Background.png"
LOGO_PATH = APP_DIR / "assets" / "logo.png"
SCHEMA_NAME = "clientes_novauniao"
TABLE_NAME = "prospecao_mkt"
APP_TIMEZONE = "America/Sao_Paulo"
PERIOD_OPTIONS = ["Hoje", "Essa semana", "Esse mes"]


st.set_page_config(
    page_title="CRM Nova Uniao",
    page_icon="NU",
    layout="wide",
    initial_sidebar_state="collapsed",
)


def image_data_uri(path: Path) -> str:
    if not path.exists():
        return ""
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:image/png;base64,{encoded}"


def inject_styles() -> None:
    background = image_data_uri(BACKGROUND_PATH)
    st.markdown(
        f"""
        <style>
        :root {{
            --ink: #ffffff;
            --muted: rgba(255, 255, 255, .76);
            --line: rgba(255, 255, 255, .20);
            --panel: rgba(3, 12, 28, .58);
        }}

        .stApp {{
            background-image: url("{background}");
            background-size: cover;
            background-position: center;
            background-attachment: fixed;
        }}

        .block-container {{
            max-width: 1380px;
            padding-top: 1.1rem;
            padding-bottom: 2rem;
        }}

        html, body, .stApp,
        .stApp h1, .stApp h2, .stApp h3,
        .stApp p, .stApp label, .stApp span,
        .stApp div, .stApp button {{
            color: var(--ink);
            letter-spacing: 0;
        }}

        .crm-header {{
            display: flex;
            align-items: center;
            justify-content: center;
            min-height: 13rem;
            padding: 1.35rem 1.5rem;
            margin-bottom: 1.15rem;
            border: 1px solid var(--line);
            border-radius: 8px;
            background:
                radial-gradient(circle at 50% 35%, rgba(57, 164, 255, .18), transparent 36%),
                linear-gradient(90deg, rgba(2, 10, 24, .80), rgba(4, 20, 45, .52));
            box-shadow: 0 22px 64px rgba(0, 0, 0, .30);
            backdrop-filter: blur(9px);
        }}

        .brand-lockup {{
            display: flex;
            align-items: center;
            justify-content: center;
            width: 100%;
        }}

        .logo-mark {{
            width: min(34rem, 72vw);
            max-height: 10rem;
            height: auto;
            object-fit: contain;
            filter: brightness(0) invert(1) drop-shadow(0 16px 36px rgba(0, 0, 0, .36));
        }}

        div[data-testid="stCaptionContainer"] {{
            color: var(--muted) !important;
        }}

        div[data-testid="stCaptionContainer"] p,
        div[data-testid="stMarkdownContainer"] p {{
            color: var(--muted) !important;
        }}

        .period-title {{
            width: min(100%, 920px);
            margin: .2rem auto .45rem;
            color: #fff;
            font-size: 1.02rem;
            font-weight: 800;
            line-height: 1.15;
        }}

        .stSelectbox label {{
            display: none;
        }}

        div[data-baseweb="select"] *,
        [data-testid="stSelectbox"] * {{
            color: #fff !important;
        }}

        div[data-baseweb="select"] > div {{
            min-height: 3rem;
            border-radius: 8px !important;
            background:
                linear-gradient(180deg, rgba(10, 38, 78, .92), rgba(3, 14, 32, .92)) !important;
            border: 1px solid rgba(99, 179, 255, .42) !important;
            box-shadow:
                inset 0 1px 0 rgba(255, 255, 255, .10),
                0 12px 34px rgba(0, 0, 0, .28);
        }}

        div[data-baseweb="select"] > div:hover {{
            border-color: rgba(99, 179, 255, .72) !important;
        }}

        div[data-baseweb="popover"],
        ul[role="listbox"] {{
            background: #071326 !important;
            border-color: rgba(99, 179, 255, .26) !important;
        }}

        li[role="option"] {{
            color: #fff !important;
            background: #071326 !important;
        }}

        li[role="option"]:hover {{
            background: rgba(57, 164, 255, .22) !important;
        }}

        [data-testid="stDataFrame"] {{
            border: 1px solid var(--line);
            border-radius: 8px;
            overflow: hidden;
            background: linear-gradient(180deg, rgba(4, 16, 36, .94), rgba(2, 9, 22, .90));
            box-shadow: 0 24px 70px rgba(0, 0, 0, .38);
        }}

        .detail-title {{
            font-size: clamp(2rem, 4vw, 3.4rem);
            font-weight: 850;
            line-height: 1;
            margin: 1.6rem 0 .45rem;
            color: #fff;
            text-shadow: 0 18px 42px rgba(0, 0, 0, .38);
        }}

        .detail-subtitle {{
            color: var(--muted);
            font-size: .98rem;
            margin-bottom: 1.3rem;
        }}

        .cnpj-highlight {{
            display: inline-flex;
            align-items: center;
            gap: .48rem;
            width: fit-content;
            margin: 0 0 .72rem;
            padding: .46rem .72rem;
            border: 1px solid rgba(99, 179, 255, .36);
            border-radius: 8px;
            background:
                linear-gradient(135deg, rgba(57, 164, 255, .20), transparent 48%),
                rgba(3, 14, 32, .58);
            box-shadow: 0 14px 36px rgba(0, 0, 0, .24);
        }}

        .cnpj-label {{
            color: rgba(99, 179, 255, .98);
            font-size: .72rem;
            font-weight: 820;
            letter-spacing: .08em;
            text-transform: uppercase;
        }}

        .cnpj-value {{
            color: #fff;
            font-size: 1.02rem;
            font-weight: 820;
        }}

        .section-title {{
            color: #fff;
            font-size: 1.45rem;
            font-weight: 840;
            letter-spacing: .02em;
            margin: 1.2rem 0 .85rem;
            text-transform: uppercase;
        }}

        .contact-decision {{
            width: fit-content;
            min-width: min(100%, 28rem);
            margin-bottom: .9rem;
            padding: .7rem .85rem;
            border: 1px solid rgba(99, 179, 255, .24);
            border-radius: 8px;
            background:
                linear-gradient(135deg, rgba(57, 164, 255, .16), transparent 46%),
                rgba(3, 14, 32, .46);
            box-shadow: 0 16px 42px rgba(0, 0, 0, .26);
        }}

        .contact-label {{
            color: rgba(99, 179, 255, .95);
            font-size: .72rem;
            font-weight: 800;
            letter-spacing: .08em;
            text-transform: uppercase;
            margin-bottom: .18rem;
        }}

        .contact-name {{
            color: #fff;
            font-size: 1.12rem;
            font-weight: 780;
        }}

        .field-label {{
            color: var(--muted);
            font-size: .74rem;
            font-weight: 720;
            text-transform: uppercase;
            margin-bottom: .1rem;
        }}

        .field-value {{
            color: #fff;
            font-size: .95rem;
            word-break: break-word;
            margin-bottom: .72rem;
        }}

        .stButton > button,
        .stLinkButton > a {{
            border-radius: 8px;
            font-weight: 700;
            min-height: 2.35rem;
            color: #fff !important;
            border-color: rgba(99, 179, 255, .28) !important;
            background: linear-gradient(135deg, rgba(13, 92, 170, .92), rgba(9, 37, 76, .92)) !important;
            box-shadow: 0 14px 34px rgba(0, 0, 0, .25);
        }}

        @media (max-width: 760px) {{
            .crm-header {{
                min-height: 9.5rem;
                padding: 1rem;
            }}

            .logo-mark {{
                width: min(24rem, 78vw);
                max-height: 7.6rem;
            }}

            .period-title {{
                width: 100%;
            }}
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_header() -> None:
    logo = image_data_uri(LOGO_PATH)
    logo_html = f'<img class="logo-mark" src="{logo}" alt="Nova Uniao">' if logo else ""
    st.markdown(
        f"""
        <header class="crm-header">
            <div class="brand-lockup">
                {logo_html}
            </div>
        </header>
        """,
        unsafe_allow_html=True,
    )


def clean_text(value: Any, fallback: str = "-") -> str:
    if value is None:
        return fallback
    if isinstance(value, float) and pd.isna(value):
        return fallback
    text = " ".join(str(value).strip().split())
    return text or fallback


def safe_text(value: Any, fallback: str = "-") -> str:
    return html.escape(clean_text(value, fallback))


def digits_only(value: Any) -> str:
    return re.sub(r"\D+", "", clean_text(value, ""))


def format_phone(phone: Any) -> str:
    digits = digits_only(phone)
    if not digits:
        return "-"
    if digits.startswith("55") and len(digits) >= 12:
        digits = digits[2:]
    if len(digits) == 11:
        return f"({digits[:2]}) {digits[2:7]}-{digits[7:]}"
    if len(digits) == 10:
        return f"({digits[:2]}) {digits[2:6]}-{digits[6:]}"
    return digits


def whatsapp_url(phone: Any) -> str:
    digits = digits_only(phone)
    if not digits:
        return ""
    if len(digits) in (10, 11):
        digits = f"55{digits}"
    elif not digits.startswith("55"):
        digits = f"55{digits}"
    return f"https://wa.me/{digits}"


def email_url(email: Any) -> str:
    address = clean_text(email, "")
    if not address:
        return ""
    return f"mailto:{quote(address, safe='@._+-')}"


def normalize_url(value: Any) -> str:
    url = clean_text(value, "")
    if not url:
        return ""
    if url.startswith(("http://", "https://")):
        return url
    return f"https://{url}"


def format_datetime(value: Any) -> str:
    if pd.isna(value):
        return "-"
    timestamp = pd.to_datetime(value, errors="coerce")
    if pd.isna(timestamp):
        return "-"
    if timestamp.tzinfo is not None:
        timestamp = timestamp.tz_convert(APP_TIMEZONE)
    return timestamp.strftime("%d/%m/%Y %H:%M")


def cliente_sga_label(value: Any) -> str:
    if value is True:
        return "Sim"
    if value is False:
        return "Nao"
    return "Nao informado"


def get_database_url() -> str:
    load_dotenv(dotenv_path=APP_DIR / ".env")
    load_dotenv(dotenv_path=APP_DIR.parent / ".env")
    database_url = os.getenv("SUPABASE_DATABASE_URL")
    if not database_url:
        try:
            database_url = st.secrets.get("SUPABASE_DATABASE_URL", "")
        except Exception:
            database_url = ""
    if not database_url:
        st.error("SUPABASE_DATABASE_URL nao encontrada no .env local ou nos secrets do Streamlit.")
        st.stop()
    return database_url


@st.cache_data(ttl=120, show_spinner=False)
def load_leads() -> pd.DataFrame:
    database_url = get_database_url()
    query = sql.SQL("select * from {}.{} order by ultima_interacao desc nulls last").format(
        sql.Identifier(SCHEMA_NAME),
        sql.Identifier(TABLE_NAME),
    )
    with psycopg.connect(database_url) as conn:
        with conn.cursor() as cur:
            cur.execute(query)
            columns = [desc.name for desc in cur.description]
            df = pd.DataFrame(cur.fetchall(), columns=columns)

    if df.empty:
        return df

    df["ultima_interacao_dt"] = pd.to_datetime(df["ultima_interacao"], errors="coerce", utc=True)
    df["ultima_interacao_local"] = df["ultima_interacao_dt"].dt.tz_convert(APP_TIMEZONE)
    df["ultima_interacao_fmt"] = df["ultima_interacao_local"].map(format_datetime)
    df["telefone_principal"] = df.apply(primary_phone, axis=1)
    df["telefone_formatado"] = df["telefone_principal"].map(format_phone)
    df["nome_exibicao"] = df.apply(
        lambda row: clean_text(row.get("empresa"), clean_text(row.get("decisor"), "Lead sem nome")),
        axis=1,
    )
    df["decisor_exibicao"] = df["decisor"].map(lambda value: clean_text(value, "-"))
    df["localizacao"] = df.apply(
        lambda row: ", ".join(
            part
            for part in [clean_text(row.get("municipio"), ""), clean_text(row.get("uf"), "")]
            if part
        )
        or "-",
        axis=1,
    )
    df["cliente_sga_fmt"] = df["cliente_sga"].map(cliente_sga_label)
    return df


def primary_phone(row: pd.Series) -> str:
    phone = digits_only(row.get("celular_decisor"))
    if phone:
        return phone
    phones = row.get("telefones_contato")
    if isinstance(phones, list):
        for candidate in phones:
            phone = digits_only(candidate)
            if phone:
                return phone
    return ""


def all_phones(row: pd.Series) -> list[tuple[str, str]]:
    phones: list[tuple[str, str]] = []
    seen: set[str] = set()

    def add_phone(label: str, value: Any) -> None:
        digits = digits_only(value)
        if digits and digits not in seen:
            seen.add(digits)
            phones.append((label, digits))

    add_phone("Celular decisor", row.get("celular_decisor"))
    contato = row.get("telefones_contato")
    if isinstance(contato, list):
        for index, phone in enumerate(contato, start=1):
            add_phone(f"Telefone {index}", phone)
    return phones


def filter_by_period(df: pd.DataFrame, period: str) -> pd.DataFrame:
    now = pd.Timestamp.now(tz=APP_TIMEZONE)
    start_today = now.normalize()

    if period == "Hoje":
        start = start_today
        end = start + pd.Timedelta(days=1)
    elif period == "Essa semana":
        start = start_today - pd.Timedelta(days=now.weekday())
        end = start + pd.Timedelta(days=7)
    else:
        start = start_today.replace(day=1)
        end = start + pd.DateOffset(months=1)

    filtered = df[
        (df["ultima_interacao_local"].notna())
        & (df["ultima_interacao_local"] >= start)
        & (df["ultima_interacao_local"] < end)
    ].copy()
    return filtered.sort_values("ultima_interacao_local", ascending=False)


def render_period_selector(df: pd.DataFrame) -> pd.DataFrame:
    _, center, _ = st.columns([0.14, 0.72, 0.14])
    with center:
        st.markdown('<div class="period-title">Ultima interacao</div>', unsafe_allow_html=True)
        period = st.selectbox("Ultima interacao", PERIOD_OPTIONS, index=0)

        return filter_by_period(df, period)


def render_table(df: pd.DataFrame) -> int:
    table = df[
        [
            "ultima_interacao_fmt",
            "nome_exibicao",
            "decisor_exibicao",
        ]
    ].rename(
        columns={
            "ultima_interacao_fmt": "Ultima interacao",
            "nome_exibicao": "Empresa",
            "decisor_exibicao": "Decisor",
        }
    )

    _, center, _ = st.columns([0.14, 0.72, 0.14])
    with center:
        event = st.dataframe(
            table,
            width="stretch",
            height=330,
            hide_index=True,
            on_select="rerun",
            selection_mode="single-row",
            column_config={
                "Ultima interacao": st.column_config.TextColumn("Ultima interacao", width="small"),
                "Empresa": st.column_config.TextColumn("Empresa", width="large"),
                "Decisor": st.column_config.TextColumn("Decisor", width="medium"),
            },
        )

    selected_rows = event.selection.rows if event and event.selection else []
    if selected_rows:
        return int(selected_rows[0])
    return 0


def field(label: str, value: Any) -> None:
    st.markdown(
        f"""
        <div class="field-label">{safe_text(label)}</div>
        <div class="field-value">{safe_text(value)}</div>
        """,
        unsafe_allow_html=True,
    )


def render_contact_actions(row: pd.Series) -> None:
    phones = all_phones(row)
    instagram = normalize_url(row.get("url_instagram"))
    facebook = normalize_url(row.get("url_facebook"))

    st.markdown('<div class="section-title">Contatos</div>', unsafe_allow_html=True)
    st.markdown(
        f"""
        <div class="contact-decision">
            <div class="contact-label">Decisor</div>
            <div class="contact-name">{safe_text(row.get("decisor_exibicao"))}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    phone_cols = st.columns(3)
    if phones:
        for index, (label, phone) in enumerate(phones):
            with phone_cols[index % len(phone_cols)]:
                st.link_button(
                    f"{label}: {format_phone(phone)}",
                    whatsapp_url(phone),
                    width="stretch",
                )
    else:
        st.caption("Nenhum telefone disponivel.")

    social_links = [
        ("Instagram", instagram),
        ("Facebook", facebook),
    ]
    visible_social_links = [(label, url) for label, url in social_links if url]
    if visible_social_links:
        social_cols = st.columns(len(visible_social_links))
        for index, (label, url) in enumerate(visible_social_links):
            social_cols[index].link_button(label, url, width="stretch")


def render_lead_detail(row: pd.Series) -> None:
    cnpj = clean_text(row.get("cnpj"), "")
    cnpj_html = (
        f"""
        <div class="cnpj-highlight">
            <span class="cnpj-label">CNPJ</span>
            <span class="cnpj-value">{safe_text(cnpj)}</span>
        </div>
        """
        if cnpj
        else ""
    )
    st.markdown(
        f"""
        <div class="detail-title">{safe_text(row.get("nome_exibicao"))}</div>
        {cnpj_html}
        <div class="detail-subtitle">Ultima interacao: {safe_text(row.get("ultima_interacao_fmt"))}</div>
        """,
        unsafe_allow_html=True,
    )

    render_contact_actions(row)

    st.markdown('<div class="section-title">Dados do lead</div>', unsafe_allow_html=True)
    c1, c2, c3 = st.columns(3)
    with c1:
        field("Empresa", row.get("empresa"))
        field("Decisor", row.get("decisor"))
        field("Email", row.get("email"))
        field("CNPJ", row.get("cnpj"))
    with c2:
        field("Municipio / UF", row.get("localizacao"))
        field("Endereco", row.get("endereco"))
        field("Natureza juridica", row.get("natureza_juridica"))
        field("Cliente SGA", row.get("cliente_sga_fmt"))
    with c3:
        field("Porte", row.get("porte"))
        field("Capital social", row.get("capital_social"))
        field("Anos de mercado", row.get("anos_mercado"))
        field("Ultima interacao", row.get("ultima_interacao_fmt"))


def main() -> None:
    inject_styles()

    with st.spinner("Carregando leads do Supabase..."):
        df = load_leads()

    render_header()

    if df.empty:
        st.warning("Nenhum lead encontrado na tabela.")
        return

    filtered = render_period_selector(df)
    if filtered.empty:
        st.warning("Nenhum lead encontrado nesse periodo.")
        return

    filtered = filtered.reset_index(drop=True)
    selected_index = render_table(filtered)
    selected_row = filtered.iloc[selected_index]

    render_lead_detail(selected_row)


if __name__ == "__main__":
    main()
