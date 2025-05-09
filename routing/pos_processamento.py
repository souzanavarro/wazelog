def realocar_pedidos_restritos(rotas_df, frota, pedidos, raio_km=20):
    # Garante que a frota tenha as colunas de janela de tempo e preenche valores padrão se necessário
    if 'Janela Início' not in frota.columns:
        frota['Janela Início'] = '05:00'
    else:
        frota['Janela Início'] = frota['Janela Início'].fillna('05:00').replace('', '05:00')
    if 'Janela Fim' not in frota.columns:
        frota['Janela Fim'] = '18:00'
    else:
        frota['Janela Fim'] = frota['Janela Fim'].fillna('18:00').replace('', '18:00')

    # Garante que rotas_df tenha as colunas de janela de tempo do pedido
    if 'Janela Início' not in rotas_df.columns:
        rotas_df['Janela Início'] = '05:00'
    else:
        rotas_df['Janela Início'] = rotas_df['Janela Início'].fillna('05:00').replace('', '05:00')
    if 'Janela Fim' not in rotas_df.columns:
        rotas_df['Janela Fim'] = '18:00'
    else:
        rotas_df['Janela Fim'] = rotas_df['Janela Fim'].fillna('18:00').replace('', '18:00')

    # Define id_col antes de qualquer uso
    id_col = 'ID Veículo' if 'ID Veículo' in frota.columns else 'Placa'

    # Cria dicionário de janelas da frota
    janela_inicio_frota = frota.set_index(id_col)['Janela Início'].to_dict()
    janela_fim_frota = frota.set_index(id_col)['Janela Fim'].to_dict()

    # Marca como restrito todo pedido cuja janela não está contida na janela do veículo
    for idx, row in rotas_df.iterrows():
        veic = row['Veículo']
        if pd.isnull(veic):
            continue
        janela_ini_ped = row['Janela Início'] if 'Janela Início' in row else '05:00'
        janela_fim_ped = row['Janela Fim'] if 'Janela Fim' in row else '18:00'
        janela_ini_veic = janela_inicio_frota.get(veic, '05:00')
        janela_fim_veic = janela_fim_frota.get(veic, '18:00')
        # Compara horários (formato HH:MM)
        try:
            from datetime import datetime
            fmt = '%H:%M'
            ini_ped = datetime.strptime(str(janela_ini_ped), fmt)
            fim_ped = datetime.strptime(str(janela_fim_ped), fmt)
            ini_veic = datetime.strptime(str(janela_ini_veic), fmt)
            fim_veic = datetime.strptime(str(janela_fim_veic), fmt)
            # Se pedido começa antes do veículo ou termina depois do veículo, marca como restrito
            if ini_ped < ini_veic or fim_ped > fim_veic:
                rotas_df.at[idx, 'Alocacao_Restrita'] = True
                logging.warning(f"Pedido {idx} com janela [{janela_ini_ped}-{janela_fim_ped}] não cabe na janela do veículo {veic} [{janela_ini_veic}-{janela_fim_veic}]. Marcado como restrito.")
        except Exception as e:
            logging.warning(f"Erro ao comparar janelas de tempo para pedido {idx}: {e}")
    """
    Tenta realocar pedidos marcados como Alocacao_Restrita para outros veículos que atendam até 2 regiões próximas (por nome e raio) e tenham capacidade disponível.
    Remove a marcação se conseguir realocar. Retorna o DataFrame atualizado e o número de realocações.
    """
    from geopy.distance import geodesic
    import numpy as np
    import logging
    # Validação e padronização das colunas essenciais
    col_essenciais = ['Região', 'Latitude', 'Longitude', 'Veículo', 'Demanda']
    for col in col_essenciais:
        if col not in rotas_df.columns:
            logging.error(f"Coluna obrigatória '{col}' ausente em rotas_df. Abortando realocação.")
            return rotas_df, 0
    if pedidos is None or 'Região' not in pedidos.columns or 'Latitude' not in pedidos.columns or 'Longitude' not in pedidos.columns:
        logging.error("Pedidos DataFrame ausente ou sem colunas essenciais. Abortando realocação.")
        return rotas_df, 0
    # Padroniza nomes de regiões (strip, title)
    rotas_df['Região'] = rotas_df['Região'].astype(str).str.strip().str.title()
    pedidos['Região'] = pedidos['Região'].astype(str).str.strip().str.title()
    # Converte coordenadas para float e remove linhas inválidas
    rotas_df['Latitude'] = pd.to_numeric(rotas_df['Latitude'], errors='coerce')
    rotas_df['Longitude'] = pd.to_numeric(rotas_df['Longitude'], errors='coerce')
    pedidos['Latitude'] = pd.to_numeric(pedidos['Latitude'], errors='coerce')
    pedidos['Longitude'] = pd.to_numeric(pedidos['Longitude'], errors='coerce')
    # Remove pedidos restritos sem coordenadas válidas
    pedidos_restritos = rotas_df[(rotas_df['Alocacao_Restrita'] == True) & rotas_df['Latitude'].notnull() & rotas_df['Longitude'].notnull()]
    if pedidos_restritos.empty:
        logging.info("Nenhum pedido restrito com coordenadas válidas para realocação.")
        return rotas_df, 0
    id_col = 'ID Veículo' if 'ID Veículo' in frota.columns else 'Placa'
    capacidades = frota.set_index(id_col)['Capacidade (Kg)'].to_dict() if 'Capacidade (Kg)' in frota.columns else {}
    realocados = 0
    for idx, row in pedidos_restritos.iterrows():
        lat = row['Latitude']
        lon = row['Longitude']
        reg_pedido = row['Região']
        demanda = row['Demanda'] if 'Demanda' in row else 0
        veic_atual = row['Veículo']
        if pd.isnull(lat) or pd.isnull(lon) or not reg_pedido or pd.isnull(veic_atual):
            logging.warning(f"Pedido restrito ignorado por dados faltantes: idx={idx}, regiao={reg_pedido}, lat={lat}, lon={lon}, veic_atual={veic_atual}")
            continue
        melhor_veic = None
        for veic in rotas_df['Veículo'].unique():
            if veic == veic_atual:
                continue
            pedidos_veic = rotas_df[rotas_df['Veículo'] == veic]
            if pedidos_veic.empty:
                continue
            regioes_pred = pedidos_veic['Região'].value_counts().index[:2].tolist()
            centroides = []
            for reg in regioes_pred:
                pedidos_regiao = pedidos[pedidos['Região'] == reg]
                if not pedidos_regiao.empty and 'Latitude' in pedidos_regiao.columns and 'Longitude' in pedidos_regiao.columns:
                    lat_centroide = pedidos_regiao['Latitude'].mean()
                    lon_centroide = pedidos_regiao['Longitude'].mean()
                    centroides.append((reg, (lat_centroide, lon_centroide)))
            permitido = False
            for reg, (lat_c, lon_c) in centroides:
                if reg_pedido == reg:
                    dist = geodesic((lat, lon), (lat_c, lon_c)).km
                    if dist <= raio_km:
                        permitido = True
                        break
            if not permitido:
                continue
            cap = capacidades.get(veic, None)
            carga_atual = rotas_df[rotas_df['Veículo'] == veic]['Demanda'].sum() if 'Demanda' in rotas_df.columns else 0
            if cap is not None and carga_atual + demanda <= cap:
                melhor_veic = veic
                break
        if melhor_veic:
            rotas_df.at[idx, 'Veículo'] = melhor_veic
            rotas_df.at[idx, 'Alocacao_Restrita'] = False
            realocados += 1
    return rotas_df, realocados
