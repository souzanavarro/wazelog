import streamlit as st
import pandas as pd
from database import carregar_pedidos, carregar_endereco_partida
import folium
from folium.plugins import MarkerCluster
from streamlit_folium import st_folium
import random
import time # Necessário para o sleep
import os # <<< ADICIONADO para verificar existência do arquivo

# Função para gerar cores aleatórias
def gerar_cor_aleatoria():
    return "#{:06x}".format(random.randint(0, 0xFFFFFF))

st.markdown('<div style="display:flex;align-items:center;gap:1rem;margin-bottom:1.5rem;"><span style="font-size:2.5rem;">🗾</span><span style="font-size:2rem;font-weight:700;">Mapas</span></div>', unsafe_allow_html=True)
st.markdown('<div class="hero-subtitle">Visualize rotas e entregas no mapa de forma clara</div>', unsafe_allow_html=True)
st.header("Mapas de Pedidos", divider="rainbow")
st.write("Visualize todos os pedidos e rotas no mapa de forma simples e rápida.")
st.divider()

# <<< ADICIONADO: Caminho para o arquivo CSV >>>
ROTEIRIZACAO_CSV_PATH = "/workspaces/WazeLog/data/Roteirizacao.csv"

# <<< ADICIONADO: URL do servidor OSRM >>>
OSRM_SERVER_URL = os.environ.get("OSRM_BASE_URL", "https://router.project-osrm.org")

