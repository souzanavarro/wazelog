"""
Pré-processamento e clusterização de pedidos para roteirização.
"""

from sklearn.cluster import KMeans
import pandas as pd # Adicionar import

def agrupar_por_regiao(pedidos_df, n_clusters=300):
    """Agrupa pedidos por região para facilitar a roteirização."""
    pedidos_df = clusterizar_geograficamente(pedidos_df, n_clusters)
    return pedidos_df

def clusterizar_geograficamente(pedidos_df, n_clusters=None):
    """Executa clusterização geográfica (ex: KMeans) para agrupar pedidos próximos.
    Se a coluna 'regiao' já existir e não tiver nulos, usa os valores existentes.
    """
    # Verifica se a coluna 'regiao' existe e não tem valores nulos
    if 'regiao' in pedidos_df.columns and not pd.isna(pedidos_df['regiao']).any():
        print("Usando coluna 'regiao' existente.")
        return pedidos_df

    print("Coluna 'regiao' não encontrada ou com valores nulos. Executando KMeans.")
    # Supondo que pedidos_df tenha colunas 'latitude' e 'longitude'
    if 'latitude' not in pedidos_df.columns or 'longitude' not in pedidos_df.columns:
        raise ValueError("DataFrame deve conter colunas 'latitude' e 'longitude' para clusterização.")

    if n_clusters is None:
        n_clusters = 300  # valor padrão atualizado

    coords = pedidos_df[['latitude', 'longitude']].dropna() # Garante que não há nulos nas coordenadas

    if coords.empty:
        print("Não há coordenadas válidas para clusterizar.")
        pedidos_df['regiao'] = None # Ou algum valor padrão
        return pedidos_df

    kmeans = KMeans(n_clusters=min(n_clusters, len(coords)), random_state=42, n_init=10) # Ajusta n_clusters se for maior que amostras
    # Atribui clusters apenas para linhas com coordenadas válidas
    pedidos_df.loc[coords.index, 'regiao'] = kmeans.fit_predict(coords)

    return pedidos_df
