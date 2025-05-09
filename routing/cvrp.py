# Função auxiliar: solver CVRP por cluster/região
def solver_cvrp_por_cluster(pedidos, frota, matriz_distancias, pos_processamento=None, coluna_cluster='Cluster', **kwargs):
    """
    Executa o solver CVRP separadamente para cada cluster/região, concatenando o resultado.
    - pedidos: DataFrame de pedidos, deve conter coluna de cluster/região.
    - frota: DataFrame de frota (pode ser a mesma para todos os clusters).
    - matriz_distancias: matriz de distâncias global (deve ser numpy array ou lista de listas, depósito na posição 0).
    - coluna_cluster: nome da coluna de cluster/região (default: 'Cluster').
    - kwargs: argumentos extras para o solver_cvrp.
    Retorna: DataFrame concatenado das rotas, com coluna do cluster.
    """
    import pandas as pd
    import numpy as np
    from .cvrp import solver_cvrp
    if coluna_cluster not in pedidos.columns:
        raise ValueError(f"Coluna '{coluna_cluster}' não encontrada nos pedidos para roteirização por cluster.")
    resultados = []
    clusters = pedidos[coluna_cluster].dropna().unique()
    for cluster in clusters:
        pedidos_cluster = pedidos[pedidos[coluna_cluster] == cluster].copy()
        if pedidos_cluster.empty:
            continue
        # Monta nova matriz de distâncias: depósito + pedidos do cluster
        indices_pedidos = pedidos_cluster.index.tolist()
        # O depósito é sempre o índice 0 na matriz global
        indices_matriz = [0] + [i+1 for i in indices_pedidos]  # +1 pois matriz inclui depósito
        matriz_cluster = np.array(matriz_distancias)[np.ix_(indices_matriz, indices_matriz)]
        # Rodar solver para este cluster
        rotas_df = solver_cvrp(pedidos_cluster.reset_index(drop=True), frota, matriz_cluster, pos_processamento=pos_processamento, **kwargs)
        if not rotas_df.empty:
            rotas_df[coluna_cluster] = cluster
            # Ajusta Node_Index_OR para o índice global (opcional, para rastreabilidade)
            if 'Node_Index_OR' in rotas_df.columns:
                # Mapear do índice local para global
                node_map = {i+1: idx+1 for i, idx in enumerate(indices_pedidos)}
                node_map[0] = 0
                rotas_df['Node_Index_OR_Global'] = rotas_df['Node_Index_OR'].map(node_map)
            resultados.append(rotas_df)
    if resultados:
        return pd.concat(resultados, ignore_index=True)
    else:
        return pd.DataFrame()