def show():
    st.header("Mapas de Rotas", divider="rainbow")
    st.write("Visualize no mapa os pontos dos pedidos e as rotas por veículo.")

    # Carrega dados básicos
    pedidos_todos = carregar_pedidos()
    endereco_partida_salvo, lat_partida_salva, lon_partida_salva = carregar_endereco_partida()
    default_depot_location = [lat_partida_salva, lon_partida_salva] if lat_partida_salva and lon_partida_salva else [-23.5505, -46.6333]

    # --- Seletor de Visualização ---
    cenarios_disponiveis = st.session_state.get('cenarios_roteirizacao', [])
    opcoes_visualizacao = ["Mostrar apenas pedidos"]
    # <<< ADICIONADO: Opção para carregar do CSV >>>
    if os.path.exists(ROTEIRIZACAO_CSV_PATH):
        opcoes_visualizacao.append("Carregar última rota salva (CSV)")
    # Adiciona cenários da sessão
    opcoes_visualizacao.extend([
        f"{i}: {c.get('data', '')} - {c.get('tipo', '')} ({c.get('qtd_pedidos_roteirizados', '?')} pedidos)"
        for i, c in enumerate(cenarios_disponiveis)
    ])

    selecao = st.selectbox(
        "Selecione o que deseja visualizar no mapa:",
        options=opcoes_visualizacao,
        index=0 # Padrão é "Mostrar apenas pedidos"
    )

    # Inicializa variáveis do mapa
    map_location = default_depot_location
    rotas_df = None
    pedidos_mapa = pd.DataFrame()
    depot_lat = default_depot_location[0]
    depot_lon = default_depot_location[1]

    # --- Processa a Seleção ---
    depot_index = 0  # Índice do depósito na matriz de distâncias
    if selecao == "Mostrar apenas pedidos":
        st.info("Exibindo localizações dos pedidos carregados.")
        if pedidos_todos is not None:
            pedidos_mapa = pedidos_todos.dropna(subset=['Latitude', 'Longitude']).copy()
            if not pedidos_mapa.empty:
                # <<< SUBSTITUÍDO st.map por folium >>>
                map_location = default_depot_location # Usa localização padrão ou salva
                m = folium.Map(location=map_location, zoom_start=11) # Zoom um pouco mais afastado

                # Adiciona marcador do depósito (opcional, mas mantém consistência)
                if depot_lat and depot_lon:
                    folium.Marker(
                        [depot_lat, depot_lon],
                        icon=folium.Icon(color='blue', icon='home'),
                        tooltip='Depósito'
                    ).add_to(m)

                # Gera um dicionário de cores por cluster/região
                cor_por_grupo = {}
                grupos = None
                if 'Cluster' in pedidos_mapa.columns:
                    grupos = pedidos_mapa['Cluster'].unique()
                    for i, grupo in enumerate(grupos):
                        cor_por_grupo[grupo] = gerar_cor_aleatoria()
                elif 'Região' in pedidos_mapa.columns:
                    grupos = pedidos_mapa['Região'].unique()
                    for i, grupo in enumerate(grupos):
                        cor_por_grupo[grupo] = gerar_cor_aleatoria()
                # Adiciona marcadores para cada pedido como bolinhas pequenas e coloridas por grupo
                for idx, row in pedidos_mapa.iterrows():
                    grupo = row['Cluster'] if 'Cluster' in pedidos_mapa.columns else row['Região'] if 'Região' in pedidos_mapa.columns else None
                    cor = cor_por_grupo.get(grupo, gerar_cor_aleatoria())
                    pedido_info = f"Pedido: {row.get('Nº Pedido', 'ID Desconhecido')}" + (f"<br>Grupo: {grupo}" if grupo is not None else "")
                    folium.CircleMarker(
                        location=[row['Latitude'], row['Longitude']],
                        radius=6,
                        color=cor,
                        fill=True,
                        fill_color=cor,
                        fill_opacity=0.85,
                        tooltip=pedido_info,
                        popup=pedido_info
                    ).add_to(m)

                # Exibe o mapa folium
                st_folium(m, width=None, height=500, key="mapa_apenas_pedidos") # Chave fixa para esta visualização
            else:
                st.warning("Nenhum pedido com coordenadas válidas encontrado.")
        else:
            st.warning("Não foi possível carregar os dados dos pedidos.")

    # <<< ADICIONADO: Lógica para carregar do CSV >>>
    elif selecao == "Carregar última rota salva (CSV)":
        st.info(f"Tentando carregar a última rota salva de {ROTEIRIZACAO_CSV_PATH}")
        try:
            rotas_df = pd.read_csv(ROTEIRIZACAO_CSV_PATH, encoding='utf-8')
            if not rotas_df.empty and 'Latitude' in rotas_df.columns and 'Longitude' in rotas_df.columns:
                st.success(f"Rota carregada com sucesso do arquivo CSV ({len(rotas_df)} pontos).")
                # Usa as coordenadas do depósito salvas
                depot_lat = default_depot_location[0]
                depot_lon = default_depot_location[1]
                map_location = [depot_lat, depot_lon]
            else:
                st.error("O arquivo CSV está vazio ou não contém as colunas 'Latitude' e 'Longitude'.")
                rotas_df = None # Garante que não prossiga
        except FileNotFoundError:
            st.error(f"Arquivo {ROTEIRIZACAO_CSV_PATH} não encontrado.")
            rotas_df = None
        except Exception as e:
            st.error(f"Erro ao ler o arquivo CSV: {e}")
            rotas_df = None

    # <<< MODIFICADO: Condição para cenários da sessão >>>
    elif ":" in selecao: # Identifica cenários da sessão pelo formato "índice: descrição"
        try:
            idx_cenario = int(selecao.split(":")[0])
            cenario_selecionado = cenarios_disponiveis[idx_cenario]
            rotas_df = cenario_selecionado.get('rotas')
            depot_lat = cenario_selecionado.get('lat_partida', default_depot_location[0])
            depot_lon = cenario_selecionado.get('lon_partida', default_depot_location[1])
            map_location = [depot_lat, depot_lon]

            if rotas_df is not None and not rotas_df.empty and 'Latitude' in rotas_df.columns and 'Longitude' in rotas_df.columns:
                st.info(f"Exibindo rotas do cenário: {cenario_selecionado.get('data', '')} ({cenario_selecionado.get('tipo', '')})")
                # Filtro de placas e cards de resumo
                placa_selecionada = None
                if 'Veículo' in rotas_df.columns:
                    placas_unicas = rotas_df['Veículo'].dropna().unique().tolist()
                    placa_selecionada = st.selectbox(
                        "Selecione a placa do veículo para análise:",
                        options=placas_unicas,
                        index=0,
                        help="Selecione uma placa para visualizar e analisar as rotas desse veículo no mapa."
                    )
                    if placa_selecionada:
                        rotas_df = rotas_df[rotas_df['Veículo'] == placa_selecionada]
                        # Cards de resumo
                        capacidade_veiculo = None
                        frota_df = None
                        try:
                            from database import carregar_frota
                            frota_df = carregar_frota()
                        except Exception:
                            pass
                        if frota_df is not None and not frota_df.empty and 'Placa' in frota_df.columns:
                            veic_row = frota_df[frota_df['Placa'] == placa_selecionada]
                            if not veic_row.empty:
                                capacidade_veiculo = veic_row.iloc[0].get('Capacidade (Kg)', None)
                        qtd_pedidos = len(rotas_df)
                        # --- CORREÇÃO AQUI: Usar 'Demanda' em vez de 'Peso dos Itens' ---
                        peso_total = 0
                        if 'Demanda' in rotas_df.columns:
                            # Garante que a coluna é numérica antes de somar
                            demanda_numeric = pd.to_numeric(rotas_df['Demanda'], errors='coerce').fillna(0)
                            peso_total = demanda_numeric.sum()
                        else:
                            st.warning("Coluna 'Demanda' não encontrada no DataFrame de rotas filtrado.")
                        # --- FIM DA CORREÇÃO ---

                # Exibe rotas no mapa com trajeto real por ruas usando OSRM
                if not rotas_df.empty:
                    pontos = rotas_df.dropna(subset=["Latitude", "Longitude"])
                    if not pontos.empty:
                        if 'Sequencia' in pontos.columns:
                            pontos = pontos.sort_values('Sequencia')

                        # --- OTIMIZAÇÃO: Requisição única OSRM para toda a rota ---
                        coords = [[depot_lat, depot_lon]]
                        coords += pontos[["Latitude", "Longitude"]].values.tolist()
                        if len(coords) > 2 and (coords[-1] != coords[0]):
                            coords.append([depot_lat, depot_lon])
                        m = folium.Map(location=[depot_lat, depot_lon], zoom_start=12)
                        folium.Marker([depot_lat, depot_lon], icon=folium.Icon(color='blue', icon='home'), tooltip='Depósito').add_to(m)

                        # Usa MarkerCluster para muitos pontos
                        marker_cluster = MarkerCluster().add_to(m)
                        for i, row in pontos.iterrows():
                            pedido_id_display = row.get('ID Pedido', row.get('Nº Pedido', 'ID Desconhecido'))
                            pedido_info = f"Pedido: {pedido_id_display}"
                            folium.Marker(
                                [row['Latitude'], row['Longitude']],
                                tooltip=pedido_info,
                                popup=pedido_info,
                                icon=folium.Icon(color='red', icon='info-sign')
                            ).add_to(marker_cluster)

                        # --- Requisição OSRM otimizada (multi-point) ---
                        import requests
                        progress_bar = st.progress(0, text="Calculando rota otimizada no mapa...")
                        try:
                            # Monta string de coordenadas para OSRM
                            coords_osrm = ";".join([f"{lon},{lat}" for lat, lon in coords])
                            url = f"{OSRM_SERVER_URL}/route/v1/driving/{coords_osrm}?overview=full&geometries=geojson"
                            resp = requests.get(url, timeout=30)
                            if resp.status_code == 200:
                                data = resp.json()
                                if data.get('routes'):
                                    route = data['routes'][0]
                                    geometry = route['geometry']
                                    folium.PolyLine(
                                        locations=[(lat, lon) for lon, lat in geometry['coordinates']],
                                        color='red', weight=4, opacity=0.8
                                    ).add_to(m)
                                    distancia_total_km = route.get('distance', 0) / 1000
                                    tempo_total_min = route.get('duration', 0) / 60
                                else:
                                    distancia_total_km = 0
                                    tempo_total_min = 0
                            else:
                                st.error(f"Erro ao requisitar rota ao OSRM: {resp.status_code}")
                                distancia_total_km = 0
                                tempo_total_min = 0
                        except Exception as osrm_err:
                            st.error(f"Erro ao requisitar rota ao OSRM: {osrm_err}")
                            distancia_total_km = 0
                            tempo_total_min = 0
                        progress_bar.empty()

                        # Chave dinâmica para o mapa
                        safe_selecao = "".join(c for c in selecao if c.isalnum() or c in ('_'))
                        map_key = f"folium_map_{safe_selecao}_{placa_selecionada or 'all'}"
                        st_folium(m, width=None, height=500, key=map_key)

                        # Exibir métricas organizadas em 2 colunas, separadas por '-'
                        # <<< GARANTIR INDENTAÇÃO CORRETA AQUI >>>
                        with st.container():
                            col_esq, col_dir = st.columns(2)
                            with col_esq:
                                st.metric("Placa do Veículo", placa_selecionada)
                                st.markdown("<div style='font-size:1.2rem;text-align:center;'>-</div>", unsafe_allow_html=True)
                                st.metric("Pedidos Empenhados", qtd_pedidos)
                                st.markdown("<div style='font-size:1.2rem;text-align:center;'>-</div>", unsafe_allow_html=True)
                                st.metric("Distância Total (km)", f"{distancia_total_km:.1f}")
                            with col_dir:
                                st.metric("Capacidade do Veículo (Kg)", f"{capacidade_veiculo:,.1f}" if capacidade_veiculo is not None else "N/A")
                                st.markdown("<div style='font-size:1.2rem;text-align:center;'>-</div>", unsafe_allow_html=True)
                                st.metric("Peso Empenhado (Kg)", f"{peso_total:,.1f}")
                                st.markdown("<div style='font-size:1.2rem;text-align:center;'>-</div>", unsafe_allow_html=True)
                                # Exibir tempo estimado no formato hh:mm
                                horas = int(tempo_total_min // 60) if tempo_total_min else 0
                                minutos = int(round(tempo_total_min % 60)) if tempo_total_min else 0
                                tempo_formatado = f"{horas}:{minutos:02d}"
                                st.metric("Tempo Estimado (h)", tempo_formatado)
                    else:
                        st.info("Não há coordenadas válidas para exibir o trajeto.")
                else:
                    st.info("Não há dados de rota para a placa selecionada.")
            else:
                # Se rotas_df for None ou vazio após carregar CSV ou cenário
                if selecao != "Mostrar apenas pedidos":
                     st.warning("Não foi possível carregar ou exibir os dados da rota selecionada.")
                # else: # Caso de 'Mostrar apenas pedidos' já tratado
                #     pass # Não faz nada extra aqui se for só pedidos

        except (ValueError, IndexError):
            st.error("Erro ao selecionar o cenário.")
        except Exception as e_map_display: # Captura exceção geral na exibição do mapa/métricas
             st.error(f"Erro ao exibir mapa ou métricas para o cenário selecionado: {e_map_display}")
             st.exception(e_map_display)

    # <<< MODIFICADO: Movido para fora do bloco try/except do cenário >>>
    elif selecao != "Mostrar apenas pedidos" and rotas_df is None: # Se tentou carregar CSV e falhou (rotas_df ainda é None)
        st.warning("Não foi possível carregar ou exibir os dados da rota selecionada do CSV.")


# Comentar execução direta se a navegação for centralizada
# if __name__ == "__main__":
#     show()

# --- NOVA SEÇÃO: Análise Detalhada por Veículo ---
st.divider()
st.header("Análise Detalhada por Veículo", divider="rainbow")
st.write("Selecione um veículo para ver detalhes da rota, incluindo distância, peso e tempo estimado.")
st.divider()

# Carrega dados básicos novamente (necessário aqui também)
pedidos_todos = carregar_pedidos()
endereco_partida_salvo, lat_partida_salva, lon_partida_salva = carregar_endereco_partida()
default_depot_location = [lat_partida_salva, lon_partida_salva] if lat_partida_salva and lon_partida_salva else [-23.5505, -46.6333]

# --- Seletor de Veículo ---
placas_disponiveis = []
cenarios_disponiveis = st.session_state.get('cenarios_roteirizacao', [])
for cenario in cenarios_disponiveis:
    rotas = cenario.get('rotas')
    if rotas is not None and not rotas.empty and 'Veículo' in rotas.columns:
        placas = rotas['Veículo'].dropna().unique().tolist()
        placas_disponiveis.extend(placas)
placas_disponiveis = list(set(placas_disponiveis)) # Remove duplicatas
placas_disponiveis.sort()

veiculo_selecionado = st.selectbox(
    "Selecione o veículo para análise detalhada:",
    options=placas_disponiveis,
    index=0 if placas_disponiveis else -1,
    help="Selecione um veículo para ver detalhes da rota, incluindo distância, peso e tempo estimado."
)

# --- Processa Seleção de Veículo ---
if veiculo_selecionado:
    st.info(f"Analisando dados para o veículo: {veiculo_selecionado}")
    rotas_veiculo = []
    for cenario in cenarios_disponiveis:
        rotas = cenario.get('rotas')
        if rotas is not None and not rotas.empty:
            # Filtra apenas as rotas do veículo selecionado
            rotas_veiculo.append(rotas[rotas['Veículo'] == veiculo_selecionado])

    if rotas_veiculo:
        # Concatena todos os DataFrames de rotas do veículo selecionado
        rota_veiculo_selecionado = pd.concat(rotas_veiculo, ignore_index=True)
        st.success(f"Foram encontradas {len(rota_veiculo_selecionado)} rotas para o veículo selecionado.")

        # --- Tabela da Rota Selecionada ---
        st.subheader("Tabela da Rota Selecionada")
        st.dataframe(rota_veiculo_selecionado, use_container_width=True, hide_index=True)

        # --- Cálculo da Distância Total ---
        distancia_total_m = 0
        matriz_distancias = None
        if 'Node_Index_OR' in rota_veiculo_selecionado.columns:
            # Tenta carregar a matriz de distâncias correspondente
            try:
                id_cenario = rota_veiculo_selecionado['ID_Cenario'].iloc[0] if not rota_veiculo_selecionado.empty else None
                if id_cenario is not None:
                    matriz_distancias = st.session_state.get(f"matriz_distancias_{id_cenario}")
                    if matriz_distancias is not None:
                        st.info("Matriz de distâncias encontrada na sessão.")
                    else:
                        st.warning("Matriz de distâncias não encontrada na sessão.")
                else:
                    st.error("ID do cenário não encontrado na rota selecionada.")
            except Exception as e:
                st.error(f"Erro ao carregar matriz de distâncias: {e}")

        # --- Cálculo da Distância Total (continuação) ---
        if matriz_distancias is not None and 'Node_Index_OR' in rota_veiculo_selecionado.columns:
            node_indices = [depot_index] + rota_veiculo_selecionado.sort_values('Sequencia')['Node_Index_OR'].tolist() + [depot_index]
            for i in range(len(node_indices) - 1):
                idx_from = node_indices[i]
                idx_to = node_indices[i+1]
                if 0 <= idx_from < len(matriz_distancias) and 0 <= idx_to < len(matriz_distancias[idx_from]):
                    distancia_total_m += matriz_distancias[idx_from][idx_to]
                else:
                    st.warning(f"Índice fora dos limites ao calcular distância: {idx_from} -> {idx_to}")

        distancia_total_km = distancia_total_m / 1000 if distancia_total_m > 0 else 0
        st.metric("Distância Total (km)", f"{distancia_total_km:,.1f}")

        # --- Cálculo do Peso Empenhado ---
        peso_empenhado = 0
        if 'Demanda' in rota_veiculo_selecionado.columns:
            # Converte para numérico, força erros para NaN, preenche NaN com 0
            demanda_numeric = pd.to_numeric(rota_veiculo_selecionado['Demanda'], errors='coerce').fillna(0)
            peso_empenhado = demanda_numeric.sum()
            # Debug temporário (pode ser removido depois)
            # st.write(f"Debug: Coluna Demanda (numeric): {demanda_numeric.tolist()}")
            # st.write(f"Debug: Soma da Demanda: {peso_empenhado}")
        else:
            st.warning("Coluna 'Demanda' não encontrada para calcular peso empenhado.")
            # st.write("Debug: Colunas disponíveis:", rota_veiculo_selecionado.columns.tolist())

        st.metric("Peso Empenhado (Kg)", f"{peso_empenhado:,.1f}")

        # --- Cálculo do Tempo Estimado ---
        # Usar a distância total e uma velocidade média estimada (ex: 40 km/h)
        velocidade_media_kmh = 40
        tempo_estimado_h = distancia_total_km / velocidade_media_kmh if velocidade_media_kmh > 0 else 0
        horas = int(tempo_estimado_h)
        minutos = int((tempo_estimado_h - horas) * 60)
        st.metric("Tempo Estimado (h)", f"{horas:02d}:{minutos:02d}")

        # --- Gráfico da Rota (opcional) ---
        st.subheader("Gráfico da Rota")
        if 'Latitude' in rota_veiculo_selecionado.columns and 'Longitude' in rota_veiculo_selecionado.columns:
            coords = rota_veiculo_selecionado[['Latitude', 'Longitude']].dropna().values.tolist()
            if coords:
                m = folium.Map(location=coords[0], zoom_start=12)
                folium.Marker(coords[0], icon=folium.Icon(color='blue', icon='home'), tooltip='Início').add_to(m)
                folium.Marker(coords[-1], icon=folium.Icon(color='red', icon='flag'), tooltip='Fim').add_to(m)
                folium.PolyLine(coords, color='green', weight=2.5, opacity=0.8).add_to(m)
                st_folium(m, width=None, height=500, key="mapa_rota_selecionada")
            else:
                st.warning("Nenhum ponto válido encontrado para exibir no mapa.")
        else:
            st.warning("As colunas 'Latitude' e 'Longitude' não foram encontradas na rota selecionada.")

        # --- Métricas do veículo selecionado
        col1_met, col2_met = st.columns(2)
        with col1_met:
            st.metric("Placa do Veículo", veiculo_selecionado)
            st.metric("Pedidos Empenhados", len(rota_veiculo_selecionado))
            # Calcular Distância Total para este veículo
            distancia_veiculo_m = 0
            if matriz_distancias is not None and 'Node_Index_OR' in rota_veiculo_selecionado.columns:
                node_indices_veiculo = [depot_index] + rota_veiculo_selecionado.sort_values('Sequencia')['Node_Index_OR'].tolist() + [depot_index]
                for i in range(len(node_indices_veiculo) - 1):
                    idx_from = node_indices_veiculo[i]
                    idx_to = node_indices_veiculo[i+1]
                    if 0 <= idx_from < len(matriz_distancias) and 0 <= idx_to < len(matriz_distancias[idx_from]):
                        distancia_veiculo_m += matriz_distancias[idx_from][idx_to]
                    else:
                        st.warning(f"Índice fora dos limites ao calcular distância para veículo {veiculo_selecionado}: {idx_from} -> {idx_to}")
            st.metric("Distância Total (km)", f"{distancia_veiculo_m / 1000:,.1f}")

        with col2_met:
            # Tenta buscar a capacidade da frota do cenário, se disponível
            capacidade_veiculo = 0
            frota_cenario = None
            id_cenario_atual = None
            # Encontra o cenário correspondente para buscar a frota
            for i, c in enumerate(cenarios_disponiveis):
                rotas_c = c.get('rotas')
                if rotas_c is not None and not rotas_c.empty and veiculo_selecionado in rotas_c['Veículo'].unique():
                    # Assume que a frota usada está no mesmo cenário (pode precisar de ajuste se não for o caso)
                    # Idealmente, a frota usada deveria ser salva junto com o cenário
                    # Tenta buscar a frota do estado da sessão se não foi salva no cenário
                    frota_cenario = c.get('frota_usada', st.session_state.get('frota_carregada')) # Exemplo
                    id_cenario_atual = i
                    break # Usa o primeiro cenário encontrado com o veículo

            if frota_cenario is not None and not frota_cenario.empty:
                id_col_frota = 'ID Veículo' if 'ID Veículo' in frota_cenario.columns else 'Placa'
                if id_col_frota in frota_cenario.columns and 'Capacidade (Kg)' in frota_cenario.columns:
                    veiculo_info = frota_cenario[frota_cenario[id_col_frota] == veiculo_selecionado]
                    if not veiculo_info.empty:
                        capacidade_veiculo = pd.to_numeric(veiculo_info['Capacidade (Kg)'].iloc[0], errors='coerce').fillna(0)

            st.metric("Capacidade do Veículo (Kg)", f"{capacidade_veiculo:,.1f}")

            # --- CORREÇÃO REFORÇADA AQUI ---
            peso_empenhado = 0
            if 'Demanda' in rota_veiculo_selecionado.columns:
                # Converte para numérico, força erros para NaN, preenche NaN com 0
                demanda_numeric = pd.to_numeric(rota_veiculo_selecionado['Demanda'], errors='coerce').fillna(0)
                peso_empenhado = demanda_numeric.sum()
                # Debug temporário (pode ser removido depois)
                # st.write(f"Debug: Coluna Demanda (numeric): {demanda_numeric.tolist()}")
                # st.write(f"Debug: Soma da Demanda: {peso_empenhado}")
            else:
                st.warning("Coluna 'Demanda' não encontrada para calcular peso empenhado.")
                # st.write("Debug: Colunas disponíveis:", rota_veiculo_selecionado.columns.tolist())

            st.metric("Peso Empenhado (Kg)", f"{peso_empenhado:,.1f}")
            # --- FIM DA CORREÇÃO REFORÇADA ---

            # Calcular Tempo Estimado (usando distância calculada anteriormente)
            tempo_estimado_h = distancia_veiculo_m / (40 * 1000) if distancia_veiculo_m > 0 else 0 # Exemplo: 40 km/h médio
            horas = int(tempo_estimado_h)
            minutos = int((tempo_estimado_h - horas) * 60)
            st.metric("Tempo Estimado (h)", f"{horas:02d}:{minutos:02d}")

    else:
        st.warning(f"Nenhuma rota encontrada nos cenários para o veículo selecionado: {veiculo_selecionado}")

else: # Fim do if veiculo_selecionado
    if placas_disponiveis:
        st.info("Selecione um veículo na lista acima para ver a análise detalhada.")
    else:
        st.warning("Nenhum veículo com rotas encontradas nos cenários disponíveis para análise.")
