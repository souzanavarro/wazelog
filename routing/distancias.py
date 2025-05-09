"""
Cálculo de matriz de distâncias/tempos entre pontos usando OSRM, Mapbox, Google, etc.
"""
import requests
import numpy as np
import time
import logging
import json
import traceback # Adicionado para log de erro completo
import os # Adicionado para ler variáveis de ambiente

# --- Constantes ---
# Use a variável de ambiente OSRM_BASE_URL se definida, senão usa localhost:5000
OSRM_SERVER_URL = os.environ.get("OSRM_BASE_URL", "https://router.project-osrm.org")
MAX_RETRIES = 3
# --- AJUSTE AQUI ---
RETRY_DELAY = 15 # Segundos entre retentativas
DEFAULT_TIMEOUT = 180 # Timeout para cada requisição OSRM em segundos
# -------------------
INFINITE_VALUE = 9999999 # Valor para representar "infinito" ou falha

# Configuração do logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- AJUSTE AQUI: Adicionar extra_params=None ---
def _get_osrm_table_batch(url_base, coords_str, metrica, timeout=DEFAULT_TIMEOUT, extra_params=None):
    """Faz a requisição OSRM Table API para um lote, com retentativas."""
    # --- AJUSTE AQUI: Mesclar parâmetros ---
    params = {"annotations": metrica}
    if extra_params:
        params.update(extra_params)
    # --------------------------------------
    full_url = f"{url_base}{coords_str}"
    last_exception = None # Armazena a última exceção para log final

    for attempt in range(1, MAX_RETRIES + 1):
        response = None # Garante que response esteja definida
        try:
            # Log da URL completa apenas na primeira tentativa para reduzir verbosidade
            # --- AJUSTE AQUI: Incluir params no log da URL ---
            params_str = "&".join([f"{k}={v}" for k, v in params.items()])
            log_url = f"{full_url}?{params_str}" if attempt == 1 else f"{url_base}... (params omitidos)"
            # -------------------------------------------------
            logging.info(f"Consultando OSRM Table API via GET (Batch - Tentativa {attempt}/{MAX_RETRIES}): {log_url} (timeout={timeout}s)")
            # --- AJUSTE AQUI: Passar o dicionário 'params' mesclado ---
            response = requests.get(full_url, params=params, timeout=timeout)
            # ---------------------------------------------------------
            response.raise_for_status() # Levanta exceção para status HTTP 4xx/5xx
            logging.info(f"OSRM Status Code (Batch): {response.status_code}")
            data = response.json()
            metric_key = f"{metrica}s"
            if metric_key not in data:
                logging.error(f"Resposta OSRM não contém a chave esperada '{metric_key}'. Resposta: {data}")
                return None # Falha, não retenta (erro de formato de resposta)
            return data[metric_key] # Sucesso! Retorna os dados

        except requests.exceptions.Timeout as e:
            last_exception = e
            logging.warning(f"Timeout na requisição OSRM (Tentativa {attempt}/{MAX_RETRIES}): {e}.")
            if attempt == MAX_RETRIES:
                logging.error(f"Máximo de retentativas ({MAX_RETRIES}) atingido devido a Timeout.")
            else:
                logging.info(f"Tentando novamente em {RETRY_DELAY}s...")
                time.sleep(RETRY_DELAY)

        except requests.exceptions.RequestException as e:
            last_exception = e
            status_code = e.response.status_code if e.response is not None else "N/A"

            # Erro 400 (Bad Request) - Não retentar
            if e.response is not None and status_code == 400:
                 logging.error(f"Erro HTTP 400 (Bad Request) do OSRM API. Verifique a string de coordenadas e a URL.")
                 # Usar e.request.url se disponível para a URL exata enviada
                 # --- AJUSTE AQUI: Incluir params no log da URL ---
                 params_str_err = "&".join([f"{k}={v}" for k, v in params.items()])
                 logging.error(f"URL Enviada (aproximada): {full_url}?{params_str_err}")
                 # -------------------------------------------------
                 logging.error(f"Coordenadas Enviadas: {coords_str[:200]}...") # Log truncado
                 try:
                     error_body = e.response.json()
                     logging.error(f"Corpo da Resposta (Erro 400): {error_body}")
                 except json.JSONDecodeError:
                     logging.error(f"Corpo da Resposta (Erro 400, não JSON): {e.response.text}")
                 return None # Falha, não retenta

            # Outros erros HTTP (5xx, etc.) - Retentar
            logging.warning(f"Erro na requisição OSRM (Tentativa {attempt}/{MAX_RETRIES}): Status={status_code}, Erro={e}.")
            if attempt == MAX_RETRIES:
                 logging.error(f"Máximo de retentativas ({MAX_RETRIES}) atingido. Último erro: Status={status_code}, Erro={e}")
                 # Log do corpo da resposta na falha final, se houver resposta
                 if e.response is not None:
                     try:
                         error_body = e.response.json()
                         logging.error(f"Corpo da resposta OSRM (falha final): {error_body}")
                     except json.JSONDecodeError:
                         logging.error(f"Corpo da resposta OSRM (falha final, não JSON): {e.response.text}")
            else:
                 logging.info(f"Tentando novamente em {RETRY_DELAY}s...")
                 time.sleep(RETRY_DELAY)

        except json.JSONDecodeError as e:
             last_exception = e
             logging.warning(f"Erro ao decodificar JSON da resposta OSRM (Tentativa {attempt}/{MAX_RETRIES}): {e}")
             if response is not None:
                 logging.error(f"Texto da resposta inválida: {response.text}")
             if attempt == MAX_RETRIES:
                 logging.error(f"Máximo de retentativas ({MAX_RETRIES}) atingido após erro de JSON.")
             else:
                 logging.info(f"Tentando novamente em {RETRY_DELAY}s...")
                 time.sleep(RETRY_DELAY)

    # Se o loop terminar (todas as tentativas falharam), retorna None
    logging.error(f"Falha ao obter dados do OSRM após {MAX_RETRIES} tentativas. Última exceção: {last_exception}")
    return None