def restringir_1_regiao_por_veiculo(rotas_df, raio_km=20, pedidos=None):
    """
    Para cada veículo, identifica a região predominante e só permite pedidos dentro de um raio máximo (em km)
    do centroide da região predominante. Pedidos fora desse raio são marcados como restritos.
    """
    from geopy.distance import geodesic
    import numpy as np
    if rotas_df is None or rotas_df.empty or 'Veículo' not in rotas_df.columns or 'Região' not in rotas_df.columns:
        return rotas_df
    if pedidos is None or 'Latitude' not in rotas_df.columns or 'Longitude' not in rotas_df.columns:
        # fallback: só restringe por nome de região
        for veic in rotas_df['Veículo'].unique():
            pedidos_veic = rotas_df[rotas_df['Veículo'] == veic]
            if pedidos_veic.empty:
                continue
            regiao_pred = pedidos_veic['Região'].mode().iloc[0]
            fora_regiao = pedidos_veic[pedidos_veic['Região'] != regiao_pred]
            for idx in fora_regiao.index:
                rotas_df.at[idx, 'Alocacao_Restrita'] = True
                logging.warning(f"Pedido {rotas_df.at[idx, 'Pedido_Index_DF']} está fora da região predominante '{regiao_pred}' do veículo {veic}.")
        return rotas_df
    # Com coordenadas e DataFrame de pedidos
    for veic in rotas_df['Veículo'].unique():
        pedidos_veic = rotas_df[rotas_df['Veículo'] == veic]
        if pedidos_veic.empty:
            continue
        # Identifica até 2 regiões predominantes
        regioes_pred = pedidos_veic['Região'].value_counts().index[:2].tolist()
        # Calcula centroides das 2 regiões
        centroides = []
        for reg in regioes_pred:
            pedidos_regiao = pedidos[pedidos['Região'] == reg]
            if not pedidos_regiao.empty and 'Latitude' in pedidos_regiao.columns and 'Longitude' in pedidos_regiao.columns:
                lat_centroide = pedidos_regiao['Latitude'].mean()
                lon_centroide = pedidos_regiao['Longitude'].mean()
                centroides.append((reg, (lat_centroide, lon_centroide)))
        for idx, row in pedidos_veic.iterrows():
            lat = row['Latitude']
            lon = row['Longitude']
            reg_pedido = row['Região']
            if np.isnan(lat) or np.isnan(lon):
                rotas_df.at[idx, 'Alocacao_Restrita'] = True
                continue
            # Permite se o pedido está em uma das 2 regiões predominantes E dentro do raio
            permitido = False
            for reg, (lat_c, lon_c) in centroides:
                if reg_pedido == reg:
                    dist = geodesic((lat, lon), (lat_c, lon_c)).km
                    if dist <= raio_km:
                        permitido = True
                        break
            if not permitido:
                rotas_df.at[idx, 'Alocacao_Restrita'] = True
                logging.warning(f"Pedido {row['Pedido_Index_DF']} está fora das 2 regiões predominantes do veículo {veic} ou além do raio permitido.")
    return rotas_df
