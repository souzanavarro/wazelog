import numpy as np
import pandas as pd
import logging # Adicionado para logging mais estruturado

# Configuração do Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Constantes de Custo Padrão (Exemplo)
DEFAULT_COSTS = {
    'cost_per_km': 1.5,      # Custo por quilômetro rodado (combustível, manutenção, etc.)
    'cost_per_hour': 30.0,   # Custo por hora (salário do motorista, etc.) - aplicado ao tempo de operação
    'fixed_cost_per_vehicle': 50.0, # Custo fixo por veículo utilizado (depreciação, seguro diário, etc.)
    'default_service_time_min': 15, # Tempo de serviço padrão por parada em minutos (usado se não vier do VRPTW)
    'velocidade_media_kmh': 40,   # Velocidade média para estimar tempo de viagem (usado se matriz for distância)
    # 'cost_per_stop': 0.0 # Exemplo: Custo adicional por parada
}

def calcular_distancia_tempo_rota(rota_indices, matriz_distancias, matriz_tempos=None):
    """
    Calcula a distância e o tempo total de uma sequência de índices de nós.
    Se matriz_tempos não for fornecida, estima o tempo a partir da distância e velocidade média.
    """
    distancia = 0
    tempo = 0
    velocidade_media_mps = (DEFAULT_COSTS['velocidade_media_kmh'] * 1000) / 3600 if DEFAULT_COSTS['velocidade_media_kmh'] > 0 else 0

    for i in range(len(rota_indices) - 1):
        idx_from = rota_indices[i]
        idx_to = rota_indices[i+1]

        # Verifica limites da matriz de distâncias
        if not (0 <= idx_from < matriz_distancias.shape[0] and 0 <= idx_to < matriz_distancias.shape[1]):
            logging.warning(f"Índices ({idx_from}, {idx_to}) fora dos limites da matriz de distâncias {matriz_distancias.shape} na rota {rota_indices}.")
            return np.inf, np.inf # Retorna infinito se a rota for inválida

        dist_segmento = matriz_distancias[idx_from, idx_to]
        distancia += dist_segmento

        # Calcula tempo do segmento
        if matriz_tempos is not None:
             # Verifica limites da matriz de tempos
            if not (0 <= idx_from < matriz_tempos.shape[0] and 0 <= idx_to < matriz_tempos.shape[1]):
                 logging.warning(f"Índices ({idx_from}, {idx_to}) fora dos limites da matriz de tempos {matriz_tempos.shape} na rota {rota_indices}.")
                 return np.inf, np.inf
            tempo_segmento = matriz_tempos[idx_from, idx_to]
        elif velocidade_media_mps > 0:
            tempo_segmento = dist_segmento / velocidade_media_mps # Tempo em segundos
        else:
            tempo_segmento = 0 # Não é possível estimar o tempo

        tempo += tempo_segmento

    return distancia, tempo