# --- Funções de Validação Adicionadas ---
def _is_valid_coord(value):
    """Verifica se um valor é um número finito (não NaN, não infinito)."""
    return isinstance(value, (int, float)) and np.isfinite(value)

def _is_valid_lat_lon(lat, lon):
    """Verifica se latitude e longitude são válidas."""
    return _is_valid_coord(lat) and _is_valid_coord(lon) and -90 <= lat <= 90 and -180 <= lon <= 180

def _validar_coordenadas(pontos_lote):
    """Valida uma lista de pontos (lat, lon) e retorna os válidos e seus índices originais."""
    pontos_validos = []
    indices_validos_no_lote = []
    for i, (lat, lon) in enumerate(pontos_lote):
        if _is_valid_lat_lon(lat, lon):
            pontos_validos.append((lat, lon))
            indices_validos_no_lote.append(i)
        else:
            logging.warning(f"Coordenada inválida no lote: índice {i}, valor ({lat}, {lon}). Será ignorada.")
    return pontos_validos, indices_validos_no_lote
# --- Fim Funções de Validação ---


def calcular_matriz_distancias(pontos, provider="osrm", metrica="duration", progress_callback=None):
    """
    Calcula a matriz de distâncias ou tempos usando OSRM Table API em lotes,
    validando coordenadas antes de cada requisição.

    Args:
        pontos (list): Lista de tuplas (latitude, longitude).
        provider (str): Provedor de roteamento (atualmente apenas "osrm").
        metrica (str): "duration" (tempo em segundos) ou "distance" (distância em metros).
        progress_callback (function, optional): Função para reportar progresso (recebe float 0.0 a 1.0).

    Returns:
        numpy.ndarray or None: Matriz NxN com os valores da métrica, ou None se ocorrer erro crítico.
                               Retorna INFINITE_VALUE para pares impossíveis de rotear.
    """
    n = len(pontos)
    if n == 0:
        logging.warning("Lista de pontos vazia.")
        return np.array([[]])
    if provider != "osrm":
        raise NotImplementedError("Apenas o provedor 'osrm' é suportado no momento.") # Corrigido: Adicionado raise
    if metrica not in ["duration", "distance"]:
        raise ValueError("Métrica deve ser 'duration' ou 'distance'.") # Corrigido: Adicionado raise

    url_base = f"{OSRM_SERVER_URL}/table/v1/driving/"
    final_matrix = np.full((n, n), INFINITE_VALUE, dtype=int) # Usar int para tempos/distâncias
    np.fill_diagonal(final_matrix, 0)

    # --- AJUSTE AQUI ---
    max_coords_per_request = 15 # Reduzido de 20 para 15
    # -------------------
    num_batches = (n + max_coords_per_request - 1) // max_coords_per_request
    batches = [list(range(i * max_coords_per_request, min((i + 1) * max_coords_per_request, n))) for i in range(num_batches)]
    total_requests = num_batches * num_batches

    logging.info(f"Dividindo {n} pontos em {num_batches} lotes (máx {max_coords_per_request} por lote). Total de {total_requests} requisições OSRM.")
    request_count = 0

    try:
        for r_idx, batch_origem_indices_global in enumerate(batches):
            for c_idx, batch_destino_indices_global in enumerate(batches):
                request_count += 1
                logging.info(f"Calculando submatriz Lote {r_idx+1}/{num_batches} -> Lote {c_idx+1}/{num_batches} (Req {request_count}/{total_requests})")

                # --- Validação dos Pontos do Lote Combinado ---
                # Combina índices globais de origem e destino, removendo duplicatas e mantendo a ordem
                combined_indices_global = sorted(list(set(batch_origem_indices_global + batch_destino_indices_global)))
                pontos_lote_combinado = [pontos[i] for i in combined_indices_global]

                # Valida as coordenadas *deste lote combinado*
                osrm_points_coords, indices_validos_no_lote_combinado = _validar_coordenadas(pontos_lote_combinado)

                # Mapeia índices válidos no lote combinado de volta para índices globais
                indices_globais_validos = [combined_indices_global[i] for i in indices_validos_no_lote_combinado]

                # Mapeia índices globais de origem/destino para índices *dentro da lista de pontos válidos* (osrm_points_coords)
                # que será enviada ao OSRM. Cria um dicionário para busca rápida.
                map_global_to_osrm_idx = {osrm_idx: global_idx for osrm_idx, global_idx in enumerate(indices_globais_validos)}

                # Filtra os índices globais de origem/destino para incluir apenas os que são válidos
                batch_origem_indices_validos_global = [idx for idx in batch_origem_indices_global if idx in map_global_to_osrm_idx]
                batch_destino_indices_validos_global = [idx for idx in batch_destino_indices_global if idx in map_global_to_osrm_idx]

                # Obtém os índices correspondentes na lista que vai para o OSRM
                osrm_sources_indices = [map_global_to_osrm_idx[idx] for idx in batch_origem_indices_validos_global]
                osrm_destinations_indices = [map_global_to_osrm_idx[idx] for idx in batch_destino_indices_validos_global]
                # --- Fim Validação ---


                # --- Requisição OSRM com Pontos Válidos ---
                # Não faz requisição se houver menos de 2 pontos válidos em sources ou destinations
                if len(osrm_sources_indices) < 2 or len(osrm_destinations_indices) < 2:
                    logging.warning(f"Lote ignorado: menos de 2 pontos em sources ou destinations (sources={len(osrm_sources_indices)}, destinations={len(osrm_destinations_indices)}). Pulando requisição OSRM.")
                    if progress_callback:
                        progress_callback(request_count / total_requests)
                    continue

                if not osrm_points_coords or len(osrm_points_coords) < 1 or not osrm_sources_indices or not osrm_destinations_indices:
                     logging.warning(f"Nenhum ponto válido ou nenhuma origem/destino válido no lote combinado (Req {request_count}). Pulando requisição OSRM.")
                     if progress_callback:
                        progress_callback(request_count / total_requests)
                     continue

                batch_coords_str = ";".join([f"{lon},{lat}" for lat, lon in osrm_points_coords])

                # Adiciona os parâmetros sources e destinations
                sources_param = ";".join(map(str, osrm_sources_indices))
                destinations_param = ";".join(map(str, osrm_destinations_indices))
                params_com_indices = {"sources": sources_param, "destinations": destinations_param}

                # --- AJUSTE AQUI: Usar extra_params ---
                # Chama a função _get_osrm_table_batch passando a URL base e os parâmetros extras
                partial_matrix_raw = _get_osrm_table_batch(url_base, batch_coords_str, metrica, timeout=DEFAULT_TIMEOUT, extra_params=params_com_indices)
                # --------------------------------------


                if partial_matrix_raw is None:
                    # O log de erro detalhado já acontece dentro de _get_osrm_table_batch
                    logging.error(f"Falha crítica ao obter dados do OSRM para o lote (Req {request_count}/{total_requests}). Abortando cálculo da matriz.")
                    return None # Aborta se a requisição falhar após retentativas

                # --- Preenchimento da Matriz Final ---
                # A matriz retornada pelo OSRM com sources/destinations tem shape (len(sources), len(destinations))
                # Iteramos sobre os resultados e colocamos na matriz final usando os índices globais válidos
                expected_rows = len(osrm_sources_indices)
                expected_cols = len(osrm_destinations_indices)
                actual_rows = len(partial_matrix_raw) if partial_matrix_raw is not None else 0
                actual_cols = len(partial_matrix_raw[0]) if actual_rows > 0 and partial_matrix_raw[0] is not None else 0

                if actual_rows != expected_rows or actual_cols != expected_cols:
                     logging.error(f"Erro: Dimensões da matriz OSRM ({actual_rows}x{actual_cols}) "
                                   f"não correspondem aos índices de origem/destino enviados ({expected_rows}x{expected_cols}). Req {request_count}")
                     # Considerar isso um erro crítico também? Por enquanto, loga e continua, pode preencher errado.
                     # return None # Descomentar para abortar
                else:
                    for i, source_global_idx in enumerate(batch_origem_indices_validos_global):
                        for j, dest_global_idx in enumerate(batch_destino_indices_validos_global):
                            value = partial_matrix_raw[i][j]
                            # OSRM retorna null para rotas impossíveis
                            final_matrix[source_global_idx, dest_global_idx] = int(value) if value is not None else INFINITE_VALUE

                # Atualiza progresso
                if progress_callback:
                    progress_callback(request_count / total_requests)
                # --- Fim Preenchimento ---

        logging.info(f"Matriz de '{metrica}' ({final_matrix.shape}) calculada com sucesso usando lotes.")
        return final_matrix

    except Exception as e:
        logging.error(f"Erro inesperado durante cálculo da matriz OSRM em lote: {e}")
        logging.error(traceback.format_exc()) # Log completo do traceback
        return None

