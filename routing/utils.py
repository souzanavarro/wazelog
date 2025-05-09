def pedido_destino_sp(pedido, col_municipio='Município', col_uf='UF'):
    """
    Retorna True se o pedido tem destino para o município de São Paulo/SP.
    Aceita tanto Series (linha) quanto dict.
    """
    municipio = str(pedido.get(col_municipio, '') if hasattr(pedido, 'get') else pedido[col_municipio]).strip().lower()
    uf = str(pedido.get(col_uf, '') if hasattr(pedido, 'get') else pedido[col_uf]).strip().upper()
    return municipio in ['sao paulo', 'são paulo'] and uf == 'SP'
def validar_coordenadas_dataframe(df, lat_col='Latitude', lon_col='Longitude', nome_df='DataFrame'):
    """
    Valida coordenadas em um DataFrame. Retorna (ok, msg, df_invalidos):
    - ok: True se todas válidas, False se houver problemas
    - msg: resumo do problema
    - df_invalidos: DataFrame com linhas problemáticas
    """
    if lat_col not in df.columns or lon_col not in df.columns:
        return False, f"Colunas '{lat_col}' e/ou '{lon_col}' ausentes em {nome_df}.", df
    # Critérios de validade
    cond_na = df[lat_col].isna() | df[lon_col].isna()
    cond_zero = (df[lat_col] == 0) | (df[lon_col] == 0)
    cond_out = ~df[lat_col].between(-90, 90) | ~df[lon_col].between(-180, 180)
    cond_invalid = cond_na | cond_zero | cond_out
    df_invalidos = df[cond_invalid]
    if not df_invalidos.empty:
        msg = f"{len(df_invalidos)} linhas com coordenadas inválidas em {nome_df}. Exemplos: {df_invalidos[[lat_col, lon_col]].head(3).to_dict('records')}"
        return False, msg, df_invalidos
    return True, "Todas as coordenadas válidas", pd.DataFrame([])
import logging
import pandas as pd
import numpy as np

def get_logger(name=__name__):
    """Retorna logger padronizado para o projeto."""
    logger = logging.getLogger(name)
    if not logger.hasHandlers():
        logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    return logger

def validar_dataframe(df, colunas_obrigatorias=None, nome_df='DataFrame'):
    """Valida se o DataFrame possui as colunas obrigatórias e não está vazio."""
    if df is None or df.empty:
        return False, f"{nome_df} está vazio ou não foi carregado."
    if colunas_obrigatorias:
        faltantes = [col for col in colunas_obrigatorias if col not in df.columns]
        if faltantes:
            return False, f"Colunas obrigatórias ausentes em {nome_df}: {faltantes}"
    return True, "OK"

def validar_matriz(matriz, tamanho_esperado=None):
    """Valida se a matriz é um array/lista quadrada e, se fornecido, do tamanho esperado."""
    if matriz is None:
        return False, "Matriz não fornecida."
    arr = np.array(matriz)
    if arr.ndim != 2 or arr.shape[0] != arr.shape[1]:
        return False, f"Matriz não é quadrada: shape={arr.shape}"
    if tamanho_esperado and arr.shape[0] != tamanho_esperado:
        return False, f"Matriz tem tamanho {arr.shape[0]}, esperado {tamanho_esperado}"
    return True, "OK"


def clusterizar_pedidos(pedidos, n_clusters):
    """
    Agrupa pedidos por região (se disponível) ou por proximidade geográfica (KMeans).
    - Se 'Região' existir e for informativa, cada região vira um cluster.
    - Se houver mais regiões do que clusters, regiões pequenas são agrupadas por proximidade (KMeans nos centroides).
    - Se não houver regiões, aplica KMeans nas coordenadas.
    - Pedidos sem coordenada ficam com cluster -1.
    """
    import numpy as np
    import pandas as pd
    from sklearn.cluster import KMeans

    if 'Região' in pedidos.columns and pedidos['Região'].notnull().any():
        regioes = pedidos['Região'].fillna('N/A').astype(str)
        regioes_unicas = regioes.unique()
        n_regioes = len(regioes_unicas)
        if n_regioes <= n_clusters:
            regiao_to_cluster = {reg: i for i, reg in enumerate(regioes_unicas)}
            return regioes.map(regiao_to_cluster).values
        else:
            # Agrupa regiões pequenas por proximidade
            regioes_centroides = pedidos.groupby('Região')[['Latitude', 'Longitude']].mean()
            kmeans = KMeans(n_clusters=n_clusters, random_state=42, n_init='auto')
            labels_regioes = kmeans.fit_predict(regioes_centroides)
            regiao_to_cluster = {reg: labels_regioes[i] for i, reg in enumerate(regioes_centroides.index)}
            return regioes.map(regiao_to_cluster).values
    else:
        # KMeans puro nas coordenadas
        if 'Latitude' not in pedidos.columns or 'Longitude' not in pedidos.columns:
            raise ValueError("DataFrame deve conter colunas 'Latitude' e 'Longitude' para clusterização.")
        coords = pedidos[['Latitude', 'Longitude']].dropna()
        labels_series = pd.Series(-1, index=pedidos.index)
        if not coords.empty:
            n_clusters = min(n_clusters, len(coords))
            kmeans = KMeans(n_clusters=n_clusters, random_state=42, n_init='auto')
            labels = kmeans.fit_predict(coords)
            for arr_idx, df_idx in enumerate(coords.index):
                labels_series.at[df_idx] = labels[arr_idx]
        return labels_series.values

def placa_em_rodizio_sp(placa: str, dia_semana: int) -> bool:
    """
    Retorna True se a placa está em rodízio em SP no dia da semana informado.
    placa: string da placa (ex: 'ABC1234')
    dia_semana: 0=segunda, 1=terça, ..., 4=sexta (rodízio só de segunda a sexta)
    """
    if not placa or not placa[-1].isdigit():
        return False
    final = int(placa[-1])
    rodizio = {
        0: [1, 2],  # segunda-feira
        1: [3, 4],  # terça-feira
        2: [5, 6],  # quarta-feira
        3: [7, 8],  # quinta-feira
        4: [9, 0],  # sexta-feira
    }
    return dia_semana in rodizio and final in rodizio[dia_semana]