def priorizar_regioes_preferidas(rotas_df, frota, pedidos):
    """
    Move pedidos para veículos que tenham a região do pedido em suas 'Regiões Preferidas' (restrição dura).
    Se não houver capacidade, aloca para o veículo cuja região preferida seja mais próxima.
    Se ainda assim não couber, aloca para qualquer veículo disponível.
    """
    import pandas as pd
    import numpy as np
    from geopy.distance import geodesic
    if rotas_df is None or rotas_df.empty or 'Veículo' not in rotas_df.columns or 'Pedido_Index_DF' not in rotas_df.columns:
        return rotas_df, 0
    if 'Região' not in pedidos.columns:
        return rotas_df, 0
    id_col = 'ID Veículo' if 'ID Veículo' in frota.columns else 'Placa'
    regioes_pref_dict = {}
    regioes_centroides = {}
    for _, row in frota.iterrows():
        veic = row.get(id_col)
        regioes_pref = row.get('Regiões Preferidas', '')
        regioes_pref_list = [r.strip().lower() for r in str(regioes_pref).split(',') if r.strip()]
        regioes_pref_dict[veic] = regioes_pref_list
        # Calcula centroide das regiões preferidas do veículo
        for reg in regioes_pref_list:
            if reg and reg not in regioes_centroides and reg in pedidos['Região'].str.lower().values:
                pedidos_reg = pedidos[pedidos['Região'].str.lower() == reg]
                if not pedidos_reg.empty:
                    lat = pedidos_reg['Latitude'].mean()
                    lon = pedidos_reg['Longitude'].mean()
                    regioes_centroides[reg] = (lat, lon)
    pedido_regiao = pedidos['Região'].fillna('').astype(str).str.lower().tolist()
    pedido_lat = pedidos['Latitude'].tolist() if 'Latitude' in pedidos.columns else None
    pedido_lon = pedidos['Longitude'].tolist() if 'Longitude' in pedidos.columns else None
    capacidades = frota.set_index(id_col)['Capacidade (Kg)'].to_dict() if 'Capacidade (Kg)' in frota.columns else {}
    realocados = 0
    for idx, row in rotas_df.iterrows():
        veic_atual = row['Veículo']
        pedido_idx = row['Pedido_Index_DF']
        if pd.isnull(pedido_idx):
            continue
        pedido_idx = int(pedido_idx)
        regiao_pedido = pedido_regiao[pedido_idx] if pedido_idx < len(pedido_regiao) else ''
        lat_pedido = pedido_lat[pedido_idx] if pedido_lat and pedido_idx < len(pedido_lat) else None
        lon_pedido = pedido_lon[pedido_idx] if pedido_lon and pedido_idx < len(pedido_lon) else None
        if not regiao_pedido:
            continue
        # 1. Tenta alocar para veículos preferenciais (restrição dura)
        veics_pref = [v for v, regs in regioes_pref_dict.items() if regiao_pedido in regs]
        demanda = row['Demanda'] if 'Demanda' in row else 0
        melhor_veic = None
        menor_carga = None
        for v in veics_pref:
            cap = capacidades.get(v, None)
            if cap is None:
                continue
            carga_atual = rotas_df[rotas_df['Veículo'] == v]['Demanda'].sum() if 'Demanda' in rotas_df.columns else 0
            if carga_atual + demanda > cap:
                continue
            if menor_carga is None or carga_atual < menor_carga:
                melhor_veic = v
                menor_carga = carga_atual
        if melhor_veic and melhor_veic != veic_atual:
            rotas_df.at[idx, 'Veículo'] = melhor_veic
            realocados += 1
            continue
        # 2. Se não couber, busca veículo cuja região preferida seja mais próxima (restrição dura)
        if veics_pref and not melhor_veic:
            min_dist = None
            veic_mais_proximo = None
            for v, regs in regioes_pref_dict.items():
                for reg in regs:
                    if reg in regioes_centroides and lat_pedido is not None and lon_pedido is not None:
                        dist = geodesic((lat_pedido, lon_pedido), regioes_centroides[reg]).km
                        cap = capacidades.get(v, None)
                        carga_atual = rotas_df[rotas_df['Veículo'] == v]['Demanda'].sum() if 'Demanda' in rotas_df.columns else 0
                        if cap is not None and carga_atual + demanda <= cap:
                            if min_dist is None or dist < min_dist:
                                min_dist = dist
                                veic_mais_proximo = v
            if veic_mais_proximo and veic_mais_proximo != veic_atual:
                rotas_df.at[idx, 'Veículo'] = veic_mais_proximo
                realocados += 1
                continue
        # 3. Fallback: NÃO permite alocação para veículos fora das regiões preferidas
        # Ou seja, pedidos que não couberem em nenhum veículo preferencial permanecem como estão
        # (Opcional: pode-se marcar esses pedidos para análise posterior)
        # Exemplo de log para pedidos não alocados:
        if not veics_pref or (veics_pref and not melhor_veic and not veic_mais_proximo):
            logging.warning(f"Pedido {pedido_idx} (região '{regiao_pedido}') NÃO será alocado: nenhum veículo com região preferida disponível/capaz. Veículo atual: {veic_atual}.")
            # Opcional: marcar para análise
            rotas_df.at[idx, 'Alocacao_Restrita'] = True
            continue
    return rotas_df, realocados