def calcular_distancia(ponto_a, ponto_b, provider="osrm", metrica="duration"):
    """
    Calcula a distância ou tempo entre dois pontos específicos.
    Nota: Menos eficiente que calcular a matriz inteira se precisar de muitos pares.

    Args:
        ponto_a (tuple): Tupla (latitude, longitude) do ponto de origem.
        ponto_b (tuple): Tupla (latitude, longitude) do ponto de destino.
        provider (str): Provedor de roteamento (atualmente suporta apenas "osrm").
        metrica (str): 'duration' (tempo em segundos) ou 'distance' (distância em metros).

    Returns:
        float: Valor da métrica solicitada, ou None em caso de erro.
    """
    if not _validar_coordenadas([ponto_a, ponto_b]):
        return INFINITE_VALUE # Retorna infinito se a validação falhar

    if provider.lower() != "osrm":
        logging.error(f"Provedor '{provider}' não suportado.")
        raise NotImplementedError(f"Provedor '{provider}' não suportado.")

    lat_a, lon_a = ponto_a
    lat_b, lon_b = ponto_b

    # Formata os pontos para a URL do OSRM: longitude,latitude;longitude,latitude
    coords_str = f"{lon_a},{lat_a};{lon_b},{lat_b}"
    # Monta a URL para o serviço 'route'
    url = f"{OSRM_SERVER_URL}/route/v1/driving/{coords_str}"
    params = {
        "overview": "false", # Não precisamos da geometria da rota
        "annotations": "false" # Não precisamos de anotações detalhadas
    }

    try:
        logging.info(f"Consultando OSRM Route API: {url}")
        response = requests.get(url, params=params, timeout=30) # Timeout de 30s
        response.raise_for_status()
        data = response.json()

        if data['code'] != 'Ok' or not data.get('routes'):
            logging.warning(f"Rota não encontrada ou erro na API OSRM entre {ponto_a} e {ponto_b}: {data.get('message', 'Sem rota')}")
            return INFINITE_VALUE # Retorna infinito se não houver rota

        # Extrai a métrica da primeira rota encontrada
        route_data = data['routes'][0]
        if metrica == "duration":
            valor = route_data.get('duration')
        elif metrica == "distance":
            valor = route_data.get('distance')
        else:
            logging.error(f"Métrica '{metrica}' não reconhecida pela implementação.")
            return None

        if valor is None:
             logging.warning(f"API OSRM não retornou valor para a métrica '{metrica}' entre {ponto_a} e {ponto_b}.")
             return INFINITE_VALUE # Retorna infinito se valor for None

        logging.info(f"{metrica.capitalize()} entre {ponto_a} e {ponto_b}: {valor}")
        return int(valor) # Retorna como inteiro

    except requests.exceptions.RequestException as e:
        logging.error(f"Erro de conexão/requisição ao servidor OSRM: {e}")
        return INFINITE_VALUE # Retorna infinito em caso de erro de conexão
    except Exception as e:
        logging.error(f"Erro inesperado ao calcular {metrica}: {e}")
        return INFINITE_VALUE # Retorna infinito em caso de erro inesperado

