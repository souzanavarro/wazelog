import requests
import logging
import os

# URL do servidor OSRM local (primeira opção)
OSRM_LOCAL_URL = "http://localhost:5000" 
# URL do servidor OSRM público (segunda opção)
OSRM_PUBLIC_URL = "https://router.project-osrm.org"

# Variável de ambiente para definir qual OSRM usar como padrão ou para testes
# Pode ser "local", "public", ou "auto" (tenta local primeiro, depois público)
# MODIFICADO: Força o uso do servidor público como padrão se a variável de ambiente não estiver definida ou for "auto".
OSRM_SERVER_PREFERENCE = os.environ.get("OSRM_SERVER_PREFERENCE", "public").lower()

def consultar_google_maps_directions(origem, destino, api_key):
    """
    Exemplo de consulta à API Google Maps Directions.
    Args:
        origem (str): Endereço ou coordenadas de origem.
        destino (str): Endereço ou coordenadas de destino.
        api_key (str): Chave da API Google.
    Returns:
        dict: Resposta da API ou None em caso de erro.
    """
    url = "https://maps.googleapis.com/maps/api/directions/json"
    params = {"origin": origem, "destination": destino, "key": api_key}
    try:
        resp = requests.get(url, params=params, timeout=10)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        logging.error(f"Erro ao consultar Google Maps Directions: {e}")
        return None

def consultar_mapbox_directions(origem, destino, access_token):
    """
    Exemplo de consulta à API Mapbox Directions.
    Args:
        origem (tuple): (lat, lon) origem.
        destino (tuple): (lat, lon) destino.
        access_token (str): Token de acesso Mapbox.
    Returns:
        dict: Resposta da API ou None em caso de erro.
    """
    url = f"https://api.mapbox.com/directions/v5/mapbox/driving/{origem[1]},{origem[0]};{destino[1]},{destino[0]}"
    params = {"access_token": access_token, "geometries": "geojson"}
    try:
        resp = requests.get(url, params=params, timeout=10)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        logging.error(f"Erro ao consultar Mapbox Directions: {e}")
        return None

def consultar_api_rastreamento(placa, token):
    """
    Exemplo de consulta a uma API de rastreamento de veículos.
    Args:
        placa (str): Placa do veículo.
        token (str): Token de autenticação.
    Returns:
        dict: Dados de rastreamento simulados.
    """
    # Exemplo fictício
    url = f"https://api.rastreamento.com/veiculo/{placa}"
    headers = {"Authorization": f"Bearer {token}"}
    try:
        resp = requests.get(url, headers=headers, timeout=10)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        logging.error(f"Erro ao consultar API de rastreamento: {e}")
        return None

def consultar_osrm_route(coordenadas, osrm_url=None):  # Exemplo: [(lat, lon), (lat, lon), ...]
    """
    Consulta rota real por ruas usando OSRM local.
    Args:
        coordenadas (list): Lista de tuplas (lat, lon) na ordem da rota.
        osrm_url (str): URL base do OSRM local (ex: http://localhost:5000).
    Returns:
        dict: Resposta da API OSRM ou None em caso de erro.
    """
    # Determina qual URL OSRM usar
    if OSRM_SERVER_PREFERENCE == "local":
        osrm_url_to_use = OSRM_LOCAL_URL
    # Se a preferência for "public" ou "auto" (ou qualquer outra coisa não "local"), usa o público.
    # A lógica de fallback para "auto" é tratada na seção except.
    else: 
        osrm_url_to_use = OSRM_PUBLIC_URL

    # Se uma URL específica for passada como argumento para a função, ela tem prioridade máxima.
    if osrm_url:
        osrm_url_to_use = osrm_url

    if not coordenadas or len(coordenadas) < 2:
        logging.warning("Consulta OSRM Route: Coordenadas insuficientes.")
        return None
    
    coords_str = ";".join(f"{lon},{lat}" for lat, lon in coordenadas)
    url = f"{osrm_url_to_use}/route/v1/driving/{coords_str}"
    params = {"overview": "full", "geometries": "geojson", "steps": "true"}
    
    try:
        logging.info(f"Consultando OSRM Route em: {url}")
        resp = requests.get(url, params=params, timeout=10) # Timeout de 10 segundos
        resp.raise_for_status()
        return resp.json()
    except requests.exceptions.RequestException as e:
        logging.error(f"Erro ao consultar rota OSRM em {url}: {e}")
        # Se a tentativa foi no local (osrm_url_to_use era OSRM_LOCAL_URL) E a preferência é "auto", tenta o público.
        if osrm_url_to_use == OSRM_LOCAL_URL and OSRM_SERVER_PREFERENCE == "auto":
            logging.info(f"Falha no OSRM local ({OSRM_LOCAL_URL}) com preferência 'auto', tentando OSRM público: {OSRM_PUBLIC_URL}")
            url_public = f"{OSRM_PUBLIC_URL}/route/v1/driving/{coords_str}"
            try:
                resp_public = requests.get(url_public, params=params, timeout=15) # Timeout maior para o público
                resp_public.raise_for_status()
                return resp_public.json()
            except requests.exceptions.RequestException as e_public:
                logging.error(f"Erro ao consultar rota OSRM no servidor público {OSRM_PUBLIC_URL}: {e_public}")
                return None
        return None