import numpy as np
import itertools
import logging
import pandas as pd
import json

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def calcular_distancia_rota(rota, matriz_distancias):
    """
    Calcula a distância total de uma rota.
    Args:
        rota (list): Lista de índices dos nós visitados.
        matriz_distancias (np.ndarray): Matriz de distâncias.
    Returns:
        float: Distância total da rota ou np.inf se inválida.
    """
    distancia = 0
    for i in range(len(rota) - 1):
        idx_from = rota[i]
        idx_to = rota[i+1]
        if 0 <= idx_from < matriz_distancias.shape[0] and 0 <= idx_to < matriz_distancias.shape[1]:
            distancia += matriz_distancias[idx_from, idx_to]
        else:
            logging.warning(f"Índices ({idx_from}, {idx_to}) fora dos limites da matriz {matriz_distancias.shape} na rota {rota}.")
            return np.inf
    return distancia

def heuristica_2opt(rota, matriz_distancias):
    """
    Melhora a rota usando a heurística 2-opt.
    Assume que a rota começa e termina no depósito (índice 0).
    """
    if len(rota) <= 3:
        return rota
    melhor_rota = rota[:]
    melhor_distancia = calcular_distancia_rota(melhor_rota, matriz_distancias)
    if melhor_distancia == np.inf:
        logging.warning("Rota inicial inválida para 2-opt.")
        return rota
    melhorou = True
    while melhorou:
        melhorou = False
        for i in range(1, len(melhor_rota) - 2):
            for j in range(i + 1, len(melhor_rota) - 1):
                nova_rota = melhor_rota[:i] + melhor_rota[i:j+1][::-1] + melhor_rota[j+1:]
                nova_distancia = calcular_distancia_rota(nova_rota, matriz_distancias)
                if nova_distancia < melhor_distancia:
                    melhor_rota = nova_rota
                    melhor_distancia = nova_distancia
                    melhorou = True
                    break
            if melhorou:
                break
    return melhor_rota

def heuristica_3opt(rota, matriz_distancias):
    """
    Melhora a rota usando a heurística 3-opt (placeholder: usa 2-opt).
    """
    logging.info("heuristica_3opt está usando 2-opt como fallback.")
    return heuristica_2opt(rota, matriz_distancias)

def swap(rota, i, j):
    """
    Troca dois pontos (nós) da rota.
    Args:
        rota (list): Rota original.
        i (int): Índice do primeiro nó.
        j (int): Índice do segundo nó.
    Returns:
        list: Nova rota com os nós trocados.
    """
    if 0 < i < len(rota) -1 and 0 < j < len(rota) -1 and i != j:
        nova_rota = rota[:]
        nova_rota[i], nova_rota[j] = nova_rota[j], nova_rota[i]
        return nova_rota
    logging.warning(f"Índices de swap inválidos ({i}, {j}) para rota de tamanho {len(rota)}.")
    return rota

