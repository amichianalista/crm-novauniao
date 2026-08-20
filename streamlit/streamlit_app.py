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
            --ink: #18212c;
            --muted: #5f6b7a;
            --line: rgba(24, 33, 44, .18);
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

        h1, h2, h3, p, label {{
            color: var(--ink);
            letter-spacing: 0;
        }}

        h1 {{
            font-size: 1.75rem;
            margin-bottom: .15rem;
        }}

        div[data-testid="stCaptionContainer"] {{
            color: var(--muted);
        }}

        [data-testid="stDataFrame"] {{
            border: 1px solid var(--line);
            border-radius: 8px;
            overflow: hidden;
        }}

        .detail-title {{
            font-size: 1.25rem;
            font-weight: 760;
            margin: 1rem 0 .1rem;
            color: var(--ink);
        }}

        .detail-subtitle {{
            color: var(--muted);
            font-size: .92rem;
            margin-bottom: .8rem;
        }}

        .field-label {{
            color: var(--muted);
            font-size: .74rem;
            font-weight: 720;
            text-transform: uppercase;
            margin-bottom: .1rem;
        }}

        .field-value {{
            color: var(--ink);
            font-size: .95rem;
            word-break: break-word;
            margin-bottom: .72rem;
        }}

        .stButton > button,
        .stLinkButton > a {{
            border-radius: 8px;
            font-weight: 700;
            min-height: 2.35rem;
        }}
        </style>
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
    c1, c2 = st.columns([0.28, 0.72])
    with c1:
        period = st.selectbox("Ultima interacao", PERIOD_OPTIONS, index=0)
    with c2:
        st.write("")
        st.caption("Os leads abaixo seguem sempre a data da ultima_interacao, do mais recente para o mais antigo.")

    filtered = filter_by_period(df, period)
    st.caption(f"{len(filtered)} leads encontrados em: {period}")
    return filtered


def render_table(df: pd.DataFrame) -> int:
    table = df[
        [
            "ultima_interacao_fmt",
            "nome_exibicao",
            "decisor_exibicao",
            "telefone_formatado",
            "email",
            "localizacao",
            "cliente_sga_fmt",
        ]
    ].rename(
        columns={
            "ultima_interacao_fmt": "Ultima interacao",
            "nome_exibicao": "Empresa / Lead",
            "decisor_exibicao": "Decisor",
            "telefone_formatado": "Telefone",
            "email": "Email",
            "localizacao": "Localizacao",
            "cliente_sga_fmt": "Cliente SGA",
        }
    )
    event = st.dataframe(
        table,
        width="stretch",
        height=430,
        hide_index=True,
        on_select="rerun",
        selection_mode="single-row",
        column_config={
            "Ultima interacao": st.column_config.TextColumn("Ultima interacao", width="small"),
            "Empresa / Lead": st.column_config.TextColumn("Empresa / Lead", width="large"),
            "Decisor": st.column_config.TextColumn("Decisor", width="medium"),
            "Telefone": st.column_config.TextColumn("Telefone", width="small"),
            "Email": st.column_config.TextColumn("Email", width="medium"),
            "Localizacao": st.column_config.TextColumn("Localizacao", width="small"),
            "Cliente SGA": st.column_config.TextColumn("Cliente SGA", width="small"),
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
    email = email_url(row.get("email"))
    instagram = normalize_url(row.get("url_instagram"))
    facebook = normalize_url(row.get("url_facebook"))

    st.subheader("Contato")
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

    link_cols = st.columns(3)
    if email:
        link_cols[0].link_button("Email", email, width="stretch")
    else:
        link_cols[0].button("Email", disabled=True, width="stretch")
    if instagram:
        link_cols[1].link_button("Instagram", instagram, width="stretch")
    else:
        link_cols[1].button("Instagram", disabled=True, width="stretch")
    if facebook:
        link_cols[2].link_button("Facebook", facebook, width="stretch")
    else:
        link_cols[2].button("Facebook", disabled=True, width="stretch")


def render_lead_detail(row: pd.Series) -> None:
    st.markdown(
        f"""
        <div class="detail-title">{safe_text(row.get("nome_exibicao"))}</div>
        <div class="detail-subtitle">
            {safe_text(row.get("decisor_exibicao"))} &middot;
            {safe_text(row.get("localizacao"))} &middot;
            Ultima interacao: {safe_text(row.get("ultima_interacao_fmt"))}
        </div>
        """,
        unsafe_allow_html=True,
    )

    render_contact_actions(row)

    st.subheader("Dados do lead")
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

    st.title("CRM Nova Uniao")
    st.caption("Leads organizados pela data da ultima_interacao.")

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
