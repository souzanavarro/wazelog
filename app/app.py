import sys
import os
import streamlit as st
import pandas as pd
import requests
sys.dont_write_bytecode = True

st.set_page_config(page_title="Wazelog", layout="wide")

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from database import init_db
init_db()

from dashboard_page import show as show_dashboard
from frota_page import show as show_frota
from pedidos_page import show as show_pedidos
from roteirizacao_page import show as show_roteirizacao
from mapas_page import show as show_mapas
from cnpj_page import show as show_cnpj

# --- Toggle de tema ---
# Remover título e centralizar layout do menu
with st.sidebar:
    st.markdown("""
        <style>
        .stSidebar, section[data-testid="stSidebar"] {
            display: flex;
            flex-direction: column;
            align-items: center;
        }
        .menu-title {display: none !important;}
        </style>
    """, unsafe_allow_html=True)
    theme_mode = st.radio('', options=['🌞 Claro', '🌙 Escuro'], horizontal=True, key='theme_mode')

# --- CSS para tema light e dark com vermelho Streamlit ---
streamlit_red = "#FF4B4B"
streamlit_red_dark = "#c62828"
streamlit_accent_hover = "#D32F2F" # Um vermelho um pouco mais escuro para hover

if theme_mode == '🌞 Claro':
    st.markdown(f'''
    <style>
    body, .stApp {{
      font-family: 'Inter', 'Roboto', sans-serif;
      background: transparent !important;
      color: #1f1f1f !important;
    }}
    .stSidebar, section[data-testid="stSidebar"] {{
      background: #ffffff !important;
      color: #1f1f1f !important;
      border-radius: 16px; /* Consistente com cards */
      border-right: 1px solid #e0e0e0;
      box-shadow: 0 2px 10px rgba(0,0,0,0.05);
    }}
    .menu-title {{
      font-size: 1.4rem; /* Um pouco maior */
      font-weight: 700;
      color: {streamlit_red};
      margin-bottom: 1.8rem;
      letter-spacing: 0.5px;
      text-align: left;
    }}
    .menu-btn {{
      display: flex;
      align-items: center;
      gap: 0.8rem; /* Ajuste no gap */
      background: transparent;
      color: #333;
      border: none;
      border-radius: 12px; /* Mais arredondado */
      font-size: 1.05rem; /* Levemente maior */
      font-weight: 500;
      padding: 0.8rem 1.1rem; /* Ajuste no padding */
      margin-bottom: 0.4rem;
      transition: background 0.2s ease-in-out, color 0.2s ease-in-out, box-shadow 0.2s ease-in-out;
      cursor: pointer;
      /* box-shadow: 0 1px 3px rgba(0,0,0,0.04); Removido para um look mais flat inicial */
    }}
    .menu-btn.selected, .menu-btn:hover {{
      background: {streamlit_red}1A; /* Vermelho com baixa opacidade */
      color: {streamlit_red};
      font-weight: 600;
      /* box-shadow: 0 2px 8px rgba(255,75,75,0.12); Sombra sutil no hover/selected */
    }}
    .menu-btn .icon {{
      font-size: 1.4rem;
      margin-right: 0.3rem;
    }}
    .menu-divider {{
      height: 1.5px; /* Mais sutil */
      background: #e0e0e0; /* Cinza claro */
      margin: 1.5rem 0.5rem; /* Margem horizontal para não tocar as bordas */
      border: none;
    }}
    .cardbox {{
      background: #ffffff;
      border-radius: 16px; /* Cantos mais arredondados */
      box-shadow: 0 5px 15px rgba(0,0,0,0.07); /* Sombra mais suave e moderna */
      padding: 1.5rem 1.8rem;
      margin: 1.5rem 0 2rem 0;
      color: #1f1f1f;
      transition: box-shadow 0.2s ease-in-out, transform 0.2s ease-in-out;
      border: 1px solid #e9e9e9; /* Borda sutil */
    }}
    .cardbox:hover {{
      box-shadow: 0 8px 25px rgba(0,0,0,0.1);
      transform: translateY(-3px); /* Efeito de elevação */
    }}
    .kpi {{
      font-size: 2.3rem;
      font-weight: 700; /* Mais leve que 800 */
      color: {streamlit_red};
      margin-top: 0.5rem; /* Adiciona um pouco de espaço acima do número do KPI */
    }}
    .kpi-title {{
        font-size: 1.1rem;
        font-weight: 600;
        color: #333;
        margin-bottom: 0.2rem;
    }}
    .stButton>button, .stDownloadButton>button {{
      border-radius: 12px;
      font-weight: 600;
      font-size: 1rem;
      min-height: 44px;
      height: 44px;
      padding: 0 1.4rem;
      background: #ffffff;
      color: #333333;
      border: 1px solid #d0d0d0;
      box-shadow: 0 2px 5px rgba(0,0,0,0.08);
      transition: background 0.2s, box-shadow 0.2s, transform 0.2s, border-color 0.2s;
      display: flex;
      align-items: center;
      gap: 0.6rem;
    }}
    .stButton>button:hover, .stDownloadButton>button:hover {{
      background: #f5f5f5;
      color: #111111;
      border-color: #c0c0c0;
      box-shadow: 0 3px 8px rgba(0,0,0,0.12);
      transform: translateY(-1px);
    }}
    .stButton>button:active, .stDownloadButton>button:active {{
        transform: translateY(0px);
        background: #e9e9e9;
        box-shadow: 0 1px 3px rgba(0,0,0,0.1);
    }}
    .stButton.secondary>button {{
        background: #f0f0f0;
        color: #333;
        border-color: #d0d0d0;
        box-shadow: 0 2px 5px rgba(0,0,0,0.07);
        min-height: 44px;
        height: 44px;
    }}
    .stButton.secondary>button:hover {{
        background: #e5e5e5;
        color: #111;
        border-color: #c0c0c0;
        box-shadow: 0 3px 8px rgba(0,0,0,0.1);
    }}

    /* Estilo para st.download_button */
    .stDownloadButton>button {{
        border-radius: 12px !important;
        font-weight: 600 !important;
        font-size: 1rem !important;
        padding: 0.65rem 1.35rem !important;
        background: #f9f9f9 !important; /* Quase branco */
        color: #555555 !important; /* Texto um pouco mais claro que o primário */
        border: 1px solid #dcdcdc !important;
        box-shadow: 0 2px 4px rgba(0,0,0,0.06) !important;
        transition: background 0.2s ease-in-out, box-shadow 0.2s ease-in-out, transform 0.2s ease-in-out, border-color 0.2s ease-in-out !important;
    }}
    .stDownloadButton>button:hover {{
        background: #efefef !important;
        color: #333333 !important;
        border-color: #c0c0c0 !important;
        box-shadow: 0 3px 7px rgba(0,0,0,0.1) !important;
        transform: translateY(-1px) !important;
    }}
    .stDownloadButton>button:active {{
        transform: translateY(0px) !important;
        background: #e5e5e5 !important;
        box-shadow: 0 1px 2px rgba(0,0,0,0.08) !important;
    }}

    /* Estilos para Inputs e Selectbox */
    div[data-testid="stTextInput"] input,
    div[data-testid="stNumberInput"] input,
    div[data-testid="stTextArea"] textarea,
    div[data-testid="stSelectbox"] div[data-baseweb="select"] > div {{
        background-color: #ffffff !important;
        color: #333333 !important;
        border: 1px solid #d0d0d0 !important;
        border-radius: 8px !important; /* Cantos um pouco menos arredondados que botões */
        box-shadow: 0 1px 3px rgba(0,0,0,0.05) !important;
    }}
    div[data-testid="stTextInput"] input:focus,
    div[data-testid="stNumberInput"] input:focus,
    div[data-testid="stTextArea"] textarea:focus,
    div[data-testid="stSelectbox"] div[data-baseweb="select"] > div:focus-within {{
        border-color: #FF4B4B !important; /* Destaque vermelho no foco */
        box-shadow: 0 0 0 2px rgba(255, 75, 75, 0.2) !important;
    }}
    div[data-baseweb="select"] .css-1u9des2-indicatorSeparator {{
        background-color: #fff !important;
    }}
    div[data-baseweb="select"] .css-1dimb5e-singleValue {{
        color: #333 !important;
    }}
    div[data-baseweb="select"] .css-1n7v3ny-option {{
        background-color: #fff !important;
        color: #333 !important;
    }}
    div[data-baseweb="select"] .css-9gakcf-option {{
        background-color: #f5f5f5 !important;
        color: #333 !important;
    }}
    /* Placeholder text color */
    div[data-testid="stTextInput"] input::placeholder,
    div[data-testid="stTextArea"] textarea::placeholder {{
        color: #888888 !important;
    }}

    .stMarkdown p {{
        margin-bottom: 0.8rem;
        line-height: 1.7;
    }}
    .stMarkdown li {{
        margin-bottom: 0.5rem;
        line-height: 1.7;
    }}
    .page-subtitle {{
      font-size: 1.1rem; /* Um pouco maior */
      color: #4f4f4f; /* Mais escuro para melhor contraste */
      margin-bottom: 1.5rem;
      line-height: 1.65;
    }}

    /* Estilização de Tabelas Streamlit (st.dataframe / st.table) */
    .stDataFrame, .stTable {{
        width: 100%;
        border-collapse: collapse;
        border-radius: 12px; /* Cantos arredondados para o container da tabela */
        box-shadow: 0 3px 10px rgba(0,0,0,0.05);
        overflow: hidden; /* Para que o border-radius funcione nos cantos */
        border: 1px solid #e0e0e0;
    }}
    .stDataFrame thead th, .stTable thead th {{
        background-color: #f7f7f7; /* Fundo do cabeçalho mais claro */
        color: #333;
        font-weight: 600;
        padding: 0.9rem 1rem; /* Mais padding */
        text-align: left;
        border-bottom: 2px solid #d0d0d0; /* Linha mais forte abaixo do cabeçalho */
    }}
    .stDataFrame tbody tr:nth-child(even), .stTable tbody tr:nth-child(even) {{
        background-color: #fafafa; /* Zebrado sutil */
    }}
    .stDataFrame tbody tr:hover, .stTable tbody tr:hover {{
        background-color: #f0f0f0; /* Hover nas linhas */
    }}
    .stDataFrame tbody td, .stTable tbody td {{
        padding: 0.8rem 1rem; /* Mais padding */
        border-bottom: 1px solid #e9e9e9; /* Linhas de célula mais sutis */
        color: #2f2f2f;
    }}
    .stDataFrame tbody tr:last-child td, .stTable tbody tr:last-child td {{
        border-bottom: none; /* Remove a borda da última linha */
    }}

    /* Aplicar estilo de card aos st.container(border=True) */
    div[data-testid="stVerticalBlock"] > div[data-testid="stVerticalBlockBorderWrapper"] > div[data-testid="stVerticalBlockContainer"] {{
      background: #ffffff !important;
      border-radius: 16px !important;
      box-shadow: 0 5px 15px rgba(0,0,0,0.07) !important;
      padding: 1.5rem 1.8rem !important;
      color: #1f1f1f !important;
      transition: box-shadow 0.2s ease-in-out, transform 0.2s ease-in-out !important;
      border: 1px solid #e9e9e9 !important;
    }}
    /* Estilo para card flutuante */
    .wrapper-for-floating-card > div[data-testid="stVerticalBlock"] > div[data-testid="stVerticalBlockBorderWrapper"] > div[data-testid="stVerticalBlockContainer"] {{
        box-shadow: 0 10px 25px rgba(0,0,0,0.12) !important;
        transform: translateY(-5px) !important;
    }}
    .wrapper-for-floating-card > div[data-testid="stVerticalBlock"] > div[data-testid="stVerticalBlockBorderWrapper"] > div[data-testid="stVerticalBlockContainer"]:hover {{
        box-shadow: 0 12px 30px rgba(0,0,0,0.15) !important;
        transform: translateY(-7px) !important;
    }}
    div[data-testid="stVerticalBlock"] > div[data-testid="stVerticalBlockBorderWrapper"] > div[data-testid="stVerticalBlockContainer"]:hover {{
      box-shadow: 0 8px 25px rgba(0,0,0,0.1) !important;
      transform: translateY(-3px) !important;
    }}
    /* Remover a borda e sombra padrão que o Streamlit adiciona ao wrapper do container com borda */
    div[data-testid="stVerticalBlock"] > div[data-testid="stVerticalBlockBorderWrapper"] {{
        border: none !important;
        box-shadow: none !important;
        border-radius: 16px !important; /* Para garantir que o hover/transform não corte */
        overflow: visible !important; /* Para garantir que a sombra do conteúdo não seja cortada */
        margin: 1.5rem 0 2rem 0 !important; /* Aplicar a margem do card aqui */
    }}

    @media (max-width: 600px) {{
      .cardbox {{ padding: 1.2rem; margin: 1rem 0 1.5rem 0; }}
      .menu-title {{ font-size: 1.2rem; }}
      .kpi {{ font-size: 1.8rem; }}
      .stButton>button {{ padding: 0.6rem 1.2rem; font-size: 0.95rem; }}
      .page-subtitle {{ font-size: 1rem; }}
      .stDataFrame thead th, .stTable thead th {{ padding: 0.7rem 0.8rem; font-size: 0.9rem; }}
      .stDataFrame tbody td, .stTable tbody td {{ padding: 0.7rem 0.8rem; font-size: 0.9rem; }}
    }}
    </style>
    ''', unsafe_allow_html=True)