def split(rota, max_paradas_por_subrota):
    """
    Divide a rota em sub-rotas baseadas em um número máximo de paradas.
    Args:
        rota (list): Rota original.
        max_paradas_por_subrota (int): Máximo de paradas por sub-rota.
    Returns:
        list: Lista de sub-rotas.
    """
    if not isinstance(rota, list) or not rota:
        logging.warning("Rota inválida para split.")
        return []
    if rota[0] != 0 or rota[-1] != 0:
        logging.warning("Rota para split deve começar e terminar no depósito (0).")
        return [rota]
    if len(rota) <= 2:
        return [rota] if len(rota) > 0 else []
    if max_paradas_por_subrota <= 0:
        logging.warning("max_paradas_por_subrota deve ser positivo.")
        return [rota]
    sub_rotas = []
    paradas_atuais = [rota[0]]
    for parada in rota[1:-1]:
        paradas_atuais.append(parada)
        if len(paradas_atuais) -1 >= max_paradas_por_subrota:
            paradas_atuais.append(rota[0])
            sub_rotas.append(paradas_atuais)
            paradas_atuais = [rota[0]]
    if len(paradas_atuais) > 1:
        paradas_atuais.append(rota[0])
        sub_rotas.append(paradas_atuais)
    return sub_rotas

def merge(rotas, matriz_distancias, capacidade_maxima=None, demandas=None):
    """
    Tenta unir rotas adjacentes ou curtas se a combinação for viável e vantajosa.
    Args:
        rotas (list): Lista de rotas (listas de índices).
        matriz_distancias (np.ndarray): Matriz de distâncias.
        capacidade_maxima (float, opcional): Capacidade máxima da rota combinada.
        demandas (list, opcional): Lista de demandas por nó.
    Returns:
        list: Lista de rotas otimizadas.
    """
    if not isinstance(rotas, list) or len(rotas) <= 1:
        return rotas
    if demandas is not None and not isinstance(demandas, (list, np.ndarray)):
        logging.warning("'demandas' deve ser uma lista ou array numpy.")
        return rotas
    rotas_otimizadas = [r[:] for r in rotas if isinstance(r, list) and len(r) >= 2 and r[0] == 0 and r[-1] == 0]
    if len(rotas_otimizadas) <= 1:
        return rotas_otimizadas
    melhorou = True
    while melhorou:
        melhorou = False
        melhor_combinacao = None
        maior_economia = 0
        for i in range(len(rotas_otimizadas)):
            for j in range(i + 1, len(rotas_otimizadas)):
                rota_a = rotas_otimizadas[i]
                rota_b = rotas_otimizadas[j]
                nova_rota_ab = rota_a[:-1] + rota_b[1:]
                demanda_total_ab = 0
                valida_ab = True
                if demandas is not None:
                    try:
                        demanda_total_ab = sum(demandas[node] for node in nova_rota_ab if node != 0)
                    except (IndexError, TypeError):
                        valida_ab = False
                if valida_ab and (capacidade_maxima is None or demanda_total_ab <= capacidade_maxima):
                    dist_orig_a = calcular_distancia_rota(rota_a, matriz_distancias)
                    dist_orig_b = calcular_distancia_rota(rota_b, matriz_distancias)
                    if dist_orig_a != np.inf and dist_orig_b != np.inf:
                        nova_dist_ab = calcular_distancia_rota(nova_rota_ab, matriz_distancias)
                        if nova_dist_ab != np.inf:
                            economia_ab = (dist_orig_a + dist_orig_b) - nova_dist_ab
                            if economia_ab > maior_economia:
                                maior_economia = economia_ab
                                melhor_combinacao = (i, j, nova_rota_ab, economia_ab)
                nova_rota_ba = rota_b[:-1] + rota_a[1:]
                demanda_total_ba = 0
                valida_ba = True
                if demandas is not None:
                    try:
                        demanda_total_ba = sum(demandas[node] for node in nova_rota_ba if node != 0)
                    except (IndexError, TypeError):
                        valida_ba = False
                if valida_ba and (capacidade_maxima is None or demanda_total_ba <= capacidade_maxima):
                    dist_orig_a = calcular_distancia_rota(rota_a, matriz_distancias)
                    dist_orig_b = calcular_distancia_rota(rota_b, matriz_distancias)
                    if dist_orig_a != np.inf and dist_orig_b != np.inf:
                        nova_dist_ba = calcular_distancia_rota(nova_rota_ba, matriz_distancias)
                        if nova_dist_ba != np.inf:
                            economia_ba = (dist_orig_a + dist_orig_b) - nova_dist_ba
                            if economia_ba > maior_economia:
                                maior_economia = economia_ba
                                melhor_combinacao = (i, j, nova_rota_ba, economia_ba)
        if melhor_combinacao is not None:
            idx_a, idx_b, rota_combinada, economia = melhor_combinacao
            indices_para_remover = sorted([idx_a, idx_b], reverse=True)
            try:
                rotas_otimizadas.pop(indices_para_remover[0])
                rotas_otimizadas.pop(indices_para_remover[1])
                rotas_otimizadas.append(rota_combinada)
                melhorou = True
            except IndexError:
                logging.error("Erro ao remover rotas durante o merge. Parando.")
                melhorou = False
        else:
            melhorou = False
    return rotas_otimizadas

