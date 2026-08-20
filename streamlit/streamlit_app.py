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


st.set_page_config(
    page_title="CRM Nova Uniao",
    page_icon="NU",
    layout="wide",
    initial_sidebar_state="expanded",
)


def inject_styles() -> None:
    background = image_data_uri(BACKGROUND_PATH)
    st.markdown(
        f"""
        <style>
        :root {{
            --ink: #17202a;
            --muted: #65717f;
            --line: rgba(23, 32, 42, .12);
            --panel: rgba(255, 255, 255, .91);
            --panel-strong: rgba(255, 255, 255, .97);
            --green: #0f7b5c;
            --teal: #116a7b;
            --amber: #b66a00;
            --red: #b42318;
        }}

        .stApp {{
            background:
                linear-gradient(90deg, rgba(247, 250, 252, .96), rgba(247, 250, 252, .88)),
                url("{background}");
            background-size: cover;
            background-position: center;
            background-attachment: fixed;
        }}

        [data-testid="stSidebar"] {{
            background: rgba(255, 255, 255, .94);
            border-right: 1px solid var(--line);
        }}

        .block-container {{
            padding-top: 1.4rem;
            padding-bottom: 2rem;
            max-width: 1540px;
        }}

        h1, h2, h3 {{
            color: var(--ink);
            letter-spacing: 0;
        }}

        h1 {{
            font-size: 2rem;
            margin-bottom: .2rem;
        }}

        h2, h3 {{
            margin-top: .2rem;
        }}

        div[data-testid="stCaptionContainer"] {{
            color: var(--muted);
        }}

        div[data-testid="stMetric"] {{
            background: var(--panel-strong);
            border: 1px solid var(--line);
            border-radius: 8px;
            padding: .72rem .86rem;
            box-shadow: 0 10px 28px rgba(31, 41, 55, .07);
        }}

        div[data-testid="stMetricLabel"] p {{
            color: var(--muted);
            font-size: .78rem;
        }}

        div[data-testid="stMetricValue"] {{
            color: var(--ink);
            font-size: 1.45rem;
        }}

        .section {{
            background: var(--panel);
            border: 1px solid var(--line);
            border-radius: 8px;
            padding: 1rem;
            box-shadow: 0 14px 34px rgba(31, 41, 55, .08);
        }}

        .lead-title {{
            font-size: 1.35rem;
            font-weight: 760;
            color: var(--ink);
            margin-bottom: .2rem;
        }}

        .lead-subtitle {{
            color: var(--muted);
            font-size: .92rem;
            margin-bottom: .85rem;
        }}

        .pill-row {{
            display: flex;
            flex-wrap: wrap;
            gap: .42rem;
            margin: .4rem 0 1rem;
        }}

        .pill {{
            display: inline-flex;
            align-items: center;
            border-radius: 999px;
            padding: .22rem .55rem;
            font-size: .78rem;
            font-weight: 650;
            border: 1px solid rgba(15, 123, 92, .22);
            background: rgba(15, 123, 92, .08);
            color: #0b5f47;
        }}

        .pill-muted {{
            border-color: rgba(101, 113, 127, .22);
            background: rgba(101, 113, 127, .08);
            color: #53606d;
        }}

        .pill-hot {{
            border-color: rgba(180, 35, 24, .18);
            background: rgba(180, 35, 24, .08);
            color: var(--red);
        }}

        .pill-warm {{
            border-color: rgba(182, 106, 0, .2);
            background: rgba(182, 106, 0, .09);
            color: var(--amber);
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
            font-size: .94rem;
            word-break: break-word;
            margin-bottom: .72rem;
        }}

        .small-note {{
            color: var(--muted);
            font-size: .84rem;
        }}

        .stDataFrame {{
            border: 1px solid var(--line);
            border-radius: 8px;
            overflow: hidden;
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


def image_data_uri(path: Path) -> str:
    if not path.exists():
        return ""
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:image/png;base64,{encoded}"


def digits_only(value: Any) -> str:
    return re.sub(r"\D+", "", clean_text(value, ""))


def normalize_phone(row: pd.Series) -> str:
    phone = digits_only(row.get("celular_decisor"))
    if phone:
        return phone
    phones = row.get("telefones_contato")
    if isinstance(phones, list) and phones:
        return digits_only(phones[0])
    return ""


def format_phone(phone: str) -> str:
    if not phone:
        return "-"
    if phone.startswith("55") and len(phone) >= 12:
        phone = phone[2:]
    if len(phone) == 11:
        return f"({phone[:2]}) {phone[2:7]}-{phone[7:]}"
    if len(phone) == 10:
        return f"({phone[:2]}) {phone[2:6]}-{phone[6:]}"
    return phone


def has_value(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, list):
        return len(value) > 0
    if isinstance(value, float) and pd.isna(value):
        return False
    return bool(str(value).strip())


def completeness(row: pd.Series) -> int:
    fields = [
        "empresa",
        "decisor",
        "email",
        "telefone_principal",
        "cnpj",
        "municipio",
        "uf",
        "porte",
        "capital_social",
        "anos_mercado",
        "url_instagram",
        "url_facebook",
    ]
    filled = sum(has_value(row.get(field)) for field in fields)
    return round(filled / len(fields) * 100)


def lead_score(row: pd.Series) -> int:
    score = 0
    if has_value(row.get("decisor")):
        score += 18
    if has_value(row.get("empresa")):
        score += 16
    if has_value(row.get("email")):
        score += 14
    if has_value(row.get("telefone_principal")):
        score += 20
    if has_value(row.get("cnpj")):
        score += 10
    if has_value(row.get("municipio")) and has_value(row.get("uf")):
        score += 8
    if has_value(row.get("url_instagram")) or has_value(row.get("url_facebook")):
        score += 6
    if bool(row.get("cliente_sga")) is False:
        score += 5
    if pd.notna(row.get("ultima_interacao")):
        score += 3
    return min(score, 100)


def lead_temperature(score: int) -> str:
    if score >= 72:
        return "Quente"
    if score >= 45:
        return "Morno"
    return "Frio"


def format_datetime(value: Any) -> str:
    if pd.isna(value):
        return "-"
    timestamp = pd.to_datetime(value, errors="coerce")
    if pd.isna(timestamp):
        return "-"
    return timestamp.strftime("%d/%m/%Y %H:%M")


def normalize_url(value: Any) -> str:
    url = clean_text(value, "")
    if not url:
        return ""
    if url.startswith(("http://", "https://")):
        return url
    return f"https://{url}"


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

    df["telefone_principal"] = df.apply(normalize_phone, axis=1)
    df["telefone_formatado"] = df["telefone_principal"].map(format_phone)
    df["whatsapp_url"] = df["telefone_principal"].map(whatsapp_url)
    df["email_url"] = df["email"].map(email_url)
    df["instagram_url"] = df["url_instagram"].map(normalize_url)
    df["facebook_url"] = df["url_facebook"].map(normalize_url)
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
    df["completude"] = df.apply(completeness, axis=1)
    df["score"] = df.apply(lead_score, axis=1)
    df["temperatura"] = df["score"].map(lead_temperature)
    df["ultima_interacao_fmt"] = df["ultima_interacao"].map(format_datetime)
    df["cliente_sga_fmt"] = df["cliente_sga"].map(
        lambda value: "Sim" if value is True else "Nao" if value is False else "Nao informado"
    )
    return df


def sidebar_filters(df: pd.DataFrame) -> pd.DataFrame:
    with st.sidebar:
        st.title("Nova Uniao CRM")
        st.caption("Prospecao marketing")
        st.divider()

        search = st.text_input("Buscar lead", placeholder="Empresa, decisor, email, CNPJ")
        temperatures = st.multiselect(
            "Prioridade",
            options=["Quente", "Morno", "Frio"],
            default=["Quente", "Morno", "Frio"],
        )
        ufs = sorted(value for value in df["uf"].dropna().unique() if str(value).strip())
        selected_ufs = st.multiselect("UF", options=ufs)
        sga_options = st.multiselect(
            "Cliente SGA",
            options=["Sim", "Nao", "Nao informado"],
            default=["Sim", "Nao", "Nao informado"],
        )
        contact = st.radio(
            "Contato disponivel",
            options=["Todos", "Com telefone", "Com email", "Telefone e email"],
            horizontal=False,
        )

        st.divider()
        if st.button("Atualizar dados", width="stretch"):
            st.cache_data.clear()
            st.rerun()

    filtered = df.copy()
    if search:
        terms = search.strip().lower()
        haystack = (
            filtered[
                ["nome_exibicao", "decisor_exibicao", "email", "cnpj", "telefone_principal"]
            ]
            .fillna("")
            .astype(str)
            .agg(" ".join, axis=1)
            .str.lower()
        )
        filtered = filtered[haystack.str.contains(re.escape(terms), na=False)]
    if temperatures:
        filtered = filtered[filtered["temperatura"].isin(temperatures)]
    if selected_ufs:
        filtered = filtered[filtered["uf"].isin(selected_ufs)]
    if sga_options:
        filtered = filtered[filtered["cliente_sga_fmt"].isin(sga_options)]
    if contact == "Com telefone":
        filtered = filtered[filtered["telefone_principal"].astype(bool)]
    elif contact == "Com email":
        filtered = filtered[filtered["email"].fillna("").astype(str).str.strip().astype(bool)]
    elif contact == "Telefone e email":
        filtered = filtered[
            filtered["telefone_principal"].astype(bool)
            & filtered["email"].fillna("").astype(str).str.strip().astype(bool)
        ]
    return filtered


def render_metrics(df: pd.DataFrame) -> None:
    total = len(df)
    with_phone = int(df["telefone_principal"].astype(bool).sum()) if total else 0
    with_company = int(df["empresa"].fillna("").astype(str).str.strip().astype(bool).sum()) if total else 0
    hot = int((df["temperatura"] == "Quente").sum()) if total else 0
    cols = st.columns(4)
    cols[0].metric("Leads filtrados", f"{total:,}".replace(",", "."))
    cols[1].metric("Com telefone", f"{with_phone:,}".replace(",", "."))
    cols[2].metric("Com empresa", f"{with_company:,}".replace(",", "."))
    cols[3].metric("Prioridade quente", f"{hot:,}".replace(",", "."))


def render_lead_detail(row: pd.Series) -> None:
    score = int(row.get("score", 0))
    temperature = clean_text(row.get("temperatura"))
    pill_class = "pill-hot" if temperature == "Quente" else "pill-warm" if temperature == "Morno" else "pill-muted"

    st.markdown('<div class="section">', unsafe_allow_html=True)
    st.markdown(
        f"""
        <div class="lead-title">{safe_text(row.get("nome_exibicao"))}</div>
        <div class="lead-subtitle">{safe_text(row.get("decisor_exibicao"))} &middot; {safe_text(row.get("localizacao"))}</div>
        <div class="pill-row">
            <span class="pill {pill_class}">{safe_text(temperature)} &middot; {score}/100</span>
            <span class="pill">Cadastro {int(row.get("completude", 0))}%</span>
            <span class="pill pill-muted">SGA: {safe_text(row.get("cliente_sga_fmt"))}</span>
            <span class="pill pill-muted">Ultima interacao: {safe_text(row.get("ultima_interacao_fmt"))}</span>
        </div>
        """,
        unsafe_allow_html=True,
    )

    c1, c2, c3 = st.columns([1.1, 1, 1])
    with c1:
        field("Email", clean_text(row.get("email")))
        field("Telefone", clean_text(row.get("telefone_formatado")))
        field("CNPJ", clean_text(row.get("cnpj")))
    with c2:
        field("Municipio / UF", clean_text(row.get("localizacao")))
        field("Endereco", clean_text(row.get("endereco")))
        field("Natureza juridica", clean_text(row.get("natureza_juridica")))
    with c3:
        field("Porte", clean_text(row.get("porte")))
        field("Capital social", clean_text(row.get("capital_social")))
        field("Anos de mercado", clean_text(row.get("anos_mercado")))

    st.markdown("**Acoes rapidas**")
    a1, a2, a3, a4 = st.columns(4)
    email = clean_text(row.get("email_url"), "")
    phone = clean_text(row.get("whatsapp_url"), "")
    instagram = clean_text(row.get("instagram_url"), "")
    facebook = clean_text(row.get("facebook_url"), "")

    if phone:
        a1.link_button("WhatsApp", phone, width="stretch")
    else:
        a1.button("WhatsApp", disabled=True, width="stretch")
    if email:
        a2.link_button("Email", email, width="stretch")
    else:
        a2.button("Email", disabled=True, width="stretch")
    if instagram:
        a3.link_button("Instagram", instagram, width="stretch")
    else:
        a3.button("Instagram", disabled=True, width="stretch")
    if facebook:
        a4.link_button("Facebook", facebook, width="stretch")
    else:
        a4.button("Facebook", disabled=True, width="stretch")

    st.markdown("</div>", unsafe_allow_html=True)


def field(label: str, value: str) -> None:
    st.markdown(
        f"""
        <div class="field-label">{safe_text(label)}</div>
        <div class="field-value">{safe_text(value)}</div>
        """,
        unsafe_allow_html=True,
    )


def render_table(df: pd.DataFrame) -> None:
    table = df[
        [
            "temperatura",
            "score",
            "nome_exibicao",
            "decisor_exibicao",
            "telefone_formatado",
            "whatsapp_url",
            "email_url",
            "instagram_url",
            "facebook_url",
            "localizacao",
            "cliente_sga_fmt",
            "ultima_interacao_fmt",
        ]
    ].rename(
        columns={
            "temperatura": "Prioridade",
            "score": "Score",
            "nome_exibicao": "Empresa / Lead",
            "decisor_exibicao": "Decisor",
            "telefone_formatado": "Telefone",
            "whatsapp_url": "WhatsApp",
            "email_url": "Email",
            "instagram_url": "Instagram",
            "facebook_url": "Facebook",
            "localizacao": "Localizacao",
            "cliente_sga_fmt": "Cliente SGA",
            "ultima_interacao_fmt": "Ultima interacao",
        }
    )
    st.dataframe(
        table,
        width="stretch",
        hide_index=True,
        column_config={
            "Prioridade": st.column_config.TextColumn("Prioridade", width="small"),
            "Score": st.column_config.ProgressColumn(
                "Score",
                min_value=0,
                max_value=100,
                format="%d",
                width="small",
            ),
            "Empresa / Lead": st.column_config.TextColumn("Empresa / Lead", width="medium"),
            "Decisor": st.column_config.TextColumn("Decisor", width="medium"),
            "Telefone": st.column_config.TextColumn("Telefone", width="small"),
            "WhatsApp": st.column_config.LinkColumn("WhatsApp", display_text="Abrir", width="small"),
            "Email": st.column_config.LinkColumn("Email", display_text="Enviar", width="small"),
            "Instagram": st.column_config.LinkColumn("Instagram", display_text="Abrir", width="small"),
            "Facebook": st.column_config.LinkColumn("Facebook", display_text="Abrir", width="small"),
            "Localizacao": st.column_config.TextColumn("Localizacao", width="small"),
            "Cliente SGA": st.column_config.TextColumn("Cliente SGA", width="small"),
            "Ultima interacao": st.column_config.TextColumn("Ultima interacao", width="small"),
        },
    )


def render_context_charts(df: pd.DataFrame) -> None:
    left, right = st.columns([1, 1])
    with left:
        st.markdown('<div class="section">', unsafe_allow_html=True)
        st.subheader("Distribuicao por UF")
        uf_counts = (
            df[df["uf"].fillna("").astype(str).str.strip().astype(bool)]["uf"]
            .value_counts()
            .head(12)
        )
        if uf_counts.empty:
            st.caption("Sem UF preenchida nos filtros atuais.")
        else:
            st.bar_chart(uf_counts)
        st.markdown("</div>", unsafe_allow_html=True)
    with right:
        st.markdown('<div class="section">', unsafe_allow_html=True)
        st.subheader("Qualidade dos contatos")
        quality = pd.Series(
            {
                "Telefone": int(df["telefone_principal"].astype(bool).sum()),
                "Email": int(df["email"].fillna("").astype(str).str.strip().astype(bool).sum()),
                "CNPJ": int(df["cnpj"].fillna("").astype(str).str.strip().astype(bool).sum()),
                "Rede social": int(
                    (
                        df["url_instagram"].fillna("").astype(str).str.strip().astype(bool)
                        | df["url_facebook"].fillna("").astype(str).str.strip().astype(bool)
                    ).sum()
                ),
            }
        )
        st.bar_chart(quality)
        st.markdown("</div>", unsafe_allow_html=True)


def main() -> None:
    inject_styles()
    with st.spinner("Carregando leads do Supabase..."):
        df = load_leads()

    st.title("Mini CRM Nova Uniao")
    st.caption("Leads da tabela clientes_novauniao.prospecao_mkt")

    if df.empty:
        st.warning("Nenhum lead encontrado na tabela.")
        return

    filtered = sidebar_filters(df)
    render_metrics(filtered)

    if filtered.empty:
        st.warning("Nenhum lead encontrado com os filtros atuais.")
        return

    lead_options = filtered["lead_key"].astype(str).tolist()
    label_map = {
        str(row.lead_key): f"{row.nome_exibicao} - {row.decisor_exibicao} - {row.temperatura}"
        for row in filtered.itertuples()
    }

    main_col, detail_col = st.columns([1.28, 1], gap="large")
    with main_col:
        st.markdown('<div class="section">', unsafe_allow_html=True)
        st.subheader("Carteira de leads")
        selected_key = st.selectbox(
            "Lead em foco",
            options=lead_options,
            format_func=lambda key: label_map.get(key, key),
            label_visibility="collapsed",
        )
        render_table(filtered)
        st.markdown("</div>", unsafe_allow_html=True)

    selected_row = filtered[filtered["lead_key"].astype(str) == selected_key].iloc[0]
    with detail_col:
        render_lead_detail(selected_row)

    st.write("")
    render_context_charts(filtered)


if __name__ == "__main__":
    main()
