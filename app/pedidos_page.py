
import pandas as pd
import streamlit as st
from pedidos import processar_pedidos, obter_coordenadas
from database import carregar_pedidos, salvar_pedidos

st.markdown('<div style="display:flex;align-items:center;gap:1rem;margin-bottom:1.5rem;"><span style="font-size:2.5rem;">📦</span><span style="font-size:2rem;font-weight:700;">Pedidos</span></div>', unsafe_allow_html=True)
st.markdown('<div class="hero-subtitle">Importe, visualize e edite pedidos com facilidade</div>', unsafe_allow_html=True)

def show():
    st.header("Gerenciar Pedidos", divider="rainbow")
    st.markdown("<div class='page-subtitle'>Importe, visualize, edite, adicione ou remova pedidos de entrega.</div>", unsafe_allow_html=True)
   
    # --- KPIs em cards ---
    # Removido KPIs de Pedidos Importados e Pedidos com Coordenadas

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
    if 'df_pedidos' in st.session_state and not st.session_state.df_pedidos.empty:
        df_resumo = st.session_state.df_pedidos
        total_pedidos = df_resumo.shape[0]
        pedidos_com_coord = df_resumo.dropna(subset=["Latitude", "Longitude"]).shape[0] if 'Latitude' in df_resumo.columns and 'Longitude' in df_resumo.columns else 0
        col1, col2, col3 = st.columns(3)
        with col1:
            st.markdown(f'''<div class="kpi-card">
                <div class="kpi-title">Quantidade de Pedidos</div>
                <div class="kpi-sub">Total / Coordenadas</div>
                <div class="kpi-value">{total_pedidos} / {pedidos_com_coord}</div>
            </div>''', unsafe_allow_html=True)
        with col2:
            peso_col = "Peso dos Itens" if "Peso dos Itens" in df_resumo.columns else None
            peso_total = df_resumo[peso_col].sum() if peso_col else 0
            st.markdown(f'''<div class="kpi-card">
                <div class="kpi-title">Peso Total dos Pedidos (Kg)</div>
                <div class="kpi-sub">Peso Total (Kg)</div>
                <div class="kpi-value">{peso_total:,.2f}</div>
            </div>''', unsafe_allow_html=True)
        with col3:
            regioes = df_resumo['Região'].nunique() if 'Região' in df_resumo.columns else 0
            st.markdown(f'''<div class="kpi-card">
                <div class="kpi-title">Regiões Distintas</div>
                <div class="kpi-sub">Total de Regiões</div>
                <div class="kpi-value">{regioes}</div>
            </div>''', unsafe_allow_html=True)
    if 'df_pedidos' not in st.session_state:
        st.session_state.df_pedidos = pd.DataFrame()
    arquivo = st.file_uploader("Upload da planilha de pedidos", type=["xlsx", "xlsm", "csv", "json"])
    if arquivo:
        try:
            with st.spinner("Processando pedidos e buscando coordenadas, isso pode levar alguns minutos..."):
                df = processar_pedidos(arquivo)
            st.session_state.df_pedidos = df.copy()
            salvar_pedidos(df)
            st.success("Pedidos importados com sucesso!")
        except Exception as e:
            st.error(f"Erro ao processar os pedidos: {e}")
    df = st.session_state.df_pedidos
    if df.empty:
        df = carregar_pedidos()
        st.session_state.df_pedidos = df.copy()
    if not df.empty:
        # Remove coluna de janela de tempo se existir
        if 'Janela de Descarga' in df.columns:
            df = df.drop(columns=['Janela de Descarga'])
        # --- Região baseada em coordenadas (agrupamento KMeans) ---
        # Removido agrupamento automático aqui
        if 'Endereço de Entrega' in df.columns and 'Bairro de Entrega' in df.columns and 'Cidade de Entrega' in df.columns:
            df['Endereço Completo'] = df['Endereço de Entrega'].astype(str) + ', ' + df['Bairro de Entrega'].astype(str) + ', ' + df['Cidade de Entrega'].astype(str)
        if 'Latitude' not in df.columns:
            df['Latitude'] = None
        if 'Longitude' not in df.columns:
            df['Longitude'] = None
        # Filtro para ordenar a planilha por coluna
        colunas_ordenaveis = [c for c in df.columns if c != 'Janela de Descarga']
        coluna_ordem = st.selectbox("Ordenar por", colunas_ordenaveis, index=0)
        if coluna_ordem:
            df = df.sort_values(by=coluna_ordem, key=lambda x: x.astype(str)).reset_index(drop=True)
        # Filtros avançados
        if 'Região' in df.columns:
            regioes = sorted([r for r in df['Região'].dropna().unique() if r and str(r).strip() and str(r).lower() != 'nan'])
        else:
            regioes = []
        regiao_filtro = st.selectbox("Filtrar por região", ["Todas"] + regioes)
        status_filtro = st.selectbox("Status de coordenadas", ["Todos", "Com coordenadas", "Sem coordenadas"])
        df_filtrado = df.copy()
        if regiao_filtro != "Todas":
            df_filtrado = df_filtrado[df_filtrado['Região'] == regiao_filtro]
        if status_filtro == "Com coordenadas":
            df_filtrado = df_filtrado[df_filtrado['Latitude'].notnull() & df_filtrado['Longitude'].notnull()]
        elif status_filtro == "Sem coordenadas":
            df_filtrado = df_filtrado[df_filtrado['Latitude'].isnull() | df_filtrado['Longitude'].isnull()]
        # Remove filtro de janela de tempo
        filtro = st.text_input("Buscar pedidos (qualquer campo)")
        if filtro:
            filtro_lower = filtro.lower()
            df_filtrado = df_filtrado[df_filtrado.apply(lambda row: row.astype(str).str.lower().str.contains(filtro_lower).any(), axis=1)]
        # Validação visual: destacar linhas com dados faltantes
        def get_row_style(row):
            falta_lat = 'Latitude' not in row or pd.isnull(row.get('Latitude'))
            falta_lon = 'Longitude' not in row or pd.isnull(row.get('Longitude'))
            if falta_lat or falta_lon:
                return ["background-color: #fff3cd"] * len(row)
            return [""] * len(row)
        # Remove colunas de janela de tempo e tempo de serviço
        for col in ["Janela Início", "Janela Fim", "Tempo de Serviço"]:
            if col in df_filtrado.columns:
                df_filtrado = df_filtrado.drop(columns=[col])
        # Garante que CNPJ sempre estará presente no DataFrame e na tabela editável
        if "CNPJ" not in df_filtrado.columns:
            df_filtrado["CNPJ"] = ""
        colunas_editor = [c for c in df_filtrado.columns if c != 'Janela de Descarga' and c not in ["Janela Início", "Janela Fim", "Tempo de Serviço"]]
        if "CNPJ" not in colunas_editor:
            # Tenta inserir após Cód. Cliente, se existir, senão no início
            if "Cód. Cliente" in colunas_editor:
                idx = colunas_editor.index("Cód. Cliente") + 1
                colunas_editor.insert(idx, "CNPJ")
            else:
                colunas_editor.insert(0, "CNPJ")
        if "Região" in df_filtrado.columns:
            df_filtrado["Região"] = df_filtrado["Região"].astype(str)
        # Exibir apenas a planilha editável, sem duplicar visualização
        st.subheader("Editar Pedidos")
        df_editado = st.data_editor(
            df_filtrado[colunas_editor],
            num_rows="dynamic",
            use_container_width=True,
            key="pedidos_editor",
            column_config={
                "Latitude": st.column_config.NumberColumn(
                    "Latitude",
                    help="Latitude do endereço de entrega."
                ),
                "Longitude": st.column_config.NumberColumn(
                    "Longitude",
                    help="Longitude do endereço de entrega."
                ),
                "Região": st.column_config.TextColumn(
                    "Região",
                    help="Região agrupada automaticamente pelo sistema."
                ),
                "Endereço Completo": st.column_config.TextColumn(
                    "Endereço Completo",
                    help="Endereço completo gerado a partir dos campos de endereço, bairro e cidade."
                ),
            },
            column_order=colunas_editor,
            hide_index=True
        )
        if not df_editado.equals(df_filtrado):
            # Atualiza o DataFrame original com as edições feitas no filtrado
            df_update = df.copy()
            df_update.update(df_editado)
            for col in ["Janela Início", "Janela Fim", "Tempo de Serviço"]:
                if col in df_update.columns:
                    df_update = df_update.drop(columns=[col])
            st.session_state.df_pedidos = df_update.copy()
            salvar_pedidos(st.session_state.df_pedidos)
        # Botões de ação em linha
        col_btn1, col_btn2 = st.columns(2)
        with col_btn1:
            if st.button("Reprocessar Coordenadas", type="primary"):
                import time
                import requests
                with st.spinner("Reprocessando coordenadas e atualizando regiões..."):
                    df_pedidos = st.session_state.df_pedidos.copy()
                    mask_sem_coord = df_pedidos['Latitude'].isnull() | df_pedidos['Longitude'].isnull()
                    pedidos_sem_coord = df_pedidos[mask_sem_coord]
                    n = len(pedidos_sem_coord)
                    # 1. Buscar coordenadas para pedidos sem coordenadas
                    if n > 0:
                        latitudes = df_pedidos['Latitude'].tolist()
                        longitudes = df_pedidos['Longitude'].tolist()
                        progress_bar = st.progress(0, text="Buscando coordenadas...")
                        start_time = time.time()
                        for idx, (i, row) in enumerate(pedidos_sem_coord.iterrows()):
                            lat, lon = obter_coordenadas(row['Endereço Completo'])
                            latitudes[i] = lat
                            longitudes[i] = lon
                            elapsed = time.time() - start_time
                            avg = elapsed / (idx + 1)
                            remaining = int(avg * (n - (idx + 1)))
                            progress_bar.progress((idx + 1) / n, text=f"Buscando coordenadas... ({idx+1}/{n}) | Estimativa: {remaining} seg restantes")
                        df_pedidos['Latitude'] = latitudes
                        df_pedidos['Longitude'] = longitudes
                        progress_bar.empty()
                        st.success("Coordenadas reprocessadas para pedidos sem coordenadas!")
                    else:
                        st.info("Todos os pedidos já possuem coordenadas!")

                    # 2. Atualizar Região para todos os pedidos com coordenadas válidas (apenas cidade, sem complemento)
                    pedidos_validos = df_pedidos.dropna(subset=['Latitude', 'Longitude']).copy()
                    if not pedidos_validos.empty:
                        regioes = []
                        n_validos = len(pedidos_validos)
                        start_time = time.time()
                        progress_bar2 = st.progress(0, text="Atualizando regiões pelas coordenadas...")
                        import os
                        def buscar_regiao_local(lat, lon, endereco_completo=None, tol=0.0001):
                            # Busca no arquivo Coordenadas.csv por lat/lon próximos OU endereço exato
                            csv_path = os.path.join(os.path.dirname(__file__), '..', 'data', 'Coordenadas.csv')
                            if not os.path.exists(csv_path):
                                return None
                            try:
                                df_coord = pd.read_csv(csv_path, dtype=str)
                                # Busca por endereço exato se fornecido
                                if endereco_completo and 'Endereço Completo' in df_coord.columns:
                                    reg = df_coord.loc[df_coord['Endereço Completo'] == str(endereco_completo), 'Região']
                                    if not reg.empty and pd.notnull(reg.values[0]) and str(reg.values[0]).strip():
                                        return reg.values[0]
                                # Busca por latitude/longitude aproximados
                                if 'Latitude' in df_coord.columns and 'Longitude' in df_coord.columns:
                                    df_coord['Latitude'] = pd.to_numeric(df_coord['Latitude'], errors='coerce')
                                    df_coord['Longitude'] = pd.to_numeric(df_coord['Longitude'], errors='coerce')
                                    mask = (abs(df_coord['Latitude'] - lat) < tol) & (abs(df_coord['Longitude'] - lon) < tol)
                                    reg = df_coord.loc[mask, 'Região']
                                    if not reg.empty and pd.notnull(reg.values[0]) and str(reg.values[0]).strip():
                                        return reg.values[0]
                            except Exception:
                                pass
                            return None

                        def buscar_cidade_por_coordenada(lat, lon, endereco_completo=None):
                            # 1. Tenta buscar no CSV local
                            reg_local = buscar_regiao_local(lat, lon, endereco_completo)
                            if reg_local:
                                return reg_local
                            # 2. Se não achou, consulta API
                            try:
                                url = f"https://nominatim.openstreetmap.org/reverse?format=json&lat={lat}&lon={lon}&zoom=10&addressdetails=1"
                                headers = {"User-Agent": "wazelog/1.0"}
                                resp = requests.get(url, headers=headers, timeout=10)
                                if resp.status_code == 200:
                                    data = resp.json()
                                    cidade = data.get('address', {}).get('city') or \
                                             data.get('address', {}).get('town') or \
                                             data.get('address', {}).get('village') or \
                                             data.get('address', {}).get('municipality') or \
                                             data.get('address', {}).get('county')
                                    return cidade if cidade else 'Desconhecida'
                            except Exception:
                                pass
                            return 'Desconhecida'

                        for idx, row in enumerate(pedidos_validos.itertuples()):
                            endereco_completo = getattr(row, 'Endereço_Completo', None) if hasattr(row, 'Endereço_Completo') else None
                            cidade = buscar_cidade_por_coordenada(row.Latitude, row.Longitude, endereco_completo)
                            regioes.append(cidade)
                            elapsed = time.time() - start_time
                            avg = elapsed / (idx + 1)
                            remaining = int(avg * (n_validos - (idx + 1)))
                            progress_bar2.progress((idx + 1) / n_validos, text=f"Atualizando regiões... ({idx+1}/{n_validos}) | Estimativa: {remaining} seg restantes")
                        # Atualiza apenas com a cidade (não bairro, não UF)
                        df_pedidos.loc[pedidos_validos.index, 'Região'] = regioes
                        progress_bar2.empty()
                        st.success("Regiões atualizadas automaticamente pelas coordenadas (priorizando base local, depois API).")
                    else:
                        st.info("Nenhum pedido com coordenadas válidas para atualizar região.")

                    # Salva/atualiza também no data/Coordenadas.csv para todas as linhas com coordenada e região
                    from pedidos import salvar_coordenada_csv
                    pedidos_para_salvar = df_pedidos.dropna(subset=["Latitude", "Longitude"]).copy()
                    for _, row in pedidos_para_salvar.iterrows():
                        endereco = row.get("Endereço Completo", "")
                        lat = row.get("Latitude", None)
                        lon = row.get("Longitude", None)
                        regiao = row.get("Região", None)
                        if endereco and lat is not None and lon is not None:
                            salvar_coordenada_csv(None, endereco, lat, lon, regiao)

                    salvar_pedidos(df_pedidos)
                    st.session_state.df_pedidos = df_pedidos.copy()
                    st.rerun()
        st.divider()
        st.subheader("Remover pedidos")
        # Remover pedidos selecionados
        def format_option(x):
            num = df_editado.loc[x, 'Nº Pedido'] if 'Nº Pedido' in df_editado.columns else str(x)
            cliente = df_editado.loc[x, 'Nome Cliente'] if 'Nome Cliente' in df_editado.columns else ''
            return f"{num} - {cliente}" if cliente else f"{num}"
        indices_remover = st.multiselect("Selecione os pedidos para remover", df_editado.index.tolist(), format_func=format_option)
        col_btn3, col_btn4 = st.columns(2)
        with col_btn3:
            if st.button("Remover selecionados") and indices_remover:
                if 'Nº Pedido' in df_editado.columns and 'Nº Pedido' in st.session_state.df_pedidos.columns:
                    pedidos_remover = df_editado.loc[indices_remover, 'Nº Pedido']
                    st.session_state.df_pedidos = st.session_state.df_pedidos[~st.session_state.df_pedidos['Nº Pedido'].isin(pedidos_remover)].reset_index(drop=True)
                else:
                    st.session_state.df_pedidos = st.session_state.df_pedidos.drop(indices_remover).reset_index(drop=True)
                salvar_pedidos(st.session_state.df_pedidos)
                st.success("Pedidos removidos!")
                st.rerun()
        with col_btn4:
            if st.button("Limpar todos os pedidos", type="primary"):
                st.session_state.df_pedidos = pd.DataFrame()
                salvar_pedidos(st.session_state.df_pedidos)
                st.success("Todos os pedidos foram removidos!")
                st.rerun()
    st.divider()
    st.subheader("Adicionar novo pedido")
    with st.form("add_pedido_form"):
        col1, col2, col3 = st.columns(3)
        with col1:
            numero = st.text_input("Nº Pedido")
            cod_cliente = st.text_input("Cód. Cliente")
            cnpj = st.text_input("CNPJ")
            nome_cliente = st.text_input("Nome Cliente")
            grupo_cliente = st.text_input("Grupo Cliente")
        with col2:
            endereco_entrega = st.text_input("Endereço de Entrega")
            bairro_entrega = st.text_input("Bairro de Entrega")
            cidade_entrega = st.text_input("Cidade de Entrega")
            estado_entrega = st.text_input("Estado de Entrega")
            qtde_itens = st.number_input("Qtde. dos Itens", min_value=0, step=1)
            peso_itens = st.number_input("Peso dos Itens", min_value=0.0, step=1.0, format="%.2f")
        with col3:
            latitude = st.number_input("Latitude", format="%.14f", value=-23.51689237191825)
            longitude = st.number_input("Longitude", format="%.14f", value=-46.48921155767101)
            anomalia = st.checkbox("Anomalia")
        # Endereço Completo gerado automaticamente
        endereco_completo_final = f"{endereco_entrega}, {bairro_entrega}, {cidade_entrega}, {estado_entrega}".strip(', ')
        regiao_final = f"{bairro_entrega} - São Paulo" if cidade_entrega.strip().lower() == "são paulo" and bairro_entrega else cidade_entrega
        submitted = st.form_submit_button("Adicionar pedido")
        if submitted and numero:
            novo = {
                "Nº Pedido": numero,
                "Cód. Cliente": cod_cliente,
                "CNPJ": cnpj,
                "Nome Cliente": nome_cliente,
                "Grupo Cliente": grupo_cliente,
                "Endereço de Entrega": endereco_entrega,
                "Bairro de Entrega": bairro_entrega,
                "Cidade de Entrega": cidade_entrega,
                "Estado de Entrega": estado_entrega,
                "Qtde. dos Itens": qtde_itens,
                "Peso dos Itens": peso_itens,
                "Endereço Completo": endereco_completo_final,
                "Região": regiao_final,
                "Latitude": latitude,
                "Longitude": longitude,
                "Anomalia": anomalia
            }
            st.session_state.df_pedidos = pd.concat([st.session_state.df_pedidos, pd.DataFrame([novo])], ignore_index=True)
            salvar_pedidos(st.session_state.df_pedidos)
            st.success("Pedido adicionado!")
            st.rerun()
    # Exportação de anomalias para CSV
    if 'df_filtrado' in locals():
        anomalias = df_filtrado[df_filtrado['Latitude'].isnull() | df_filtrado['Longitude'].isnull()]
        if not anomalias.empty:
            st.download_button(
                label="Exportar anomalias para CSV",
                data=anomalias.to_csv(index=False).encode('utf-8'),
                file_name=f"anomalias_{pd.Timestamp.now().strftime('%Y%m%d_%H%M%S')}.csv",
                mime="text/csv"
            )
    # Visualização de pedidos no mapa (fora do formulário)
    if 'df_filtrado' in locals() and st.button("Visualizar pedidos no mapa"):
        if 'Latitude' in df_filtrado.columns and 'Longitude' in df_filtrado.columns:
            df_map = df_filtrado.dropna(subset=["Latitude", "Longitude"]).rename(columns={"Latitude": "latitude", "Longitude": "longitude"})
            st.map(df_map)
        else:
            st.warning("Não há coordenadas suficientes para exibir no mapa.")