def exportar_rotas_para_csv(rotas, filepath):
    """
    Exporta uma lista de rotas para um arquivo CSV.
    Args:
        rotas (list): Lista de rotas (listas de índices).
        filepath (str): Caminho do arquivo CSV.
    """
    df = pd.DataFrame({'rota': rotas})
    df.to_csv(filepath, index=False, encoding='utf-8')
    logging.info(f"Rotas exportadas para {filepath}")

def exportar_rotas_para_geojson(rotas, coordenadas, filepath):
    """
    Exporta rotas para GeoJSON.
    Args:
        rotas (list): Lista de rotas (listas de índices).
        coordenadas (list): Lista de tuplas (lat, lon) indexadas pelo nó.
        filepath (str): Caminho do arquivo GeoJSON.
    """
    features = []
    for rota in rotas:
        coords = [coordenadas[idx] for idx in rota]
        features.append({
            "type": "Feature",
            "geometry": {
                "type": "LineString",
                "coordinates": [[lon, lat] for lat, lon in coords]
            },
            "properties": {}
        })
    geojson = {"type": "FeatureCollection", "features": features}
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(geojson, f, ensure_ascii=False, indent=2)
    logging.info(f"Rotas exportadas para {filepath} (GeoJSON)")

def balancear_carga_e_usar_todos_veiculos(
    rotas_df, frota, pedidos, max_iter=20, criterio_balanceamento='peso', priorizar_regiao=False
):
    """
    Balanceia a carga entre veículos e tenta garantir que todos os veículos ativos sejam usados.
    Permite balancear por 'peso' (Demanda) ou 'paradas' (número de pedidos).
    Se priorizar_regiao=True, tenta manter pedidos da mesma região juntos.
    """
    import numpy as np
    if rotas_df is None or rotas_df.empty or 'Veículo' not in rotas_df.columns:
        return rotas_df
    veiculos_ativos = frota['ID Veículo'] if 'ID Veículo' in frota.columns else frota['Placa']
    veiculos_ativos = veiculos_ativos.dropna().unique().tolist()
    # Garante que todos os veículos ativos recebam pelo menos um pedido
    for v in veiculos_ativos:
        if v not in rotas_df['Veículo'].unique():
            cargas = rotas_df.groupby('Veículo')['Demanda'].sum()
            v_max = cargas.idxmax()
            pedidos_vmax = rotas_df[rotas_df['Veículo'] == v_max].sort_values('Demanda', ascending=False)
            if not pedidos_vmax.empty:
                pedido_para_mover = pedidos_vmax.iloc[0]
                rotas_df.loc[rotas_df.index == pedido_para_mover.name, 'Veículo'] = v
    # --- Balanceamento ---
    for _ in range(max_iter):
        if criterio_balanceamento == 'paradas':
            cargas = rotas_df.groupby('Veículo').size()
        else:  # padrão: peso
            cargas = rotas_df.groupby('Veículo')['Demanda'].sum()
        v_max = cargas.idxmax()
        v_min = cargas.idxmin()
        if cargas[v_max] - cargas[v_min] < 1:
            break
        # Se priorizar região, tenta mover pedido da região predominante do v_max
        if priorizar_regiao and 'Região' in rotas_df.columns:
            regiao_predominante = rotas_df[rotas_df['Veículo'] == v_max]['Região'].mode().iloc[0]
            pedidos_vmax = rotas_df[(rotas_df['Veículo'] == v_max) & (rotas_df['Região'] == regiao_predominante)]
            if pedidos_vmax.empty:
                pedidos_vmax = rotas_df[rotas_df['Veículo'] == v_max]
        else:
            pedidos_vmax = rotas_df[rotas_df['Veículo'] == v_max]
        pedido_para_mover = pedidos_vmax.iloc[0]
        rotas_df.loc[rotas_df.index == pedido_para_mover.name, 'Veículo'] = v_min
    return rotas_df

