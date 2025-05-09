import streamlit as st
import pandas as pd
import plotly.express as px

def show():
    st.header("Dashboard de Indicadores", divider="rainbow")
    st.markdown("<div class='page-subtitle'>Acompanhe os principais indicadores das últimas roteirizações.</div>", unsafe_allow_html=True)
    # KPIs Gerais da Frota e Pedidos
    from database import carregar_frota, carregar_pedidos
    import numpy as np
    # Frota
    df_frota = carregar_frota()
    if not df_frota.empty:
        # Garante colunas
        if 'Disponível' not in df_frota.columns:
            df_frota['Disponível'] = True
        if 'Em Manutenção' not in df_frota.columns:
            df_frota['Em Manutenção'] = False
        if 'Capacidade (Kg)' not in df_frota.columns:
            df_frota['Capacidade (Kg)'] = 0
        if 'Capacidade (Cx)' not in df_frota.columns:
            df_frota['Capacidade (Cx)'] = 0
        total_veiculos = len(df_frota)
        ativos = ((df_frota['Disponível'] == True) & (df_frota['Em Manutenção'] == False)).sum()
        df_ativos = df_frota[(df_frota['Disponível'] == True) & (df_frota['Em Manutenção'] == False)]
        cap_kg_total = df_frota['Capacidade (Kg)'].sum()
        cap_kg_ativos = df_ativos['Capacidade (Kg)'].sum()
        cap_cx_total = df_frota['Capacidade (Cx)'].sum()
        cap_cx_ativos = df_ativos['Capacidade (Cx)'].sum()
    else:
        total_veiculos = ativos = cap_kg_total = cap_kg_ativos = cap_cx_total = cap_cx_ativos = 0

    # Pedidos
    df_pedidos = carregar_pedidos()
    if not df_pedidos.empty:
        total_pedidos = len(df_pedidos)
        pedidos_com_coord = df_pedidos.dropna(subset=["Latitude", "Longitude"]).shape[0] if 'Latitude' in df_pedidos.columns and 'Longitude' in df_pedidos.columns else 0
        peso_col = "Peso dos Itens" if "Peso dos Itens" in df_pedidos.columns else None
        peso_total = df_pedidos[peso_col].sum() if peso_col else 0
        regioes = df_pedidos['Região'].nunique() if 'Região' in df_pedidos.columns else 0
    else:
        total_pedidos = pedidos_com_coord = peso_total = regioes = 0


    # --- Custom CSS for beautiful cards ---
    st.markdown('''
    <style>
    .kpi-card {
        background: #fff;
        border-radius: 18px;
        box-shadow: 0 2px 12px 0 rgba(0,0,0,0.07);
        padding: 1.2rem 1.5rem 1.2rem 1.5rem;
        margin-bottom: 1.2rem;
        min-height: 120px;
        display: flex;
        flex-direction: column;
        align-items: flex-start;
        justify-content: center;
        border: 1.5px solid #e6e6e6;
    }
    .kpi-title {
        font-size: 1.1rem;
        font-weight: 600;
        color: #3a3a3a;
        margin-bottom: 0.2rem;
    }
    .kpi-sub {
        font-size: 0.95rem;
        color: #888;
        margin-bottom: 0.5rem;
    }
    .kpi-value {
        font-size: 2.2rem;
        font-weight: 700;
        color: #1a1a1a;
        margin-bottom: 0.1rem;
    }
    </style>
    ''', unsafe_allow_html=True)

    # KPIs - Frota
    st.subheader("Resumo da Frota", divider="gray")
    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown(f'''<div class="kpi-card">
            <div class="kpi-title">Veículos (Total / Ativos)</div>
            <div class="kpi-sub">Total / Ativos</div>
            <div class="kpi-value">{total_veiculos}/{ativos}</div>
        </div>''', unsafe_allow_html=True)
    with col2:
        st.markdown(f'''<div class="kpi-card">
            <div class="kpi-title">Capacidade Total (Kg)</div>
            <div class="kpi-sub">Total (Kg)</div>
            <div class="kpi-value">{cap_kg_total:,.0f} / {cap_kg_ativos:,.0f}</div>
        </div>''', unsafe_allow_html=True)
    with col3:
        st.markdown(f'''<div class="kpi-card">
            <div class="kpi-title">Capacidade Total (Cx)</div>
            <div class="kpi-sub">Total (Cx)</div>
            <div class="kpi-value">{cap_cx_total:,.0f} / {cap_cx_ativos:,.0f}</div>
        </div>''', unsafe_allow_html=True)

    # KPIs - Pedidos
    st.subheader("Resumo dos Pedidos", divider="gray")
    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown(f'''<div class="kpi-card">
            <div class="kpi-title">Quantidade de Pedidos</div>
            <div class="kpi-sub">Total / Coordenadas</div>
            <div class="kpi-value">{total_pedidos} / {pedidos_com_coord}</div>
        </div>''', unsafe_allow_html=True)
    with col2:
        st.markdown(f'''<div class="kpi-card">
            <div class="kpi-title">Peso Total dos Pedidos (Kg)</div>
            <div class="kpi-sub">Peso Total (Kg)</div>
            <div class="kpi-value">{peso_total:,.2f}</div>
        </div>''', unsafe_allow_html=True)
    with col3:
        st.markdown(f'''<div class="kpi-card">
            <div class="kpi-title">Regiões Distintas</div>
            <div class="kpi-sub">Total de Regiões</div>
            <div class="kpi-value">{regioes}</div>
        </div>''', unsafe_allow_html=True)

    st.divider()

    cenarios = st.session_state.get('cenarios_roteirizacao', [])
    if not cenarios:
        st.info("Nenhum cenário de roteirização calculado ainda.")
        return
    df = pd.DataFrame([
        {
            'Data': c.get('data', ''),
            'Tipo': c.get('tipo', ''),
            'Pedidos': c.get('qtd_pedidos_roteirizados', 0),
            'Veículos Usados': c.get('qtd_veiculos_utilizados', 0),
            'Veículos Disponíveis': c.get('qtd_veiculos_disponiveis', 0),
            'Distância Total (km)': c.get('distancia_total_real_m', 0) / 1000 if c.get('distancia_total_real_m') else 0,
            'Peso Empenhado (Kg)': c.get('peso_total_empenhado_kg', 0),
            'Status': c.get('status_solver', ''),
        }
        for c in cenarios
    ])
    # KPIs dos cenários (mantidos para histórico)
    col1, col2, col3 = st.columns(3)
    with col1:
        with st.container(border=True):
            st.markdown('<div class="kpi-title">Pedidos</div>', unsafe_allow_html=True)
            st.metric("Total de Pedidos", int(df['Pedidos'].sum()))
    with col2:
        with st.container(border=True):
            st.markdown('<div class="kpi-title">Veículos</div>', unsafe_allow_html=True)
            st.metric("Veículos Usados", int(df['Veículos Usados'].sum()))
    with col3:
        with st.container(border=True):
            st.markdown('<div class="kpi-title">Rotas</div>', unsafe_allow_html=True)
            st.metric("Distância Total (km)", f"{df['Distância Total (km)'].sum():,.1f}")
    
    st.divider()
    # Gráfico de evolução
    if len(df) > 1:
        with st.container(border=True):
            st.subheader("Evolução da Distância Total") # Título mais descritivo para o card
            fig = px.line(df, x='Data', y='Distância Total (km)') # Removido título do gráfico plotly
            st.plotly_chart(fig, use_container_width=True)
    # Tabela detalhada
    with st.container(border=True):
        st.subheader("Cenários Recentes")
        st.dataframe(df, use_container_width=True, hide_index=True)