# Exemplo de uso (pode ser removido ou comentado)
if __name__ == '__main__':
    # Pontos de exemplo (latitude, longitude) - São Paulo
    pontos_exemplo = [
        (-23.5505, -46.6333), # Centro SP
        (-23.5614, -46.6559), # Av. Paulista
        (-23.6825, -46.6994), # Aeroporto Congonhas
        (-23.5475, -46.6361)  # Próximo ao centro
    ]

    print("\\n--- Teste calcular_matriz_distancias (Duração) ---")
    matriz_duracao = calcular_matriz_distancias(pontos_exemplo, metrica="duration")
    if matriz_duracao is not None:
        print(matriz_duracao)

    print("\\n--- Teste calcular_matriz_distancias (Distância) ---")
    matriz_distancia = calcular_matriz_distancias(pontos_exemplo, metrica="distance")
    if matriz_distancia is not None:
        print(matriz_distancia)

    print("\\n--- Teste calcular_distancia (Duração) ---")
    duracao_0_1 = calcular_distancia(pontos_exemplo[0], pontos_exemplo[1], metrica="duration")
    if duracao_0_1 is not None:
        print(f"Duração entre ponto 0 e 1: {duracao_0_1:.2f} segundos")

    print("\\n--- Teste calcular_distancia (Distância) ---")
    distancia_0_1 = calcular_distancia(pontos_exemplo[0], pontos_exemplo[1], metrica="distance")
    if distancia_0_1 is not None:
        print(f"Distância entre ponto 0 e 1: {distancia_0_1:.2f} metros")

    print("\\n--- Teste com poucos pontos ---")
    matriz_um_ponto = calcular_matriz_distancias([pontos_exemplo[0]])
    print("Matriz com 1 ponto:")
    print(matriz_um_ponto)

    matriz_zero_pontos = calcular_matriz_distancias([])
    print("Matriz com 0 pontos:")
    print(matriz_zero_pontos)

    print("\nCalculando matriz de DISTÂNCIA...")
    matriz_distancia = calcular_matriz_distancias(pontos_exemplo, metrica="distance")
    if matriz_distancia is not None:
        print("Matriz de Distância (metros):")
        print(matriz_distancia)
    else:
        print("Falha ao calcular matriz de distância.")