def mover_para_vizinho_proximo(rotas_df, matriz_distancias, depot_index=0, max_iter=10):
    """
    Heurística de vizinhança: move pedidos para veículos que já atendem clientes próximos (minimizando distância incremental).
    """
    import numpy as np
    if rotas_df is None or rotas_df.empty or 'Veículo' not in rotas_df.columns or 'Node_Index_OR' not in rotas_df.columns:
        return rotas_df
    for _ in range(max_iter):
        melhorou = False
        for idx, pedido in rotas_df.iterrows():
            veic_atual = pedido['Veículo']
            node_idx = pedido['Node_Index_OR']
            min_delta = None
            melhor_veic = veic_atual
            for veic in rotas_df['Veículo'].unique():
                if veic == veic_atual:
                    continue
                # Calcula distância incremental para inserir o pedido na rota do outro veículo
                rota_veic = rotas_df[rotas_df['Veículo'] == veic]['Node_Index_OR'].tolist()
                if not rota_veic:
                    continue
                # Tenta inserir entre todos pares consecutivos
                for i in range(len(rota_veic)):
                    antes = rota_veic[i-1] if i > 0 else depot_index
                    depois = rota_veic[i]
                    delta = matriz_distancias[antes][node_idx] + matriz_distancias[node_idx][depois] - matriz_distancias[antes][depois]
                    if min_delta is None or delta < min_delta:
                        min_delta = delta
                        melhor_veic = veic
            if melhor_veic != veic_atual and min_delta is not None and min_delta < 0:
                rotas_df.at[idx, 'Veículo'] = melhor_veic
                melhorou = True
        if not melhorou:
            break
    return rotas_df

def reservar_veiculos_para_regioes(rotas_df, frota, pedidos, n_reservas=1):
    """
    Reserva veículos para regiões críticas (com mais pedidos).
    """
    if 'Região' not in pedidos.columns or rotas_df is None or rotas_df.empty:
        return rotas_df
    if 'Região' not in rotas_df.columns:
        raise KeyError("A coluna 'Região' não está presente no DataFrame rotas_df. Verifique os dados de entrada.")
    regioes_criticas = pedidos['Região'].value_counts().head(n_reservas).index.tolist()
    veiculos_ativos = frota['ID Veículo'] if 'ID Veículo' in frota.columns else frota['Placa']
    veiculos_ativos = veiculos_ativos.dropna().unique().tolist()
    for i, reg in enumerate(regioes_criticas):
        if i < len(veiculos_ativos):
            veic = veiculos_ativos[i]
            idxs = rotas_df[rotas_df['Região'] == reg].index
            rotas_df.loc[idxs, 'Veículo'] = veic
    return rotas_df

def balanceamento_iterativo(rotas_df, frota, pedidos, matriz_distancias, max_iter=10):
    """
    Executa balanceamento iterativo por peso, paradas, região e vizinhança até convergência.
    """
    for _ in range(max_iter):
        antes = rotas_df['Veículo'].copy()
        rotas_df = balancear_carga_e_usar_todos_veiculos(rotas_df, frota, pedidos, criterio_balanceamento='peso')
        rotas_df = balancear_carga_e_usar_todos_veiculos(rotas_df, frota, pedidos, criterio_balanceamento='paradas')
        rotas_df = balancear_carga_e_usar_todos_veiculos(rotas_df, frota, pedidos, priorizar_regiao=True)
        rotas_df = mover_para_vizinho_proximo(rotas_df, matriz_distancias)
        if rotas_df['Veículo'].equals(antes):
            break
    return rotas_df

def checar_e_corrigir_excesso_carga(rotas_df, frota, limite_pct=120):
    """
    Garante que nenhum veículo ultrapasse o limite de capacidade (ex: 120%).
    Remove pedidos excedentes e tenta realocar para veículos com espaço.
    Retorna rotas_df corrigido e lista de veículos com excesso não resolvido.
    """
    if rotas_df is None or rotas_df.empty or 'Veículo' not in rotas_df.columns or 'Demanda' not in rotas_df.columns:
        return rotas_df, []
    # Mapeia capacidade dos veículos
    id_col = 'ID Veículo' if 'ID Veículo' in frota.columns else 'Placa'
    capacidades = frota.set_index(id_col)['Capacidade (Kg)'].to_dict()
    limite_cap = {k: v * limite_pct / 100.0 for k, v in capacidades.items()}
    excesso = []
    for veic, grupo in rotas_df.groupby('Veículo'):
        cap = limite_cap.get(veic, None)
        if cap is None:
            continue
        demanda_total = grupo['Demanda'].sum()
        if demanda_total > cap:
            excesso.append((veic, demanda_total, cap))
            # Remove pedidos até ficar dentro do limite
            grupo_sorted = grupo.sort_values('Demanda', ascending=False)
            demanda_acum = 0
            indices_para_remover = []
            for idx, row in grupo_sorted.iterrows():
                if demanda_acum + row['Demanda'] > cap:
                    indices_para_remover.append(idx)
                else:
                    demanda_acum += row['Demanda']
            # Remove do DataFrame
            rotas_df.loc[indices_para_remover, 'Veículo'] = None # Marca para realocação
    # Tenta realocar pedidos sem veículo
    pedidos_sem_veic = rotas_df[rotas_df['Veículo'].isnull()]
    for idx, row in pedidos_sem_veic.iterrows():
        for veic, cap in limite_cap.items():
            demanda_atual = rotas_df[rotas_df['Veículo'] == veic]['Demanda'].sum()
            if demanda_atual + row['Demanda'] <= cap:
                rotas_df.at[idx, 'Veículo'] = veic
                break
    # Recalcula excesso
    excesso_final = []
    for veic, grupo in rotas_df.groupby('Veículo'):
        cap = limite_cap.get(veic, None)
        if cap is None:
            continue
        demanda_total = grupo['Demanda'].sum()
        if demanda_total > cap:
            excesso_final.append((veic, demanda_total, cap))
    return rotas_df, excesso_final