else: # Tema Escuro
    st.markdown(f'''
    <style>
    body, .stApp {{
      font-family: 'Inter', 'Roboto', sans-serif;
      background: #181818 !important;
      color: #e0e0e0 !important;
    }}
    .stSidebar, section[data-testid="stSidebar"] {{
      background: #2a2a2a !important; /* Fundo da sidebar um pouco mais claro */
      color: #e0e0e0 !important;
      border-radius: 16px;
      border-right: 1px solid #3a3a3a;
      box-shadow: 0 2px 10px rgba(255,75,75,0.07); /* Sombra com cor de destaque sutil */
    }}
    .menu-title {{
      font-size: 1.4rem;
      font-weight: 700;
      color: {streamlit_red};
      margin-bottom: 1.8rem;
      letter-spacing: 0.5px;
      text-align: left;
    }}
    .menu-btn {{
      display: flex;
      align-items: center;
      gap: 0.8rem;
      background: transparent;
      color: #c5c5c5; /* Cor de texto do menu mais clara */
      border: none;
      border-radius: 12px;
      font-size: 1.05rem;
      font-weight: 500;
      padding: 0.8rem 1.1rem;
      margin-bottom: 0.4rem;
      transition: background 0.2s ease-in-out, color 0.2s ease-in-out, box-shadow 0.2s ease-in-out;
      cursor: pointer;
    }}
    .menu-btn.selected, .menu-btn:hover {{
      background: {streamlit_red}33; /* Vermelho com maior opacidade para tema escuro */
      color: {streamlit_red};
      font-weight: 600;
    }}
    .menu-btn .icon {{
      font-size: 1.4rem;
      margin-right: 0.3rem;
    }}
    .menu-divider {{
      height: 1.5px;
      background: #444; /* Divisor mais escuro */
      margin: 1.5rem 0.5rem;
      border: none;
    }}
    .cardbox {{
      background: #2c2c2c; /* Cor de card para tema escuro */
      border-radius: 16px;
      box-shadow: 0 5px 15px rgba(0,0,0,0.25); /* Sombra mais adaptada ao escuro */
      padding: 1.5rem 1.8rem;
      margin: 1.5rem 0 2rem 0;
      color: #e0e0e0;
      transition: box-shadow 0.2s ease-in-out, transform 0.2s ease-in-out;
      border: 1px solid #3f3f3f; /* Borda sutil para tema escuro */
    }}
    .cardbox:hover {{
      box-shadow: 0 8px 25px rgba(0,0,0,0.35);
      transform: translateY(-3px);
    }}
    .kpi {{
      font-size: 2.3rem;
      font-weight: 700;
      color: {streamlit_red};
      margin-top: 0.5rem;
    }}
    .kpi-title {{
        font-size: 1.1rem;
        font-weight: 600;
        color: #e0e0e0; /* Cor clara para tema escuro */
        margin-bottom: 0.2rem;
    }}
    .stButton>button, .stDownloadButton>button {{
      border-radius: 12px;
      font-weight: 600;
      font-size: 1rem;
      min-height: 44px;
      height: 44px;
      padding: 0 1.4rem;
      background: #383838;
      color: #e0e0e0;
      border: 1px solid #505050;
      box-shadow: 0 2px 5px rgba(0,0,0,0.25);
      transition: background 0.2s, box-shadow 0.2s, transform 0.2s, border-color 0.2s;
      display: flex;
      align-items: center;
      gap: 0.6rem;
    }}
    .stButton>button:hover, .stDownloadButton>button:hover {{
      background: #424242;
      color: #ffffff;
      border-color: #606060;
      box-shadow: 0 3px 8px rgba(0,0,0,0.3);
      transform: translateY(-1px);
    }}
    .stButton>button:active, .stDownloadButton>button:active {{
        transform: translateY(0px);
        background: #2c2c2c;
        box-shadow: 0 1px 3px rgba(0,0,0,0.28);
    }}
    .stButton.secondary>button {{
        background: #303030;
        color: #e0e0e0;
        border-color: #484848;
        box-shadow: 0 2px 5px rgba(0,0,0,0.22);
        min-height: 44px;
        height: 44px;
    }}
    .stButton.secondary>button:hover {{
        background: #3a3a3a;
        color: #ffffff;
        border-color: #585858;
        box-shadow: 0 3px 8px rgba(0,0,0,0.28);
    }}

    /* Estilos para Inputs e Selectbox - Tema Escuro */
    div[data-testid="stTextInput"] input,
    div[data-testid="stNumberInput"] input,
    div[data-testid="stTextArea"] textarea,
    div[data-testid="stSelectbox"] div[data-baseweb="select"] > div {{
        background-color: #383838 !important; /* Cinza escuro, mas mais claro que o fundo do card */
        color: #e0e0e0 !important;
        border: 1px solid #505050 !important;
        border-radius: 8px !important;
        box-shadow: 0 1px 3px rgba(0,0,0,0.2) !important;
    }}
    div[data-testid="stTextInput"] input:focus,
    div[data-testid="stNumberInput"] input:focus,
    div[data-testid="stTextArea"] textarea:focus,
    div[data-testid="stSelectbox"] div[data-baseweb="select"] > div:focus-within {{
        border-color: #FF4B4B !important;
        box-shadow: 0 0 0 2px rgba(255, 75, 75, 0.3) !important;
    }}
    div[data-baseweb="select"] .css-1u9des2-indicatorSeparator {{
        background-color: #383838 !important;
    }}
    div[data-baseweb="select"] .css-1dimb5e-singleValue {{
        color: #e0e0e0 !important;
    }}
    div[data-baseweb="select"] .css-1n7v3ny-option {{
        background-color: #383838 !important;
        color: #e0e0e0 !important;
    }}
    div[data-baseweb="select"] .css-9gakcf-option {{
        background-color: #424242 !important;
        color: #e0e0e0 !important;
    }}
    /* Placeholder text color - Tema Escuro */
    div[data-testid="stTextInput"] input::placeholder,
    div[data-testid="stTextArea"] textarea::placeholder {{
        color: #a0a0a0 !important;
    }}

    .stMarkdown p {{
        margin-bottom: 0.8rem;
        line-height: 1.7;
    }}
    .stMarkdown li {{
        margin-bottom: 0.5rem;
        line-height: 1.7;
    }}
    .page-subtitle {{
      font-size: 1.1rem;
      color: #b0b0b0; /* Cinza claro para subtítulo no tema escuro */
      margin-bottom: 1.5rem;
      line-height: 1.65;
    }}

    /* Estilização de Tabelas Streamlit (st.dataframe / st.table) - Tema Escuro */
    .stDataFrame, .stTable {{
        width: 100%;
        border-collapse: collapse;
        border-radius: 12px;
        box-shadow: 0 3px 10px rgba(0,0,0,0.2);
        overflow: hidden;
        border: 1px solid #4a4a4a;
    }}
    .stDataFrame thead th, .stTable thead th {{
        background-color: #383838; /* Fundo do cabeçalho escuro */
        color: #e0e0e0;
        font-weight: 600;
        padding: 0.9rem 1rem;
        text-align: left;
        border-bottom: 2px solid #505050;
    }}
    .stDataFrame tbody tr:nth-child(even), .stTable tbody tr:nth-child(even) {{
        background-color: #2f2f2f; /* Zebrado sutil escuro */
    }}
    .stDataFrame tbody tr:hover, .stTable tbody tr:hover {{
        background-color: #3a3a3a; /* Hover nas linhas escuro */
    }}
    .stDataFrame tbody td, .stTable tbody td {{
        padding: 0.8rem 1rem;
        border-bottom: 1px solid #424242;
        color: #d5d5d5;
    }}
    .stDataFrame tbody tr:last-child td, .stTable tbody tr:last-child td {{
        border-bottom: none; /* Remove a borda da última linha */
    }}

    /* Aplicar estilo de card aos st.container(border=True) - Tema Escuro */
    div[data-testid="stVerticalBlock"] > div[data-testid="stVerticalBlockBorderWrapper"] > div[data-testid="stVerticalBlockContainer"] {{
      background: #2c2c2c !important;
      border-radius: 16px !important;
      box-shadow: 0 5px 15px rgba(0,0,0,0.25) !important;
      padding: 1.5rem 1.8rem !important;
      color: #e0e0e0 !important;
      transition: box-shadow 0.2s ease-in-out, transform 0.2s ease-in-out !important;
      border: 1px solid #3f3f3f !important;
    }}
    /* Estilo para card flutuante - Tema Escuro */
    .wrapper-for-floating-card > div[data-testid="stVerticalBlock"] > div[data-testid="stVerticalBlockBorderWrapper"] > div[data-testid="stVerticalBlockContainer"] {{
        box-shadow: 0 10px 25px rgba(0,0,0,0.35) !important;
        transform: translateY(-5px) !important;
    }}
    .wrapper-for-floating-card > div[data-testid="stVerticalBlock"] > div[data-testid="stVerticalBlockBorderWrapper"] > div[data-testid="stVerticalBlockContainer"]:hover {{
        box-shadow: 0 12px 30px rgba(0,0,0,0.4) !important;
        transform: translateY(-7px) !important;
    }}
    div[data-testid="stVerticalBlock"] > div[data-testid="stVerticalBlockBorderWrapper"] > div[data-testid="stVerticalBlockContainer"]:hover {{
      box-shadow: 0 8px 25px rgba(0,0,0,0.35) !important;
      transform: translateY(-3px) !important;
    }}
    /* Remover a borda e sombra padrão que o Streamlit adiciona ao wrapper - Tema Escuro */
    div[data-testid="stVerticalBlock"] > div[data-testid="stVerticalBlockBorderWrapper"] {{
        border: none !important;
        box-shadow: none !important;
        border-radius: 16px !important;
        overflow: visible !important;
        margin: 1.5rem 0 2rem 0 !important; /* Aplicar a margem do card aqui */
    }}

    @media (max-width: 600px) {{
      .cardbox {{ padding: 1.2rem; margin: 1rem 0 1.5rem 0; }}
      .menu-title {{ font-size: 1.2rem; }}
      .kpi {{ font-size: 1.8rem; }}
      .stButton>button {{ padding: 0.6rem 1.2rem; font-size: 0.95rem; }}
      .page-subtitle {{ font-size: 1rem; }}
      .stDataFrame thead th, .stTable thead th {{ padding: 0.7rem 0.8rem; font-size: 0.9rem; }}
      .stDataFrame tbody td, .stTable tbody td {{ padding: 0.7rem 0.8rem; font-size: 0.9rem; }}
    }}
    </style>
    ''', unsafe_allow_html=True)

# --- Menu lateral minimalista com ícones ---
menu_itens = [
    ("Dashboard", "🏠"),
    ("Frota", "🚚"),
    ("Pedidos", "📦"),
    ("Roteirização", "🗺️"),
    ("Mapas", "🗾"),
    ("Busca CNPJ", "🔎")
]

with st.sidebar:
    pagina = st.session_state.get('pagina_selecionada', 'Dashboard')
    for nome, icone in menu_itens:
        selected = pagina == nome
        btn = st.button(f"{icone}  {nome}", key=f"menu_{nome}", use_container_width=True)
        if btn:
            st.session_state['pagina_selecionada'] = nome
            st.rerun()
    st.markdown("<hr class='menu-divider'>", unsafe_allow_html=True)

# --- Renderização das páginas ---
pagina = st.session_state.get('pagina_selecionada', 'Dashboard')
if pagina == "Dashboard":
    show_dashboard()
elif pagina == "Frota":
    show_frota()
elif pagina == "Pedidos":
    show_pedidos()
elif pagina == "Roteirização":
    show_roteirizacao()
elif pagina == "Mapas":
    show_mapas()
elif pagina == "Busca CNPJ":
    show_cnpj()
else:
    show_dashboard()