def simular_cenario(pedidos_roteirizados, frota, matriz_distancias, matriz_tempos=None, custos=None):
    """
    Calcula métricas de desempenho para um cenário de roteirização.

    Args:
        pedidos_roteirizados (pd.DataFrame): DataFrame de pedidos com a coluna 'Veículo' preenchida.
                                             Idealmente, deve conter 'tempo_chegada', 'tempo_saida' (em segundos desde 00:00)
                                             e 'node_index' (índice do nó na matriz, 0=depósito).
        frota (pd.DataFrame): DataFrame da frota.
        matriz_distancias (np.ndarray): Matriz de distâncias (em metros).
        matriz_tempos (np.ndarray, optional): Matriz de tempos de viagem (em segundos). Se None, estima a partir da distância.
        custos (dict, optional): Dicionário com parâmetros de custo. Usa DEFAULT_COSTS se None.

    Returns:
        dict: Dicionário com métricas de desempenho, ou None em caso de erro grave.
    """
    if not isinstance(pedidos_roteirizados, pd.DataFrame) or 'Veículo' not in pedidos_roteirizados.columns:
        logging.error("Erro: 'pedidos_roteirizados' inválido ou sem coluna 'Veículo'.")
        return None
    if not isinstance(matriz_distancias, np.ndarray):
         logging.error("Erro: 'matriz_distancias' inválida.")
         return None
    if matriz_tempos is not None and not isinstance(matriz_tempos, np.ndarray):
         logging.error("Erro: 'matriz_tempos' fornecida mas inválida.")
         return None
    if matriz_tempos is not None and matriz_tempos.shape != matriz_distancias.shape:
         logging.error("Erro: Matriz de tempos e distâncias têm formas diferentes.")
         return None


    custos_usados = custos if custos is not None else DEFAULT_COSTS
    custo_por_hora = custos_usados.get('cost_per_hour', 0)
    custo_por_km = custos_usados.get('cost_per_km', 0)
    custo_fixo_veiculo = custos_usados.get('fixed_cost_per_vehicle', 0)
    tempo_servico_padrao_seg = custos_usados.get('default_service_time_min', 15) * 60

    metricas = {
        'distancia_total_km': 0,
        'tempo_viagem_total_h': 0, # Tempo total apenas de deslocamento
        'tempo_servico_total_h': 0, # Tempo total em paradas
        'tempo_operacao_total_h': 0, # Viagem + Serviço
        'custo_total': 0,
        'veiculos_usados': 0,
        'rotas_info': []
    }

    veiculos_ativos = pedidos_roteirizados['Veículo'].dropna().unique()
    metricas['veiculos_usados'] = len(veiculos_ativos)
    metricas['custo_total'] += metricas['veiculos_usados'] * custo_fixo_veiculo

    # Verifica se a coluna 'node_index' existe, senão tenta usar o índice do DataFrame + 1
    has_node_index_col = 'node_index' in pedidos_roteirizados.columns
    if not has_node_index_col:
        logging.warning("Coluna 'node_index' não encontrada em 'pedidos_roteirizados'. "
                        "Assumindo que o índice do DataFrame + 1 corresponde ao nó na matriz. "
                        "Isso pode ser impreciso se o índice foi resetado.")

    grouped = pedidos_roteirizados.dropna(subset=['Veículo']).groupby('Veículo')

    for veiculo_id, rota_df in grouped:
        # Ordena a rota se possível
        if 'tempo_chegada' in rota_df.columns:
            rota_ordenada_df = rota_df.sort_values('tempo_chegada').copy()
        else:
             logging.warning(f"Sem 'tempo_chegada' para ordenar rota do veículo {veiculo_id}. A ordem pode estar incorreta.")
             rota_ordenada_df = rota_df.copy()

        # Reconstrói a sequência de nós
        try:
            if has_node_index_col:
                # Garante que node_index seja inteiro
                indices_paradas = rota_ordenada_df['node_index'].astype(int).tolist()
            else:
                # Usa a suposição do índice + 1
                indices_paradas = (rota_ordenada_df.index + 1).tolist()

            if not indices_paradas: # Rota vazia após filtros?
                 logging.warning(f"Rota para veículo {veiculo_id} está vazia após ordenação/agrupamento.")
                 continue

            indices_rota_completa = [0] + indices_paradas + [0] # Adiciona depósito
        except (TypeError, ValueError, KeyError) as e:
             logging.error(f"Erro ao obter índices de nós para veículo {veiculo_id}: {e}. Pulando rota.")
             continue

        # Calcula distância e tempo de viagem da rota
        distancia_rota_m, tempo_viagem_seg = calcular_distancia_tempo_rota(
            indices_rota_completa, matriz_distancias, matriz_tempos
        )

        if distancia_rota_m == np.inf or tempo_viagem_seg == np.inf:
             logging.warning(f"Cálculo de distância/tempo falhou para rota do veículo {veiculo_id}. Pulando.")
             continue

        # Calcula tempo de serviço total para a rota
        tempo_servico_total_seg = 0
        if 'tempo_saida' in rota_ordenada_df.columns and 'tempo_chegada' in rota_ordenada_df.columns:
            # Calcula tempo de serviço a partir dos dados VRPTW (tempo_saida - tempo_chegada)
            # Garante que sejam numéricos e não negativos
            tempos_servico = rota_ordenada_df['tempo_saida'] - rota_ordenada_df['tempo_chegada']
            tempos_servico = tempos_servico.apply(lambda x: max(x, 0) if pd.notna(x) else 0)
            tempo_servico_total_seg = tempos_servico.sum()
            if tempo_servico_total_seg <= 0 and len(indices_paradas) > 0:
                 # Se a soma for zero, pode ser que chegada=saida, usa o default
                 logging.debug(f"Tempo de serviço calculado do VRPTW foi zero para {veiculo_id}. Usando default.")
                 tempo_servico_total_seg = len(indices_paradas) * tempo_servico_padrao_seg
        else:
            # Estima tempo de serviço usando o padrão
            tempo_servico_total_seg = len(indices_paradas) * tempo_servico_padrao_seg

        tempo_operacao_seg = tempo_viagem_seg + tempo_servico_total_seg

        # Calcula custo da rota
        custo_distancia = (distancia_rota_m / 1000) * custo_por_km
        custo_tempo = (tempo_operacao_seg / 3600) * custo_por_hora
        # custo_paradas = len(indices_paradas) * custos_usados.get('cost_per_stop', 0) # Exemplo
        custo_rota = custo_distancia + custo_tempo # + custo_paradas

        # Adiciona às métricas totais
        metricas['distancia_total_km'] += distancia_rota_m / 1000
        metricas['tempo_viagem_total_h'] += tempo_viagem_seg / 3600
        metricas['tempo_servico_total_h'] += tempo_servico_total_seg / 3600
        metricas['tempo_operacao_total_h'] += tempo_operacao_seg / 3600
        metricas['custo_total'] += custo_rota

        # Guarda informações da rota individual
        metricas['rotas_info'].append({
            'veiculo_id': veiculo_id,
            'num_paradas': len(indices_paradas),
            'distancia_km': distancia_rota_m / 1000,
            'tempo_viagem_h': tempo_viagem_seg / 3600,
            'tempo_servico_h': tempo_servico_total_seg / 3600,
            'tempo_operacao_h': tempo_operacao_seg / 3600,
            'custo_estimado': custo_rota,
            'sequencia_indices': indices_rota_completa
        })

    return metricas