# Placeholder para balanceamento visual/interativo
# (Sugestão: usar Streamlit AgGrid, Dash, ou JS para drag-and-drop)
def balanceamento_visual_placeholder():
    """
    Placeholder para futura integração de balanceamento visual/interativo.
    """
    pass

# Placeholder para agrupamento por aprendizado de máquina
def sugerir_agrupamento_ml(pedidos, historico=None):
    """
    Sugere agrupamento de pedidos usando modelo de ML treinado (placeholder).
    """
    # Exemplo: usar clustering, classificação, ou regras aprendidas do histórico
    # Integrar com routing/aprendizado.py futuramente
    pedidos['Cluster_ML'] = 0 # TODO: implementar
    return pedidos

# --- IDEIAS EXTRAS PARA BALANCEAMENTO E AGRUPAMENTO INTELIGENTE ---
# 1. Balanceamento multi-critério: combinar peso, número de paradas e distância total.
# 2. Penalizar rotas que cruzam regiões diferentes (aumentar custo se misturar regiões).
# 3. Usar heurísticas de vizinhança: mover pedidos para veículos que já atendem clientes próximos.
# 4. Permitir "reserva" de veículos para regiões críticas (ex: regiões com muitos pedidos).
# 5. Implementar balanceamento iterativo até convergência de todos os critérios.
# 6. Adicionar restrição de distância máxima por veículo.
# 7. Permitir balanceamento visual/interativo na interface (drag-and-drop).
# 8. Usar aprendizado de máquina para sugerir agrupamentos baseados em roteirizações históricas.

# Exemplo de uso modularizado (pode ser removido ou usado em testes)
def exemplo_uso():
    """Exemplo de uso das funções de pós-processamento."""
    dist_matrix = np.array([
        [0, 10, 15, 20, 25],
        [10, 0, 35, 25, 30],
        [15, 35, 0, 30, 20],
        [20, 25, 30, 0, 10],
        [25, 30, 20, 10, 0]
    ])
    rota_inicial = [0, 1, 3, 2, 4, 0]
    logging.info(f"Rota Inicial: {rota_inicial}, Distância: {calcular_distancia_rota(rota_inicial, dist_matrix)}")
    rota_otimizada_2opt = heuristica_2opt(rota_inicial, dist_matrix)
    logging.info(f"Rota Otimizada (2-opt): {rota_otimizada_2opt}, Distância: {calcular_distancia_rota(rota_otimizada_2opt, dist_matrix)}")
    rota_swap = swap(rota_otimizada_2opt, 1, 3)
    logging.info(f"Rota após Swap(1, 3): {rota_swap}, Distância: {calcular_distancia_rota(rota_swap, dist_matrix)}")
    rota_longa = [0, 1, 2, 3, 4, 1, 2, 3, 4, 0]
    sub_rotas = split(rota_longa, max_paradas_por_subrota=3)
    for sr in sub_rotas:
        logging.info(f"Sub-rota: {sr}, Distância: {calcular_distancia_rota(sr, dist_matrix)}")
    rotas_para_merge = [[0, 1, 0], [0, 4, 3, 0], [0, 2, 0]]
    demandas_exemplo = [0, 5, 8, 3, 6]
    capacidade_exemplo = 15
    rotas_merged = merge(rotas_para_merge, dist_matrix, capacidade_maxima=capacidade_exemplo, demandas=demandas_exemplo)
    for rm in rotas_merged:
        demanda_rm = sum(demandas_exemplo[node] for node in rm if node != 0 and node < len(demandas_exemplo))
        logging.info(f"Rota Merge: {rm}, Distância: {calcular_distancia_rota(rm, dist_matrix)}, Demanda: {demanda_rm}")
    rota_otimizada_3opt = heuristica_3opt(rota_inicial, dist_matrix)
    logging.info(f"Rota Otimizada (3-opt via 2-opt): {rota_otimizada_3opt}, Distância: {calcular_distancia_rota(rota_otimizada_3opt, dist_matrix)}")

if __name__ == '__main__':
    exemplo_uso()