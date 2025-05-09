import streamlit as st
import pandas as pd
import numpy as np # Adicionado
import time # Adicionado

# Adicionado para uso potencial
from relatorio_template import gerar_relatorio_html

# Importações adicionadas para funcionalidade completa
from database import (
    carregar_pedidos,
    carregar_frota,
    salvar_endereco_partida,
    carregar_endereco_partida
)
# Ajuste na importação dos solvers para pegar do módulo correto
from routing.cvrp import solver_cvrp
from routing.cvrp_flex import solver_cvrp
# Modificado para importar também INFINITE_VALUE
from routing.distancias import calcular_matriz_distancias, INFINITE_VALUE
from pedidos import obter_coordenadas # Para geocodificação do endereço de partida

# Constantes para endereço de partida padrão
DEFAULT_ENDERECO_PARTIDA = "Avenida Antonio Ortega, 3604 - Pinhal, Cabreúva - SP, 13315-000"
DEFAULT_LAT_PARTIDA = -23.251501
DEFAULT_LON_PARTIDA = -47.084560

def show():
    # Inicializa o estado da sessão para cenários, se necessário
    if 'cenarios_roteirizacao' not in st.session_state:
        st.session_state.cenarios_roteirizacao = []


    st.header("Roteirizador de Entregas", divider="rainbow") # Usando header como no original
    st.write("Carregue os dados, configure a partida, selecione o tipo de roteirização e calcule as rotas.")

    # Variáveis para armazenar dados carregados e coordenadas de partida
    pedidos = None
    frota = None
    lat_partida = None
    lon_partida = None
    endereco_partida = None
    pedidos_nao_alocados = pd.DataFrame() # Inicializa vazio

    try:
        # Carrega os dataframes usando as funções do database
        pedidos = carregar_pedidos()
        frota = carregar_frota()

        # Processamento da Frota
        if frota is not None and not frota.empty:
             frota = frota.loc[:, ~frota.columns.duplicated()] # Remove colunas duplicadas
             if 'Disponível' in frota.columns:
                  # Filtra disponíveis
                  frota = frota[frota['Disponível'] == True]
             else:
                 st.warning("Coluna 'Disponível' não encontrada na frota. Considerando todos os veículos.")
             # Garante colunas essenciais e tipos corretos
             if 'Capacidade (Kg)' not in frota.columns:
                 frota['Capacidade (Kg)'] = 0
             else:
                 frota['Capacidade (Kg)'] = pd.to_numeric(frota['Capacidade (Kg)'], errors='coerce').fillna(0)
             if 'Janela Início' not in frota.columns:
                 frota['Janela Início'] = '00:00'
             if 'Janela Fim' not in frota.columns:
                 frota['Janela Fim'] = '23:59'
        else:
             st.warning("Não foi possível carregar dados da frota ou a frota está vazia.")
             frota = pd.DataFrame() # Dataframe vazio para evitar erros

        # Processamento dos Pedidos
        if pedidos is not None and not pedidos.empty:
            if 'Região' in pedidos.columns:
                pedidos_sorted = pedidos.sort_values(by='Região').reset_index(drop=True)
            else:
                st.warning("Coluna 'Região' não encontrada nos pedidos. Exibindo sem ordenação por região.")
                pedidos_sorted = pedidos
            # Garante colunas essenciais e tipos corretos
            if 'Janela de Descarga' not in pedidos.columns:
                pedidos['Janela de Descarga'] = 30
            if 'Latitude' not in pedidos.columns:
                pedidos['Latitude'] = None
            if 'Longitude' not in pedidos.columns:
                pedidos['Longitude'] = None
            # --- NOVO: Garante que a coluna Cluster está presente e correta ---
            try:
                from routing.utils import clusterizar_pedidos
                # Corrige: clusters só para regiões presentes em pedidos válidos
                pedidos_validos = pedidos.dropna(subset=['Latitude', 'Longitude']).copy()
                regioes_validas = pedidos_validos['Região'].dropna().unique() if 'Região' in pedidos_validos.columns else []
                n_clusters = len(regioes_validas) if len(regioes_validas) > 0 else 1
                # Protege para não passar mais clusters que pedidos válidos
                n_clusters = min(n_clusters, len(pedidos_validos)) if len(pedidos_validos) > 0 else 1
                if 'Cluster' not in pedidos.columns or pedidos['Cluster'].isnull().all():
                    pedidos['Cluster'] = -1  # Inicializa todos como não agrupados
                    if not pedidos_validos.empty:
                        clusters_validos = clusterizar_pedidos(pedidos_validos, n_clusters=n_clusters)
                        pedidos.loc[pedidos_validos.index, 'Cluster'] = clusters_validos
            except Exception as e:
                st.warning(f"Não foi possível calcular o agrupamento inicial de pedidos (Cluster): {e}")
            # Separa pedidos não alocados (sem coordenadas) ANTES de filtrar
            pedidos_nao_alocados = pedidos[pedidos['Latitude'].isna() | pedidos['Longitude'].isna()].copy()
            pedidos_validos = pedidos.dropna(subset=['Latitude', 'Longitude']).copy()
        else:
            st.warning("Não foi possível carregar dados dos pedidos ou não há pedidos.")
            pedidos = pd.DataFrame() # Dataframe vazio
            pedidos_sorted = pd.DataFrame()
            pedidos_validos = pd.DataFrame()


        # --- MOVIDO PARA CÁ: Configuração do Rodízio de Placas SP ---
        st.subheader("Configuração do Rodízio de Placas SP")
        considerar_rodizio = st.checkbox(
            'Considerar rodízio de placas SP',
            value=True,
            help='Se marcado, veículos em rodízio não serão usados na roteirização.'
        )
        dias_semana = ['Segunda-feira', 'Terça-feira', 'Quarta-feira', 'Quinta-feira', 'Sexta-feira', 'Sábado', 'Domingo']
        hoje = pd.Timestamp.now().weekday()
        dia_roteirizacao = st.selectbox(
            'Dia da roteirização (para rodízio de placas em SP)',
            options=list(enumerate(dias_semana)),
            index=hoje if hoje < 5 else 0, # Padrão para hoje, ou segunda se for fim de semana
            format_func=lambda x: x[1],
            help='Veículos em rodízio neste dia não serão usados na roteirização.'
        )[0] # Pega o índice do dia (0 para Segunda, ...)


        # --- NOVA LÓGICA: Rodízio só para pedidos com destino SP ---
        if frota is not None and not frota.empty:
            if 'Placa' in frota.columns:
                from routing.utils import placa_em_rodizio_sp, pedido_destino_sp
                if considerar_rodizio and dia_roteirizacao in range(5):
                    frota['Rodizio_SP'] = frota['Placa'].apply(lambda p: placa_em_rodizio_sp(p, dia_roteirizacao))
                    st.info(f"{frota['Rodizio_SP'].sum()} veículos em rodízio para {dias_semana[dia_roteirizacao]}.")
                else:
                    frota['Rodizio_SP'] = False
                    if considerar_rodizio and dia_roteirizacao not in range(5):
                        st.info('Rodízio de placas só é aplicado de segunda a sexta-feira.')
            else:
                frota['Rodizio_SP'] = False
        elif isinstance(frota, pd.DataFrame):
            frota['Rodizio_SP'] = pd.Series(dtype=bool)

        # --- Filtro dinâmico para pedidos SP: só veículos fora do rodízio ---
        def get_frota_para_pedido(pedido):
            from routing.utils import pedido_destino_sp
            if pedido_destino_sp(pedido):
                # Só veículos fora do rodízio
                return frota[frota['Rodizio_SP'] == False]
            else:
                return frota


        # Exibição lado a lado dos dados carregados
        st.subheader("Dados Carregados")
        # --- NOVO: Tabela de Frota Disponível com seleção de rodízio ---
        col1_data, col2_data = st.columns(2)
        with col1_data:
            st.caption(f"Pedidos ({len(pedidos_sorted)})")
            st.dataframe(pedidos_sorted, height=200, use_container_width=True) # Ajuste de altura e largura
        with col2_data:
            # ADICIONADO: Exibição da frota que estava na seção de Agrupamento
            st.caption(f"Frota Disponível ({len(frota)})")
            st.dataframe(frota, height=200, use_container_width=True)
        st.divider()

        # --- Configuração do Endereço de Partida ---
        st.subheader("Endereço de Partida (Depósito)")
        with st.expander("Configurar Endereço e Coordenadas", expanded=True):
            endereco_partida_salvo, lat_partida_salva, lon_partida_salva = carregar_endereco_partida()
            endereco_partida = st.text_input(
                "Endereço de partida",
                endereco_partida_salvo or DEFAULT_ENDERECO_PARTIDA,
                key="endereco_partida_input"
            )
            col1_addr, col2_addr = st.columns(2)
            with col1_addr:
                lat_partida_manual = st.text_input(
                    "Latitude",
                    f"{lat_partida_salva:.6f}" if lat_partida_salva is not None else str(DEFAULT_LAT_PARTIDA),
                    key="lat_partida_input"
                )
            with col2_addr:
                lon_partida_manual = st.text_input(
                    "Longitude",
                    f"{lon_partida_salva:.6f}" if lon_partida_salva is not None else str(DEFAULT_LON_PARTIDA),
                    key="lon_partida_input"
                )

            usar_coord_manual = st.checkbox("Usar coordenadas manuais", value=False, key="usar_coord_manual_cb")

            if endereco_partida:
                if usar_coord_manual:
                    try:
                        lat_partida = float(lat_partida_manual.replace(',', '.')) # Trata vírgula decimal
                        lon_partida = float(lon_partida_manual.replace(',', '.'))
                        st.info(f"Usando coordenadas manuais: {lat_partida:.6f}, {lon_partida:.6f}")
                        # Salva as coordenadas manuais junto com o endereço atual
                        salvar_endereco_partida(endereco_partida, lat_partida, lon_partida)
                    except (ValueError, TypeError):
                        st.error("Coordenadas manuais inválidas. Insira números válidos.")
                        lat_partida, lon_partida = None, None # Invalida
                else:
                    # Verifica se o endereço mudou ou se não há coordenadas salvas para ele
                    if endereco_partida != endereco_partida_salvo or lat_partida_salva is None or lon_partida_salva is None:
                        with st.spinner(f"Buscando coordenadas para {endereco_partida}..."):
                            coords = obter_coordenadas(endereco_partida)
                            if coords:
                                lat_partida, lon_partida = coords
                                st.success(f"Coordenadas encontradas: {lat_partida:.6f}, {lon_partida:.6f}")
                                salvar_endereco_partida(endereco_partida, lat_partida, lon_partida)
                            else:
                                st.error(f"Não foi possível encontrar coordenadas para o endereço: {endereco_partida}. Tente inserir manualmente.")
                                lat_partida, lon_partida = None, None # Invalida
                    else:
                        # Usa as coordenadas salvas
                        lat_partida, lon_partida = lat_partida_salva, lon_partida_salva
                        st.info(f"Usando coordenadas salvas para o endereço: {lat_partida:.6f}, {lon_partida:.6f}")

                # Exibe o status final das coordenadas de partida
                if lat_partida is None or lon_partida is None:
                     st.warning("Coordenadas de partida inválidas ou não definidas.")
                # else: # Info já exibida acima
                #      st.info(f"Coordenadas de partida definidas: {lat_partida:.6f}, {lon_partida:.6f}")

            else:
                st.warning("Endereço de partida não pode estar vazio.")
                lat_partida, lon_partida = None, None # Invalida

        st.divider()

        # --- Campos para definir janelas e tempo de serviço ---
        st.subheader("Configuração de Janelas e Tempo de Serviço para Todos os Pedidos")
        col_jan1, col_jan2, col_serv = st.columns(3)
        with col_jan1:
            janela_inicio = st.text_input("Janela Início", value="06:00", help="Horário de início da janela de atendimento (ex: 06:00)")
        with col_jan2:
            janela_fim = st.text_input("Janela Fim", value="20:00", help="Horário de fim da janela de atendimento (ex: 20:00)")
        with col_serv:
            tempo_servico = st.text_input("Tempo de Serviço", value="00:30", help="Tempo de serviço no local (ex: 00:30)")
        pedidos_validos['Janela Início'] = janela_inicio
        pedidos_validos['Janela Fim'] = janela_fim
        pedidos_validos['Tempo de Serviço'] = tempo_servico

        st.divider()

        # --- Seleção do Tipo de Roteirização ---
        st.subheader("Configuração da Roteirização")
        tipo = st.selectbox(
            "Selecione o tipo de problema de roteirização",
            ["CVRP", "CVRP Flex"],
            key="tipo_roteirizacao_select",
            help="Escolha o algoritmo de roteirização baseado nas restrições do seu problema."
        )
        explicacoes = {
            "CVRP": "CVRP (Capacitated VRP): Considera a capacidade máxima (Kg ou Cx) dos veículos.",
            "CVRP Flex": "CVRP Flex: Permite ajustar a capacidade dos veículos de 0% a 120% para simular sobrecarga controlada."
        }
        st.info(explicacoes.get(tipo, ""))

        ajuste_capacidade_pct = 100
        if tipo in ["CVRP", "CVRP Flex"]:
            ajuste_capacidade_pct = st.slider(
                "Ajuste de Capacidade dos Veículos (%)",
                min_value=80, max_value=120, value=100, step=1,
                help="Permite simular veículos carregando menos ou até 20% a mais que a capacidade cadastrada."
            )

        # --- Agrupamento Inicial de Pedidos (sempre exibe se possível) ---
        st.subheader("Agrupamento Inicial de Pedidos (por proximidade geográfica)")
        col1_agrup, col2_agrup = st.columns(2)
        with col1_agrup:
            if 'Cluster' in pedidos_validos.columns:
                st.caption(f"Pedidos Agrupados ({len(pedidos_validos)})") # Adicionado caption
                st.dataframe(pedidos_validos[['ID Pedido', 'Região', 'Latitude', 'Longitude', 'Cluster']] if 'ID Pedido' in pedidos_validos.columns else pedidos_validos[['Região', 'Latitude', 'Longitude', 'Cluster']], height=250, use_container_width=True) # Ajuste de altura
            else:
                st.info("Não foi possível gerar o agrupamento inicial de pedidos.")
        
        with col2_agrup:
            if 'Cluster' in pedidos_validos.columns:
                resumo_clusters = pedidos_validos.groupby('Cluster').agg(
                    Qtd_Pedidos=('Cluster', 'count'),
                    Lat_Media=('Latitude', 'mean'),
                    Lon_Media=('Longitude', 'mean')
                ).reset_index()
                # Adiciona veículo sugerido com mais cuidado para evitar IndexError
                veiculos_sugeridos = []
                for cluster_idx in resumo_clusters['Cluster']:
                    if not frota.empty and cluster_idx < len(frota):
                        if "ID Veículo" in frota.columns:
                            veiculos_sugeridos.append(frota.iloc[cluster_idx]["ID Veículo"])
                        elif "Placa" in frota.columns:
                            veiculos_sugeridos.append(frota.iloc[cluster_idx]["Placa"])
                        else:
                            veiculos_sugeridos.append(f'Veículo {cluster_idx + 1}')
                    else:
                        veiculos_sugeridos.append(f'Veículo {cluster_idx + 1}')
                resumo_clusters['Veículo Sugerido'] = veiculos_sugeridos
                
                st.caption(f"Resumo dos Clusters ({len(resumo_clusters)})") # Adicionado caption
                st.dataframe(resumo_clusters, height=250, use_container_width=True) # Ajuste de altura
            # else: # Não precisa de else aqui, se não há cluster, não mostra resumo
            #    pass 

        # --- Opções Avançadas de Pós-Processamento e Exportação ---
        st.subheader("Opções Avançadas de Pós-Processamento e Exportação")
        st.markdown("""
        <ul>
        <li><b>2-opt</b>: Heurística clássica para rotas, troca pares de arestas para reduzir a distância total do percurso de cada veículo.</li>
        <li><b>merge</b>: Tenta unir rotas de veículos diferentes, reduzindo o número de veículos utilizados quando possível.</li>
        <li><b>split</b>: Divide rotas longas em sub-rotas menores, útil para limitar o número de paradas por veículo.</li>
        </ul>
        <b>Outras opções:</b><br>
        <ul>
        <li><b>Reservar veículos para regiões críticas</b>: Garante que regiões com muitos pedidos tenham veículos dedicados.</li>
        <li><b>Heurística de vizinhança</b>: Move pedidos para veículos que já atendem clientes próximos, otimizando a proximidade geográfica.</li>
        <li><b>Aprendizado de máquina (ML)</b>: Sugere agrupamentos de pedidos com base em histórico de roteirizações (experimental).</li>
        <li><b>Balanceamento automático de carga</b>: Distribui os pedidos de forma mais equilibrada entre os veículos, considerando peso, paradas e região.</li>
        </ul>
        """, unsafe_allow_html=True)
        aplicar_pos = st.checkbox("Aplicar heurística de pós-processamento nas rotas (2-opt, merge, split)", value=False, help="Refina as rotas após o solver para tentar reduzir a distância total ou o número de veículos.")
        tipo_heuristica = st.selectbox(
            "Heurística de pós-processamento",
            ["2opt", "merge", "split"],
            index=0,
            help="Escolha a heurística a ser aplicada nas rotas após o solver. 2-opt reduz distância, merge tenta unir rotas, split divide rotas longas."
        ) if aplicar_pos else None
        max_paradas_split = st.number_input(
            "Máximo de paradas por sub-rota (split)",
            min_value=2, max_value=20, value=5, step=1,
            help="Usado apenas se split for selecionado."
        ) if aplicar_pos and tipo_heuristica == "split" else None
        st.caption("Após calcular as rotas, você poderá exportar o resultado para CSV ou GeoJSON.")

        # --- Opções Avançadas de Balanceamento ---
        st.subheader("Opções Avançadas de Balanceamento")
        st.markdown("""
        <ul>
        <li><b>Reservar veículos para regiões críticas</b>: Garante que regiões com muitos pedidos tenham veículos dedicados, evitando sobrecarga em regiões de alta demanda.</li>
        <li><b>Heurística de vizinhança</b>: Move pedidos para veículos que já atendem clientes próximos, otimizando a proximidade geográfica e reduzindo deslocamentos desnecessários.</li>
        <li><b>Aprendizado de máquina (ML)</b>: Sugere agrupamentos de pedidos com base em padrões históricos de roteirização, buscando melhorar a eficiência (experimental).</li>
        </ul>
        """, unsafe_allow_html=True)
        usar_reserva_regioes = st.checkbox(
            "Reservar veículos para regiões críticas (maior volume de pedidos)",
            value=False,
            help="Reserva veículos para regiões com mais pedidos, priorizando atendimento regional."
        )
        usar_vizinhanca = st.checkbox(
            "Ativar heurística de vizinhança (mover pedidos para veículos com clientes próximos)",
            value=False,
            help="Move pedidos para veículos que já atendem clientes próximos, minimizando distância incremental."
        )
        usar_ml = st.checkbox(
            "Sugerir agrupamento por aprendizado de máquina (experimental)",
            value=False,
            help="Sugere agrupamento de pedidos com base em histórico de roteirizações (placeholder)."
        )

        # --- Opção de Balanceamento de Carga ---
        st.subheader("Balanceamento de Carga entre Veículos")
        st.markdown("""
        <ul>
        <li><b>Balanceamento automático de carga</b>: Distribui os pedidos de forma mais equilibrada entre os veículos, considerando peso, número de paradas e região, para evitar sobrecarga em alguns veículos e subutilização de outros.</li>
        </ul>
        """, unsafe_allow_html=True)
        balanceamento_auto = st.checkbox(
            "Ativar balanceamento automático de carga entre veículos",
            value=False,
            help="Se ativado, o sistema tentará distribuir os pedidos de forma mais equilibrada entre os veículos após o solver."
        )
        if balanceamento_auto:
            st.info("O balanceamento automático de carga será aplicado após o solver para tentar usar todos os veículos ativos e distribuir melhor os pedidos.")
        else:
            st.info("O balanceamento automático de carga NÃO será aplicado. As rotas serão mantidas conforme o solver.")

        # --- Resumo dos Dados para Roteirização ---
        with st.container(border=True): # Adiciona borda ao container
            st.markdown("##### Resumo para Cálculo")
            # Primeira linha: Pedidos com Coordenadas | Peso Total (Kg)
            col1_sum, col2_sum = st.columns(2)
            # pedidos_validos já foi definido acima
            with col1_sum:
                st.metric("Pedidos com Coordenadas", len(pedidos_validos))
            with col2_sum:
                peso_total = pedidos_validos['Peso dos Itens'].sum() if 'Peso dos Itens' in pedidos_validos.columns else 0
                st.metric("Peso Total (Kg)", f"{peso_total:,.1f}")
            # Segunda linha: Veículos Disponíveis | Capacidade Total (Kg)
            col3_sum, col4_sum = st.columns(2)
            with col3_sum:
                st.metric("Veículos Disponíveis", len(frota))
            with col4_sum:
                capacidade_total_kg = frota['Capacidade (Kg)'].sum() if 'Capacidade (Kg)' in frota.columns and not frota.empty else 0
                st.metric("Capacidade Total (Kg)", f"{capacidade_total_kg:,.1f}")
            # Adicionar outras métricas relevantes se necessário (e.g., Volume Total)

        st.divider()

        # --- Botão de Cálculo e Execução ---
        if st.button("Calcular Rotas Otimizadas", type="primary", use_container_width=True, key="calcular_rotas_btn"):
            # Validações antes de prosseguir
            if lat_partida is None or lon_partida is None:
                st.error("Erro: Coordenadas de partida inválidas. Verifique a configuração do endereço de partida.")
            elif pedidos_validos.empty:
                st.error("Erro: Nenhum pedido com coordenadas válidas encontrado para roteirizar.")
            elif frota.empty:
                 st.error(f"Erro: A frota está vazia, não é possível calcular rotas para {tipo}.")
            else:
                # --- Validações adicionais antes de calcular matrizes ---
                if tipo == "CVRP":
                    # 1. Demanda maior que qualquer veículo
                    if 'Peso dos Itens' in pedidos_validos.columns and 'Capacidade (Kg)' in frota.columns:
                        demandas_pedidos = pedidos_validos['Peso dos Itens'].fillna(0).astype(float)
                        capacidades_veic = frota['Capacidade (Kg)'].fillna(0).astype(float)
                        max_capacidade = capacidades_veic.max() if not capacidades_veic.empty else 0
                        pedidos_excedentes = pedidos_validos[demandas_pedidos > max_capacidade]
                        if not pedidos_excedentes.empty:
                            st.error(f"Existem pedidos cuja demanda excede a capacidade máxima dos veículos ({max_capacidade:.1f} Kg). Corrija antes de prosseguir.")
                            st.dataframe(pedidos_excedentes, use_container_width=True)
                            return
                # Preparar dados comuns para todos os solvers
                depot_coord = (lat_partida, lon_partida)
                customer_coords = pedidos_validos[['Latitude', 'Longitude']].values.tolist()
                all_locations = [depot_coord] + customer_coords
                depot_index = 0 # Índice do depósito na lista all_locations

                matriz_distancias = None

                # Calcular Matriz de Distâncias (necessária para VRP, CVRP, TSP e cálculo final de distância)
                with st.spinner("Calculando matriz de distâncias..."):
                    try:
                        n = len(all_locations)
                        
                        # Placeholders para a barra de progresso e texto de status da matriz
                        progress_bar_matriz = st.progress(0, text="Iniciando cálculo da matriz de distâncias...")
                        status_text_matriz = st.empty()
                        start_time_matriz = time.time()

                        # Callback para a função calcular_matriz_distancias
                        def callback_matriz_dist(progresso_atual): # progresso_atual é um float de 0.0 a 1.0
                            progress_bar_matriz.progress(progresso_atual)
                            elapsed_matriz = time.time() - start_time_matriz
                            elapsed_formatted_matriz = time.strftime('%H:%M:%S', time.gmtime(elapsed_matriz))
                            
                            texto_status = f"Calculando matriz de distâncias: {int(progresso_atual*100)}% | Decorrido: {elapsed_formatted_matriz}"
                            if progresso_atual > 0 and progresso_atual < 1.0:
                                try:
                                    total_estimado_matriz = elapsed_matriz / progresso_atual
                                    restante_estimado_matriz = total_estimado_matriz - elapsed_matriz
                                    if restante_estimado_matriz > 0:
                                        restante_formatted_matriz = time.strftime('%H:%M:%S', time.gmtime(restante_estimado_matriz))
                                        texto_status += f" | Restante est.: {restante_formatted_matriz}"
                                except ZeroDivisionError:
                                    pass # Evita divisão por zero no início
                            status_text_matriz.text(texto_status)

                        # Chamada única para calcular a matriz completa
                        matriz_distancias = calcular_matriz_distancias(all_locations, metrica='distance', progress_callback=callback_matriz_dist)
                        
                        # Limpa o texto de status após a conclusão
                        if matriz_distancias is not None:
                            status_text_matriz.text(f"Cálculo da matriz de distâncias ({matriz_distancias.shape}) finalizado em {time.strftime('%H:%M:%S', time.gmtime(time.time() - start_time_matriz))}.")
                        else:
                            status_text_matriz.text("Falha no cálculo da matriz de distâncias.")
                        # A barra de progresso pode ser deixada em 100% ou removida com st.empty() se o placeholder for guardado
                        # progress_bar_matriz.empty() # Opcional: remover a barra após conclusão

                        if matriz_distancias is None:
                             st.error("Falha crítica ao calcular a matriz de distâncias completa.")
                             # matriz_distancias já é None, não precisa reatribuir
                        elif np.any(matriz_distancias >= INFINITE_VALUE): # Usar INFINITE_VALUE importado
                             st.warning("A matriz de distâncias contém valores infinitos ou impossíveis para alguns pares. Verifique as coordenadas dos pedidos e do depósito. O solver tentará prosseguir.")
                             # Não retorna, permite que o solver tente lidar com isso.
                        else:
                             st.success(f"Matriz de distâncias ({matriz_distancias.shape}) calculada com sucesso.")
                    except Exception as e:
                        st.error(f"Erro durante o cálculo da matriz de distâncias: {e}")
                        st.exception(e) # Adiciona o traceback para depuração
                        matriz_distancias = None
                
                # Prosseguir apenas se as matrizes necessárias estiverem prontas
                matriz_ok = (matriz_distancias is not None)

                if matriz_ok:
                    rotas = None
                    rotas_df = pd.DataFrame() # Inicializa dataframe vazio
                    resultado_solver = None # Para armazenar o dict do VRPTW ou o DataFrame dos outros
                    status_solver = "Não executado"

                    with st.spinner(f"Executando o solver {tipo}..."):
                        try:
                            if tipo == "CVRP":
                                # CVRP também minimiza distância, mas considera capacidade
                                if 'Peso dos Itens' not in pedidos_validos.columns:
                                    st.error("Coluna 'Peso dos Itens' necessária para CVRP não encontrada nos pedidos.")
                                    raise ValueError("Faltando 'Peso dos Itens'")
                                elif 'Capacidade (Kg)' not in frota.columns:
                                     st.error("Coluna 'Capacidade (Kg)' necessária para CVRP não encontrada na frota.")
                                     raise ValueError("Faltando 'Capacidade (Kg)'")
                                else:
                                     rotas = solver_cvrp(
                                         pedidos_validos, frota, matriz_distancias,
                                         pos_processamento=aplicar_pos,
                                         tipo_heuristica=tipo_heuristica if aplicar_pos else '2opt',
                                         kwargs_heuristica={"max_paradas_por_subrota": max_paradas_split} if aplicar_pos and tipo_heuristica == "split" else {},
                                         ajuste_capacidade_pct=ajuste_capacidade_pct
                                     )
                                     rotas_df = rotas # Resultado já é DataFrame
                                     status_solver = "OK" if rotas_df is not None and not rotas_df.empty else "Falha ou Sem Solução"
                            elif tipo == "CVRP Flex":
                                rotas = solver_cvrp_flex(
                                    pedidos_validos, frota, matriz_distancias, depot_index=depot_index, ajuste_capacidade_pct=ajuste_capacidade_pct,
                                    pos_processamento=aplicar_pos,
                                    tipo_heuristica=tipo_heuristica if aplicar_pos else '2opt',
                                    kwargs_heuristica={"max_paradas_por_subrota": max_paradas_split} if aplicar_pos and tipo_heuristica == "split" else {}
                                )
                                # Se o solver retornar dict, tenta extrair o DataFrame
                                if isinstance(rotas, dict):
                                    # Tenta extrair a chave 'rotas' ou 'routes' ou converter o maior DataFrame do dict
                                    if 'rotas' in rotas:
                                        rotas_df = rotas['rotas']
                                    elif 'routes' in rotas:
                                        rotas_df = rotas['routes']
                                    else:
                                        # Procura o maior DataFrame no dict
                                        dfs = [v for v in rotas.values() if isinstance(v, pd.DataFrame)]
                                        rotas_df = dfs[0] if dfs else pd.DataFrame()
                                else:
                                    rotas_df = rotas
                                status_solver = "OK" if rotas_df is not None and isinstance(rotas_df, pd.DataFrame) and not rotas_df.empty else "Falha ou Sem Solução"

                        except ValueError as ve:
                             st.error(f"Erro de dados ao preparar para {tipo}: {ve}")
                             status_solver = f"Erro de Dados: {ve}"
                             rotas_df = None
                             st.session_state['rotas_calculadas'] = None
                             st.session_state['mapa_necessario'] = False
                        except Exception as solver_error:
                             st.error(f"Erro durante a execução do solver {tipo}: {solver_error}")
                             st.exception(solver_error)
                             status_solver = f"Erro Solver: {solver_error}"
                             rotas_df = None
                             st.session_state['rotas_calculadas'] = None
                             st.session_state['mapa_necessario'] = False

                        # Relatório automático de causas para inviabilidade
                        if status_solver and ("INFEASIBLE" in str(status_solver).upper() or "NENHUMA SOLUÇÃO" in str(status_solver).upper() or "Falha" in str(status_solver)):
                            st.warning("\n**Diagnóstico automático para problema inviável:**\n\n- Verifique se algum pedido tem demanda maior que a capacidade máxima dos veículos.\n- Revise as janelas de tempo dos veículos e pedidos (se existirem).\n- Confira se todos os pedidos possuem coordenadas válidas e não há outliers muito distantes.\n- Certifique-se de que a frota é suficiente para atender todos os pedidos.\n- Tente relaxar restrições (aumentar janelas, frota, capacidade) e rode novamente.\n\nSe o problema persistir, revise os dados de entrada e tente com um conjunto menor de pedidos.")

                    if rotas_df is not None and not rotas_df.empty:
                        from routing.pos_processamento import balanceamento_iterativo, reservar_veiculos_para_regioes, mover_para_vizinho_proximo, sugerir_agrupamento_ml


                        # Priorizar regiões preferidas da frota (restrição dura)

                        from routing.pos_processamento import priorizar_regioes_preferidas, restringir_1_regiao_por_veiculo, realocar_pedidos_restritos
                        # Ajuste do raio máximo pode ser feito aqui:
                        raio_max_km = 20  # Altere conforme necessidade operacional
                        rotas_df, n_realocados = priorizar_regioes_preferidas(rotas_df, frota, pedidos_validos)
                        if n_realocados > 0:
                            st.info(f"{n_realocados} pedidos foram realocados para veículos com regiões preferidas.")

                        # Restringir cada veículo a até 2 regiões próximas
                        rotas_df = restringir_1_regiao_por_veiculo(rotas_df, raio_km=raio_max_km, pedidos=pedidos_validos)
                        n_restritos = rotas_df['Alocacao_Restrita'].sum() if 'Alocacao_Restrita' in rotas_df.columns else 0
                        if n_restritos > 0:
                            st.warning(f"{n_restritos} pedidos estão fora das regiões permitidas do veículo e foram marcados como restritos.")

                        # Realocação automática de pedidos restritos
                        rotas_df, n_realocados_restritos = realocar_pedidos_restritos(rotas_df, frota, pedidos_validos, raio_km=raio_max_km)
                        if n_realocados_restritos > 0:
                            st.success(f"{n_realocados_restritos} pedidos restritos foram realocados automaticamente para veículos vizinhos com capacidade e região compatível.")
                        n_restritos_final = rotas_df['Alocacao_Restrita'].sum() if 'Alocacao_Restrita' in rotas_df.columns else 0
                        if n_restritos_final > 0:
                            st.warning(f"{n_restritos_final} pedidos permanecem restritos após tentativa de realocação automática.")

                        # ML agrupamento (placeholder)
                        if usar_ml:
                            pedidos_validos = sugerir_agrupamento_ml(pedidos_validos)
                            st.info("Agrupamento sugerido por ML aplicado (experimental).")
                        # Reserva de veículos para regiões críticas
                        if usar_reserva_regioes:
                            rotas_df = reservar_veiculos_para_regioes(rotas_df, frota, pedidos_validos, n_reservas=min(2, len(frota)))
                            st.info("Reserva de veículos para regiões críticas aplicada.")
                        # Balanceamento iterativo (peso, paradas, região)
                        if balanceamento_auto:
                            rotas_df = balanceamento_iterativo(rotas_df, frota, pedidos_validos, matriz_distancias)
                            st.info("Balanceamento avançado aplicado: peso, paradas, região e vizinhança.")
                        # Heurística de vizinhança extra (opcional)
                        if usar_vizinhanca:
                            rotas_df = mover_para_vizinho_proximo(rotas_df, matriz_distancias)
                            st.info("Heurística de vizinhança aplicada após balanceamento.")

                        # --- Checagem de excesso de carga (ajuste conforme slider) ---
                        from routing.pos_processamento import checar_e_corrigir_excesso_carga
                        rotas_df, excesso_final = checar_e_corrigir_excesso_carga(rotas_df, frota, limite_pct=ajuste_capacidade_pct)
                        if excesso_final:
                            st.error(f"Atenção: Alguns veículos ultrapassaram o limite de {ajuste_capacidade_pct}% da capacidade após o balanceamento!")
                            for veic, demanda, cap in excesso_final:
                                st.warning(f"Veículo {veic}: {demanda:.1f} kg (limite: {cap:.1f} kg)")

                        # Propaga a coluna 'Região' dos pedidos para rotas_df, se existir
                        if 'Pedido_Index_DF' in rotas_df.columns and 'Região' in pedidos_validos.columns:
                            try:
                                regioes_to_merge = pedidos_validos.reset_index(drop=True).reset_index()[['index', 'Região']].copy()
                                regioes_to_merge = regioes_to_merge.rename(columns={'index': 'Pedido_Index_DF'})
                                rotas_df = pd.merge(
                                    rotas_df,
                                    regioes_to_merge,
                                    on='Pedido_Index_DF',
                                    how='left',
                                    suffixes=(None, '_pedido')
                                )
                            except Exception as merge_reg_err:
                                st.warning(f"Não foi possível adicionar a coluna 'Região' ao DataFrame de rotas: {merge_reg_err}")

                        if 'Pedido_Index_DF' in rotas_df.columns and not pedidos_validos.empty:
                            try:
                                coords_to_merge = pedidos_validos.reset_index(drop=True).reset_index()[['index', 'Latitude', 'Longitude']].copy()
                                coords_to_merge = coords_to_merge.rename(columns={'index': 'Pedido_Index_DF'})
                                rotas_df = pd.merge(
                                    rotas_df,
                                    coords_to_merge,
                                    on='Pedido_Index_DF',
                                    how='left',
                                    suffixes=(None, '_pedido')
                                )
                                st.info("Coordenadas adicionadas ao DataFrame de rotas.")
                            except Exception as merge_err:
                                st.warning(f"Não foi possível adicionar coordenadas ao DataFrame de rotas: {merge_err}")
                        else:
                             st.warning("Não foi possível adicionar coordenadas ao DataFrame de rotas (coluna 'Pedido_Index_DF' ou 'pedidos_validos' ausente/vazio).")

                        with st.expander("Visualizar Tabela de Rotas Geradas (com Coordenadas)", expanded=True):
                            st.dataframe(rotas_df, use_container_width=True)

                        # --- Botões de Exportação ---
                        st.markdown("### Exportar Rotas Otimizadas")
                        col_exp1, col_exp2 = st.columns(2)
                        with col_exp1:
                            if st.button("Exportar para CSV", key="exportar_csv_btn"):
                                from routing.pos_processamento import exportar_rotas_para_csv
                                try:
                                    exportar_rotas_para_csv(rotas_df.values.tolist(), "/workspaces/WazeLog/data/Roteirizacao_exportada.csv")
                                    st.success("Rotas exportadas para CSV com sucesso!")
                                except Exception as e:
                                    st.error(f"Erro ao exportar para CSV: {e}")
                        with col_exp2:
                            if st.button("Exportar para GeoJSON", key="exportar_geojson_btn"):
                                from routing.pos_processamento import exportar_rotas_para_geojson
                                try:
                                    # Para GeoJSON, precisa das coordenadas dos nós
                                    coords = [(row['Latitude'], row['Longitude']) for _, row in rotas_df.iterrows() if not pd.isnull(row['Latitude']) and not pd.isnull(row['Longitude'])]
                                    exportar_rotas_para_geojson([coords], "/workspaces/WazeLog/data/Roteirizacao_exportada.geojson")
                                    st.success("Rotas exportadas para GeoJSON com sucesso!")
                                except Exception as e:
                                    st.error(f"Erro ao exportar para GeoJSON: {e}")

                        # <<< DEBUGGING >>>
                        st.write("--- Debug Info para Cálculo de Distância ---")
                        st.write(f"Tipo de matriz_distancias: {type(matriz_distancias)}")
                        if isinstance(matriz_distancias, (list, np.ndarray)):
                            try:
                                st.write(f"Shape/Len de matriz_distancias: {np.array(matriz_distancias).shape}")
                            except Exception as e:
                                st.write(f"Erro ao obter shape da matriz: {e}")
                        else:
                            st.write("matriz_distancias não é lista ou array numpy.")
                        st.write(f"Tipo de rotas_df: {type(rotas_df)}")
                        if isinstance(rotas_df, pd.DataFrame):
                            st.write(f"rotas_df está vazio: {rotas_df.empty}")
                            st.write(f"Colunas em rotas_df: {rotas_df.columns.tolist()}")
                            st.write(f"\'Veículo\' nas colunas: {'Veículo' in rotas_df.columns}")
                            st.write(f"\'Node_Index_OR\' nas colunas: {'Node_Index_OR' in rotas_df.columns}")
                        else:
                            st.write("rotas_df não é um DataFrame.")
                        st.write("--- Fim Debug Info ---")
                        # <<< END DEBUGGING >>>

                        distancia_total_real_m = 0
                        # Adicionado isinstance(rotas_df, pd.DataFrame) e not rotas_df.empty para segurança
                        if matriz_distancias is not None and isinstance(rotas_df, pd.DataFrame) and not rotas_df.empty and 'Veículo' in rotas_df.columns and 'Node_Index_OR' in rotas_df.columns:
                            try:
                                for veiculo, rota_veiculo in rotas_df.groupby('Veículo'):
                                    rota_veiculo = rota_veiculo.sort_values('Sequencia')
                                    node_indices = [depot_index] + rota_veiculo['Node_Index_OR'].tolist() + [depot_index]
                                    distancia_rota = 0
                                    for i in range(len(node_indices) - 1):
                                        idx_from = node_indices[i]
                                        idx_to = node_indices[i+1]
                                        if 0 <= idx_from < matriz_distancias.shape[0] and 0 <= idx_to < matriz_distancias.shape[1]:
                                            distancia_rota += matriz_distancias[idx_from, idx_to] # Acesso NumPy
                                        else:
                                            st.warning(f"Índice fora dos limites ao calcular distância da rota: de {idx_from} para {idx_to}. Shape da matriz: {matriz_distancias.shape}")
                                            distancia_rota += INFINITE_VALUE # Penaliza se o índice estiver errado
                                    distancia_total_real_m += distancia_rota
                                st.metric("Distância Total Real (Calculada)", f"{distancia_total_real_m / 1000:,.1f} km")
                            except Exception as calc_dist_e:
                                st.warning(f"Não foi possível calcular a distância total real a partir das rotas: {calc_dist_e}")
                                distancia_total_real_m = None
                        else:
                             # Mensagem de aviso movida para cá e ajustada
                             if isinstance(rotas_df, pd.DataFrame) and rotas_df.empty:
                                 st.info("Nenhuma rota foi gerada pelo solver, portanto a distância total não pode ser calculada.")
                             else:
                                 st.warning("Matriz de distâncias ou colunas necessárias não disponíveis para calcular a distância total real.")
                             distancia_total_real_m = None # Garante que seja None se não calculado

                        # --- Calcular e Exibir Resumo por Veículo ---
                        peso_total_empenhado_kg = 0
                        if isinstance(rotas_df, pd.DataFrame) and not rotas_df.empty and 'Veículo' in rotas_df.columns and 'Demanda' in rotas_df.columns:
                            resumo_veiculos = rotas_df.groupby('Veículo')['Demanda'].sum().reset_index()
                            resumo_veiculos = resumo_veiculos.rename(columns={'Demanda': 'Peso Empenhado (Kg)'})
                            peso_total_empenhado_kg = resumo_veiculos['Peso Empenhado (Kg)'].sum()

                            # Tentar merge com frota para obter capacidade
                            try:
                                # Identificar a coluna de ID correta na frota (prioriza 'ID Veículo')
                                id_col_frota = 'ID Veículo' if 'ID Veículo' in frota.columns else 'Placa'
                                if id_col_frota in frota.columns and 'Capacidade (Kg)' in frota.columns:
                                    frota_capacidade = frota[[id_col_frota, 'Capacidade (Kg)']].copy()
                                    # Renomear a coluna de ID da frota para corresponder à coluna 'Veículo' do resumo
                                    frota_capacidade = frota_capacidade.rename(columns={id_col_frota: 'Veículo'})
                                    resumo_veiculos = pd.merge(resumo_veiculos, frota_capacidade, on='Veículo', how='left')
                                    # Calcular % de Ocupação
                                    resumo_veiculos['Ocupação (%)'] = (
                                        (resumo_veiculos['Peso Empenhado (Kg)'] / resumo_veiculos['Capacidade (Kg)'] * 100)
                                        .fillna(0)
                                        .round(1)
                                    )
                                else:
                                    st.warning("Não foi possível encontrar 'ID Veículo'/'Placa' ou 'Capacidade (Kg)' na frota para adicionar ao resumo.")
                                    resumo_veiculos['Capacidade (Kg)'] = None
                                    resumo_veiculos['Ocupação (%)'] = None

                                with st.expander("Resumo de Carga por Veículo", expanded=False):
                                    st.dataframe(resumo_veiculos, use_container_width=True, hide_index=True)
                            except Exception as resumo_err:
                                st.warning(f"Erro ao gerar resumo por veículo: {resumo_err}")
                        # --- Fim Resumo por Veículo ---

                        cenario = {
                            'data': pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S'),
                            'tipo': tipo,
                            'rotas': rotas_df,
                            'qtd_pedidos_roteirizados': len(pedidos_validos),
                            'qtd_veiculos_utilizados': rotas_df['Veículo'].nunique() if isinstance(rotas_df, pd.DataFrame) and not rotas_df.empty else 0,
                            'qtd_veiculos_disponiveis': len(frota),
                            'peso_total_empenhado_kg': peso_total_empenhado_kg, # Adicionado
                            'distancia_total_real_m': distancia_total_real_m,
                            'custo_solver_sec': None, # Placeholder
                            'tempo_operacao_sec': None, # Placeholder
                            'status_solver': status_solver,
                            'endereco_partida': endereco_partida,
                            'lat_partida': lat_partida,
                            'lon_partida': lon_partida,
                            'pedidos_nao_alocados': pedidos_nao_alocados
                        }
                        st.session_state.cenarios_roteirizacao.insert(0, cenario)
                    else:
                        st.info(f"Nenhuma rota gerada para {tipo}. Status: {status_solver}")

                        # Diagnóstico detalhado para solver sem solução
                        st.warning("""
**Diagnóstico detalhado: Nenhuma rota foi gerada. Possíveis causas:**

- **Pedidos com demanda maior que a capacidade máxima dos veículos:**
    - Verifique se algum pedido tem 'Peso dos Itens' maior que a maior 'Capacidade (Kg)' da frota.
- **Frota vazia ou sem veículos disponíveis:**
    - Confirme se há veículos cadastrados e disponíveis, e se todos têm capacidade maior que zero.
- **Pedidos sem coordenadas válidas:**
    - Todos os pedidos devem ter 'Latitude' e 'Longitude' válidas.
- **Dados inconsistentes ou restrições muito rígidas:**
    - Janelas de tempo, capacidades ou outros parâmetros podem estar impossibilitando a solução.
- **Todos os pedidos já estão alocados ou não há pedidos válidos:**
    - Verifique se há pedidos realmente roteirizáveis.

Se necessário, revise os dados de entrada, relaxe restrições ou tente com um conjunto menor de pedidos.
""")

                else:
                     st.error("Não foi possível calcular as matrizes necessárias (distâncias e/ou tempos). Verifique os erros acima.")

        if not pedidos_nao_alocados.empty:
            st.warning(f"Atenção: {len(pedidos_nao_alocados)} pedidos não possuem coordenadas válidas e não foram incluídos na roteirização.")
            with st.expander("Ver Pedidos Não Roteirizados"):
                 st.dataframe(pedidos_nao_alocados, use_container_width=True)

        st.divider()

        if st.session_state.cenarios_roteirizacao:
            st.subheader("Histórico de Cenários Calculados")
            df_cenarios_display = pd.DataFrame([
                {
                    'Data': c.get('data', ''),
                    'Tipo': c.get('tipo', ''),
                    'Pedidos': c.get('qtd_pedidos_roteirizados', ''),
                    'Veículos': c.get('qtd_veiculos_disponiveis', ''),
                    'Distância Real': f"{c.get('distancia_total_real_m', 0) / 1000:,.1f} km" if c.get('distancia_total_real_m') is not None else "N/A",
                    'Custo Solver (s)': f"{c.get('custo_solver_sec', 0):,.0f}" if c.get('custo_solver_sec') is not None else "N/A",
                    'Tempo Operação (s)': f"{c.get('tempo_operacao_sec', 0):,.0f}" if c.get('tempo_operacao_sec') is not None else "N/A",
                    'Status': c.get('status_solver', 'N/A'),
                }
                for c in st.session_state.cenarios_roteirizacao
            ])
            st.dataframe(df_cenarios_display, use_container_width=True, hide_index=True)

            cenario_indices = range(len(st.session_state.cenarios_roteirizacao))
            selected_idx = st.selectbox(
                "Visualizar detalhes e mapa do cenário:",
                options=cenario_indices,
                format_func=lambda i: f"{df_cenarios_display.iloc[i]['Data']} - {df_cenarios_display.iloc[i]['Tipo']} ({df_cenarios_display.iloc[i]['Pedidos']} pedidos)",
                index=None,
                key="select_cenario_historico"
            )

            if selected_idx is not None:
                cenario_selecionado = st.session_state.cenarios_roteirizacao[selected_idx]
                st.markdown(f"#### Detalhes do Cenário: {cenario_selecionado['data']} ({cenario_selecionado['tipo']})")

                st.write("**Rotas Geradas:**")
                df_rotas_cenario = cenario_selecionado.get('rotas', pd.DataFrame())
                st.dataframe(df_rotas_cenario, use_container_width=True)

                df_nao_alocados_cenario = cenario_selecionado.get('pedidos_nao_alocados', pd.DataFrame())
                if not df_nao_alocados_cenario.empty:
                    st.write("**Pedidos Não Roteirizados neste Cenário:**")
                    st.dataframe(df_nao_alocados_cenario, use_container_width=True)

                if not df_rotas_cenario.empty:
                    st.write("**Mapa da Rota:**")
                    if 'Latitude' in df_rotas_cenario.columns and 'Longitude' in df_rotas_cenario.columns:
                        df_map = df_rotas_cenario.dropna(subset=["Latitude", "Longitude"]).rename(columns={"Latitude": "latitude", "Longitude": "longitude"})
                        st.map(df_map)
                    else:
                        st.info("Não há coordenadas válidas para exibir o mapa da rota.")

                # --- Botão para gerar e baixar relatório HTML ---
                st.markdown("### Relatório Automático")
                if st.button("Gerar Relatório HTML deste Cenário", key="btn_relatorio_html"):
                    html = gerar_relatorio_html(cenario_selecionado)
                    rel_path = f"/workspaces/Wazelog/data/Relatorio_{cenario_selecionado.get('data','').replace(':','-').replace(' ','_')}.html"
                    with open(rel_path, "w", encoding="utf-8") as f:
                        f.write(html)
                    st.success(f"Relatório gerado em {rel_path}")
                    with open(rel_path, "r", encoding="utf-8") as f:
                        st.download_button("Baixar Relatório HTML", f.read(), file_name=os.path.basename(rel_path), mime="text/html")

        # Diagnóstico automático de inviabilidade
        if tipo == "CVRP" and not pedidos_validos.empty and not frota.empty:
            # 1. Pedidos com demanda maior que a capacidade máxima
            if 'Peso dos Itens' in pedidos_validos.columns and 'Capacidade (Kg)' in frota.columns:
                demandas_pedidos = pedidos_validos['Peso dos Itens'].fillna(0).astype(float)
                max_capacidade = frota['Capacidade (Kg)'].max()
                pedidos_excedentes = pedidos_validos[demandas_pedidos > max_capacidade]
                if not pedidos_excedentes.empty:
                    st.warning(f"Pedidos com demanda maior que a capacidade máxima dos veículos ({max_capacidade:.1f} Kg):")
                    st.dataframe(pedidos_excedentes, use_container_width=True)
            # 2. Veículos com capacidade zero ou nula
            if 'Capacidade (Kg)' in frota.columns:
                veiculos_sem_capacidade = frota[frota['Capacidade (Kg)'] <= 0]
                if not veiculos_sem_capacidade.empty:
                    st.warning("Veículos com capacidade zero ou nula:")
                    st.dataframe(veiculos_sem_capacidade, use_container_width=True)
            # 3. Pedidos sem coordenadas
            pedidos_sem_coord = pedidos_validos[pedidos_validos['Latitude'].isna() | pedidos_validos['Longitude'].isna()]
            if not pedidos_sem_coord.empty:
                st.warning("Pedidos sem coordenadas válidas:")
                st.dataframe(pedidos_sem_coord, use_container_width=True)

    except FileNotFoundError as e:
         st.error(f"Erro: Arquivo não encontrado. Verifique se os arquivos de dados ({e.filename}) estão na pasta correta.")
    except ImportError as e:
         st.error(f"Erro de importação: {e}. Verifique se todas as dependências estão instaladas corretamente (`pip install -r requirements.txt`).")
    except Exception as e:
        st.error(f"Ocorreu um erro inesperado na página de roteirização: {e}")
        st.exception(e)