def calcular_custos(pedidos_roteirizados, frota, matriz_distancias, matriz_tempos=None, custos=None):
    """
    Calcula o custo total da roteirização. Wrapper para simular_cenario.
    """
    metricas = simular_cenario(pedidos_roteirizados, frota, matriz_distancias, matriz_tempos, custos)
    if metricas and 'custo_total' in metricas:
        return metricas['custo_total']
    logging.warning("Cálculo de custos falhou ou retornou resultado inválido.")
    return 0.0


def balancear_carga(rotas_info, frota, matriz_distancias, matriz_tempos=None, demandas=None, capacidade_veiculo=None):
    """
    Tenta balancear a carga movendo uma parada da rota mais longa para a mais curta.
    Heurística muito simples, pode não ser ótima e requer dados adicionais.

    Args:
        rotas_info (list): Lista de dicionários, como a gerada por `simular_cenario['rotas_info']`.
        frota (pd.DataFrame): DataFrame da frota.
        matriz_distancias (np.ndarray): Matriz de distâncias.
        matriz_tempos (np.ndarray, optional): Matriz de tempos.
        demandas (dict or list/array, optional): Demandas por nó (índice=nó). Necessário para verificar capacidade.
        capacidade_veiculo (int or float, optional): Capacidade padrão do veículo. Necessário se `demandas` for fornecido.

    Returns:
        list: A lista `rotas_info` potencialmente modificada.
    """
    if not rotas_info or len(rotas_info) < 2:
        logging.info("Balanceamento de carga requer pelo menos duas rotas.")
        return rotas_info # Nada a fazer

    # Ordena rotas por tempo de operação (ou distância se tempo não disponível)
    key_sort = 'tempo_operacao_h' if 'tempo_operacao_h' in rotas_info[0] else 'distancia_km'
    rotas_ordenadas = sorted(rotas_info, key=lambda x: x.get(key_sort, 0))

    rota_mais_curta = rotas_ordenadas[0]
    rota_mais_longa = rotas_ordenadas[-1]

    # Verifica se há paradas para mover na rota mais longa (além do depósito)
    if rota_mais_longa.get('num_paradas', 0) <= 0:
        logging.info("Rota mais longa não tem paradas para mover.")
        return rotas_info

    # Pega a última parada da rota mais longa (antes do depósito final)
    indice_no_mover = rota_mais_longa['sequencia_indices'][-2]

    # Verifica se o nó a mover é válido
    if indice_no_mover == 0: # Não mover o depósito
         logging.warning("Tentativa de mover depósito no balanceamento.")
         return rotas_info

    # Verifica capacidade se demandas e capacidade foram fornecidas
    if demandas is not None and capacidade_veiculo is not None:
        try:
            demanda_no = demandas[indice_no_mover]

            # Calcula demanda atual da rota mais curta
            demanda_atual_curta = sum(demandas[node] for node in rota_mais_curta['sequencia_indices'] if node != 0)

            if demanda_atual_curta + demanda_no > capacidade_veiculo:
                logging.info(f"Balanceamento: Mover nó {indice_no_mover} excede capacidade da rota {rota_mais_curta['veiculo_id']}.")
                return rotas_info # Não move
        except (KeyError, IndexError, TypeError) as e:
            logging.warning(f"Erro ao verificar demandas/capacidade no balanceamento: {e}. Não foi possível balancear com restrição.")
            # Prossegue sem garantia de capacidade se houve erro
            pass


    # Cria as novas sequências propostas
    nova_seq_longa = rota_mais_longa['sequencia_indices'][:-2] + [0] # Remove a última parada e o depósito final, adiciona depósito
    nova_seq_curta = rota_mais_curta['sequencia_indices'][:-1] + [indice_no_mover] + [0] # Insere antes do depósito final

    # Recalcula distância/tempo das rotas modificadas
    dist_orig_longa, tempo_orig_longa = calcular_distancia_tempo_rota(rota_mais_longa['sequencia_indices'], matriz_distancias, matriz_tempos)
    dist_orig_curta, tempo_orig_curta = calcular_distancia_tempo_rota(rota_mais_curta['sequencia_indices'], matriz_distancias, matriz_tempos)

    dist_nova_longa, tempo_nova_longa = calcular_distancia_tempo_rota(nova_seq_longa, matriz_distancias, matriz_tempos)
    dist_nova_curta, tempo_nova_curta = calcular_distancia_tempo_rota(nova_seq_curta, matriz_distancias, matriz_tempos)

    # Verifica se o movimento é válido e se melhora (ou não piora muito) o total
    if np.inf not in [dist_nova_longa, tempo_nova_longa, dist_nova_curta, tempo_nova_curta]:
        delta_dist = (dist_nova_longa + dist_nova_curta) - (dist_orig_longa + dist_orig_curta)
        delta_tempo = (tempo_nova_longa + tempo_nova_curta) - (tempo_orig_longa + tempo_orig_curta)

        # Critério de aceitação: não piorar muito a distância total (ex: tolerância de 10%)
        TOLERANCIA_DIST = 0.10
        dist_total_original = dist_orig_longa + dist_orig_curta
        if delta_dist <= dist_total_original * TOLERANCIA_DIST:
            logging.info(f"Balanceamento: Movendo nó {indice_no_mover} da rota {rota_mais_longa['veiculo_id']} para {rota_mais_curta['veiculo_id']}. Delta Dist: {delta_dist:.2f}m")

            # Atualiza as informações das rotas modificadas na lista original
            # Encontra os dicts originais e atualiza 'sequencia_indices' e outras métricas recalculadas
            for i, info in enumerate(rotas_info):
                if info['veiculo_id'] == rota_mais_longa['veiculo_id']:
                    rotas_info[i]['sequencia_indices'] = nova_seq_longa
                    # Recalcular e atualizar outras métricas (dist, tempo, custo) seria ideal aqui
                    # Por simplicidade, apenas atualizamos a sequência por enquanto
                    rotas_info[i]['num_paradas'] -= 1
                    break
            for i, info in enumerate(rotas_info):
                 if info['veiculo_id'] == rota_mais_curta['veiculo_id']:
                    rotas_info[i]['sequencia_indices'] = nova_seq_curta
                    rotas_info[i]['num_paradas'] += 1
                    break
            # Idealmente, chamar simular_cenario novamente com as rotas atualizadas
            return rotas_info # Retorna a lista modificada
        else:
            logging.info(f"Balanceamento: Mover nó {indice_no_mover} aumentaria muito a distância total ({delta_dist:.2f}m). Não movendo.")
    else:
        logging.warning("Balanceamento: Erro ao recalcular distância/tempo das rotas propostas.")

    return rotas_info # Retorna original se não houve mudança