def solver_cvrp(pedidos, frota, matriz_distancias, pos_processamento=None, **kwargs):
    # Validação automática das coordenadas dos pedidos e do depósito
    from routing.utils import validar_coordenadas_dataframe
    ok_coord, msg_coord, df_invalidos = validar_coordenadas_dataframe(pedidos, lat_col='Latitude', lon_col='Longitude', nome_df='Pedidos')
    if not ok_coord:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"CVRP Solver: {msg_coord}")
        # Opcional: salvar ou exibir as linhas inválidas
        return pd.DataFrame() # Retorna DataFrame vazio se houver coordenadas inválidas
    """Capacitated VRP: considera a capacidade máxima de carga dos veículos além da roteirização.
    Aceita argumentos extras para compatibilidade retroativa.
    """
    import pandas as pd
    from ortools.constraint_solver import pywrapcp, routing_enums_pb2
    import numpy as np
    import logging # Adicionado para logging

    logger = logging.getLogger(__name__) # Configura logger

    if pedidos.empty:
        logger.warning("CVRP Solver: DataFrame de pedidos vazio.")
        return pd.DataFrame() # Retorna DataFrame vazio
    if frota.empty:
        logger.warning("CVRP Solver: DataFrame de frota vazio.")
        return pd.DataFrame() # Retorna DataFrame vazio
    if not isinstance(matriz_distancias, (list, np.ndarray)) or len(matriz_distancias) == 0:
        logger.error("CVRP Solver: Matriz de distâncias inválida ou vazia.")
        return pd.DataFrame() # Retorna DataFrame vazio

    pedidos = pedidos.copy().reset_index(drop=True)
    frota = frota.copy().reset_index(drop=True)

    n_pedidos = len(pedidos)
    n_veiculos = len(frota)
    depot_index = 0 # Assumindo que o depósito é sempre o índice 0 na matriz_distancias

    # --- Preparação dos Dados para OR-Tools ---
    # Demanda (garantir que seja numérica e tratar NaNs)
    if 'Peso dos Itens' in pedidos.columns:
        demands_series = pd.to_numeric(pedidos['Peso dos Itens'], errors='coerce').fillna(1)
    elif 'Qtde. dos Itens' in pedidos.columns:
        demands_series = pd.to_numeric(pedidos['Qtde. dos Itens'], errors='coerce').fillna(1)
    else:
        logger.warning("CVRP Solver: Coluna de demanda ('Peso dos Itens' ou 'Qtde. dos Itens') não encontrada. Usando demanda 1 para todos.")
        demands_series = pd.Series([1] * n_pedidos)
    # Adiciona 0 para o depósito no início da lista de demandas
    demands = [0] + demands_series.astype(int).tolist()

    # Capacidade (garantir que seja numérica e tratar NaNs/zeros)
    if 'Capacidade (Kg)' in frota.columns:
        capacities_series = pd.to_numeric(frota['Capacidade (Kg)'], errors='coerce').fillna(1)
    elif 'Capacidade (Cx)' in frota.columns:
        capacities_series = pd.to_numeric(frota['Capacidade (Cx)'], errors='coerce').fillna(1)
    else:
        logger.warning("CVRP Solver: Coluna de capacidade ('Capacidade (Kg)' ou 'Capacidade (Cx)') não encontrada. Usando capacidade 1000 para todos.")
        capacities_series = pd.Series([1000] * n_veiculos)
    # Garante que capacidade seja pelo menos 1
    capacities = capacities_series.astype(int).clip(lower=1).tolist()

    # Matriz de distâncias (já deve incluir o depósito no índice 0)
    distance_matrix = np.array(matriz_distancias).astype(int).tolist() # Garante formato lista de listas de int
    num_locations = len(distance_matrix)

    if num_locations != n_pedidos + 1:
         logger.error(f"CVRP Solver: Inconsistência no tamanho da matriz de distâncias ({num_locations}) vs número de pedidos+depósito ({n_pedidos + 1}).")
         return pd.DataFrame()

    # --- Configuração do OR-Tools ---
    try:
        manager = pywrapcp.RoutingIndexManager(num_locations, n_veiculos, depot_index)
        routing = pywrapcp.RoutingModel(manager)

        # Callback de Distância
        def distance_callback(from_index, to_index):
            from_node = manager.IndexToNode(from_index)
            to_node = manager.IndexToNode(to_index)
            # Validação de índices
            if 0 <= from_node < num_locations and 0 <= to_node < num_locations:
                return distance_matrix[from_node][to_node]
            else:
                logger.error(f"Índice fora dos limites no distance_callback: {from_node}, {to_node}")
                return 9999999 # Retorna um valor alto para penalizar rotas inválidas
        transit_callback_index = routing.RegisterTransitCallback(distance_callback)
        routing.SetArcCostEvaluatorOfAllVehicles(transit_callback_index)

        # Callback de Demanda e Dimensão de Capacidade
        def demand_callback(from_index):
            from_node = manager.IndexToNode(from_index)
            # Validação de índices
            if 0 <= from_node < len(demands):
                return demands[from_node]
            else:
                 logger.error(f"Índice fora dos limites no demand_callback: {from_node}")
                 return 0 # Retorna 0 para evitar falhas, mas indica problema
        demand_callback_index = routing.RegisterUnaryTransitCallback(demand_callback)
        routing.AddDimensionWithVehicleCapacity(
            demand_callback_index,
            0,  # Sem folga de capacidade
            capacities,  # Capacidades máximas dos veículos
            True,  # Começar cumulativo em zero
            'Capacity'
        )
        capacity_dimension = routing.GetDimensionOrDie('Capacity')

    except Exception as e:
        logger.error(f"Erro na configuração do OR-Tools: {e}")
        return pd.DataFrame()

    # --- Parâmetros de Busca ---
    search_parameters = pywrapcp.DefaultRoutingSearchParameters()
    search_parameters.first_solution_strategy = (
        routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC
    )
    search_parameters.local_search_metaheuristic = (
        routing_enums_pb2.LocalSearchMetaheuristic.GUIDED_LOCAL_SEARCH
    )
    search_parameters.time_limit.seconds = 30 # Adiciona um limite de tempo

    # --- Resolução ---
    logger.info("Iniciando a resolução do CVRP com OR-Tools...")
    solution = routing.SolveWithParameters(search_parameters)
    logger.info("Resolução do CVRP concluída.")

    # --- Montagem do Resultado ---
    routes_data = []
    if solution:
        logger.info("Solução encontrada. Processando rotas...")
        total_distance_solution = 0
        pedidos_roteirizados_indices = set()

        for vehicle_id in range(n_veiculos):
            index = routing.Start(vehicle_id)
            sequence = 1 # Começa a sequência em 1 para o primeiro cliente
            vehicle_identifier = (
                frota['ID Veículo'].iloc[vehicle_id]
                if 'ID Veículo' in frota.columns and not frota.empty else
                frota['Placa'].iloc[vehicle_id] if 'Placa' in frota.columns and not frota.empty else f'veiculo_{vehicle_id+1}'
            )
            route_distance_vehicle = 0
            route_load_vehicle = 0

            while not routing.IsEnd(index):
                node_index = manager.IndexToNode(index)
                load_var = capacity_dimension.CumulVar(index)
                current_load = solution.Value(load_var)

                if node_index != depot_index: # Não adiciona o depósito como uma parada na sequência
                    pedido_original_index = node_index - 1 # Ajusta para índice do DataFrame 'pedidos'
                    if 0 <= pedido_original_index < n_pedidos:
                        # Verifica se o pedido já foi roteirizado (não deveria acontecer com CVRP padrão)
                        if pedido_original_index in pedidos_roteirizados_indices:
                             logger.warning(f"Pedido {pedido_original_index} aparecendo em múltiplas rotas (Veículo {vehicle_identifier}). Verifique a lógica.")
                        else:
                            pedidos_roteirizados_indices.add(pedido_original_index)
                            pedido_info = pedidos.iloc[pedido_original_index]
                            routes_data.append({
                                'Veículo': vehicle_identifier,
                                'Sequencia': sequence,
                                'Node_Index_OR': node_index, # Índice do nó no OR-Tools (inclui depósito)
                                'Pedido_Index_DF': pedido_original_index, # Índice no DataFrame 'pedidos' original
                                'ID Pedido': pedido_info.get('ID Pedido', f'Pedido_{pedido_original_index}'),
                                'Cliente': pedido_info.get('Cliente', 'N/A'),
                                'Endereço': pedido_info.get('Endereço', 'N/A'),
                                'Demanda': demands[node_index],
                                'Carga_Acumulada': current_load,
                                # Adicionar Lat/Lon aqui pode ser útil, mas será feito merge depois
                            })
                            sequence += 1
                            route_load_vehicle += demands[node_index] # Soma a demanda do nó atual
                    else:
                         logger.warning(f"Índice de pedido inválido ({pedido_original_index}) encontrado na rota do veículo {vehicle_identifier}.")

                previous_index = index
                index = solution.Value(routing.NextVar(index))
                # Calcula a distância do arco
                arc_distance = routing.GetArcCostForVehicle(previous_index, index, vehicle_id)
                route_distance_vehicle += arc_distance

            # Adiciona a distância do último nó de volta ao depósito (se houver rota)
            if routing.IsEnd(index) and manager.IndexToNode(previous_index) != depot_index:
                 end_node_index = routing.End(vehicle_id)
                 arc_distance = routing.GetArcCostForVehicle(previous_index, end_node_index, vehicle_id)
                 route_distance_vehicle += arc_distance

            if sequence > 1: # Se o veículo fez alguma entrega
                 logger.info(f"Veículo {vehicle_identifier}: {sequence-1} paradas, Carga={route_load_vehicle}, Dist={route_distance_vehicle/1000:.1f}km")
                 total_distance_solution += route_distance_vehicle

        rotas_df = pd.DataFrame(routes_data)

        if rotas_df.empty:
             logger.warning("Solver CVRP encontrou uma solução, mas nenhuma rota válida foi gerada (talvez nenhum pedido atribuído).")
        else:
             logger.info(f"Total de {len(rotas_df)} paradas distribuídas.")
             logger.info(f"Distância total (solução OR-Tools): {total_distance_solution / 1000:.1f} km")
             # Verifica se todos os pedidos foram roteirizados
             pedidos_nao_roteirizados = n_pedidos - len(pedidos_roteirizados_indices)
             if pedidos_nao_roteirizados > 0:
                  logger.warning(f"{pedidos_nao_roteirizados} pedidos não foram incluídos nas rotas pela solução.")

        return rotas_df

    else:
        logger.warning("Solver CVRP não encontrou solução.")
        status_map = {
            routing.ROUTING_NOT_SOLVED: 'NOT_SOLVED',
            routing.ROUTING_FAIL: 'FAIL',
            routing.ROUTING_FAIL_TIMEOUT: 'FAIL_TIMEOUT',
            routing.ROUTING_INVALID: 'INVALID',
        }
        logger.warning(f"Status da solução: {routing.status()} ({status_map.get(routing.status(), 'UNKNOWN')})")
        # Tentar fornecer mais detalhes sobre a inviabilidade, se possível
        # (Ex: verificar se alguma demanda excede capacidade, etc. - já feito na página)
        return pd.DataFrame() # Retorna DataFrame vazio em caso de falha

# Remover código antigo que modificava 'pedidos' diretamente
# ...