def consultar_osrm_table(coordenadas, osrm_url=None):  # Matriz de distâncias/tempos
    """
    Consulta matriz de distâncias e tempos usando OSRM local.
    Args:
        coordenadas (list): Lista de tuplas (lat, lon).
        osrm_url (str): URL base do OSRM local.
    Returns:
        dict: Resposta da API OSRM ou None em caso de erro.
    """
    # Determina qual URL OSRM usar
    if OSRM_SERVER_PREFERENCE == "local":
        osrm_url_to_use = OSRM_LOCAL_URL
    # Se a preferência for "public" ou "auto" (ou qualquer outra coisa não "local"), usa o público.
    else:
        osrm_url_to_use = OSRM_PUBLIC_URL

    # Se uma URL específica for passada como argumento para a função, ela tem prioridade máxima.
    if osrm_url:
        osrm_url_to_use = osrm_url

    if not coordenadas or len(coordenadas) < 2:
        logging.warning("Consulta OSRM Table: Coordenadas insuficientes.")
        return None

    coords_str = ";".join(f"{lon},{lat}" for lat, lon in coordenadas)
    url = f"{osrm_url_to_use}/table/v1/driving/{coords_str}"
    params = {"annotations": "duration,distance"}

    try:
        logging.info(f"Consultando OSRM Table em: {url}")
        resp = requests.get(url, params=params, timeout=20) # Timeout de 20 segundos
        resp.raise_for_status()
        return resp.json()
    except requests.exceptions.RequestException as e:
        logging.error(f"Erro ao consultar matriz OSRM em {url}: {e}")
        # Se a tentativa foi no local (osrm_url_to_use era OSRM_LOCAL_URL) E a preferência é "auto", tenta o público.
        if osrm_url_to_use == OSRM_LOCAL_URL and OSRM_SERVER_PREFERENCE == "auto":
            logging.info(f"Falha no OSRM local ({OSRM_LOCAL_URL}) com preferência 'auto', tentando OSRM público: {OSRM_PUBLIC_URL}")
            url_public = f"{OSRM_PUBLIC_URL}/table/v1/driving/{coords_str}"
            try:
                resp_public = requests.get(url_public, params=params, timeout=30) # Timeout maior para o público
                resp_public.raise_for_status()
                return resp_public.json()
            except requests.exceptions.RequestException as e_public:
                logging.error(f"Erro ao consultar matriz OSRM no servidor público {OSRM_PUBLIC_URL}: {e_public}")
                return None
        return None

# Instruções:
# - Adicione suas chaves/tokens de API em variáveis de ambiente ou arquivos seguros.
# - Use as funções acima como base para integração real.
# - Consulte a documentação oficial das APIs para detalhes de parâmetros e limites.