# Exemplo de uso
if __name__ == '__main__':
    print("--- Exemplo de Simulação e Cálculo de Custos ---")

    # Criar dados de exemplo
    pedidos_ex = pd.DataFrame({
        'ID Pedido': [1, 2, 3, 4],
        'Endereco': ['End 1', 'End 2', 'End 3', 'End 4'],
        'Peso': [10, 20, 15, 25],
        # Colunas adicionadas pela roteirização (exemplo)
        'Veículo': ['V1', 'V2', 'V1', 'V2'],
        'tempo_chegada': [30000, 33000, 36000, 39000], # Exemplo em segundos desde meia-noite (8:20, 9:10, 10:00, 10:50)
        'tempo_saida': [30900, 33900, 36900, 39900], # Adicionando 15 min (900s) de serviço
        'node_index': [1, 2, 3, 4] # Índice do nó correspondente na matriz
    })

    frota_ex = pd.DataFrame({
        'ID Veículo': ['V1', 'V2'],
        'Capacidade': [50, 50]
    })

    # Matriz de distâncias (metros)
    matriz_dist_ex = np.array([
      # D, P1, P2, P3, P4
        [0, 10000, 12000, 15000, 18000], # Depot
        [10000, 0, 5000, 7000, 9000], # P1
        [12000, 5000, 0, 4000, 10000], # P2
        [15000, 7000, 4000, 0, 6000], # P3
        [18000, 9000, 10000, 6000, 0]  # P4
    ], dtype=int)

    # Matriz de tempos (segundos) - pode ser None
    matriz_tempo_ex = (matriz_dist_ex / (DEFAULT_COSTS['velocidade_media_kmh'] * 1000 / 3600)).astype(int) # Estimativa baseada na velocidade
    matriz_tempo_ex[matriz_tempo_ex < 0] = 0 # Garante não negativo

    # Custos personalizados (opcional)
    custos_ex = {
        'cost_per_km': 1.8,
        'cost_per_hour': 35.0,
        'fixed_cost_per_vehicle': 60.0,
        'default_service_time_min': 10 # Usado se tempos VRPTW não disponíveis
    }

    print("\n1. Simulando cenário com custos personalizados:")
    metricas_simulacao = simular_cenario(pedidos_ex, frota_ex, matriz_dist_ex, matriz_tempos=matriz_tempo_ex, custos=custos_ex)

    if metricas_simulacao:
        print(f"  - Veículos Usados: {metricas_simulacao.get('veiculos_usados')}")
        print(f"  - Distância Total: {metricas_simulacao.get('distancia_total_km', 0):.2f} km")
        print(f"  - Tempo Viagem Total: {metricas_simulacao.get('tempo_viagem_total_h', 0):.2f} h")
        print(f"  - Tempo Serviço Total: {metricas_simulacao.get('tempo_servico_total_h', 0):.2f} h")
        print(f"  - Tempo Operação Total: {metricas_simulacao.get('tempo_operacao_total_h', 0):.2f} h")
        print(f"  - Custo Total Estimado: R$ {metricas_simulacao.get('custo_total', 0):.2f}")
        print("  - Detalhes das Rotas:")
        for rota_info in metricas_simulacao.get('rotas_info', []):
            print(f"    - Veículo: {rota_info['veiculo_id']}, Paradas: {rota_info['num_paradas']}, "
                  f"Dist: {rota_info['distancia_km']:.2f} km, T.Viag: {rota_info['tempo_viagem_h']:.2f} h, "
                  f"T.Serv: {rota_info['tempo_servico_h']:.2f} h, T.Op: {rota_info['tempo_operacao_h']:.2f} h, "
                  f"Custo: R$ {rota_info['custo_estimado']:.2f}, Seq: {rota_info['sequencia_indices']}")
    else:
        print("  - Falha na simulação.")

    print("\n2. Calculando apenas o custo total com custos padrão:")
    custo_total_padrao = calcular_custos(pedidos_ex, frota_ex, matriz_dist_ex, matriz_tempos=matriz_tempo_ex) # Usa DEFAULT_COSTS
    print(f"  - Custo Total Estimado (Padrão): R$ {custo_total_padrao:.2f}")

    print("\n3. Testando balanceamento de carga:")
    # Demandas exemplo (índice = nó)
    demandas_ex = {0: 0, 1: 10, 2: 20, 3: 15, 4: 25}
    capacidade_ex = 50
    rotas_info_antes = metricas_simulacao.get('rotas_info', [])
    print(f"  - Rotas antes (Sequências): {[r['sequencia_indices'] for r in rotas_info_antes]}")
    rotas_info_depois = balancear_carga(rotas_info_antes, frota_ex, matriz_dist_ex, matriz_tempo_ex, demandas=demandas_ex, capacidade_veiculo=capacidade_ex)
    print(f"  - Rotas depois (Sequências): {[r['sequencia_indices'] for r in rotas_info_depois]}")
    # Para ver o efeito real, seria necessário re-simular com as rotas_info_depois