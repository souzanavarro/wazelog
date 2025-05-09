import pandas as pd
import numpy as np
import logging
import joblib # Para salvar/carregar modelos treinados
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestRegressor, RandomForestClassifier
from sklearn.linear_model import LinearRegression # Exemplo alternativo
from sklearn.metrics import mean_squared_error, accuracy_score, classification_report
from sklearn.preprocessing import StandardScaler, OneHotEncoder # Para feature engineering
from sklearn.compose import ColumnTransformer # Para feature engineering
from sklearn.pipeline import Pipeline # Para criar pipelines de ML

# Configuração do Logging
# Nível INFO para mensagens gerais, DEBUG para detalhes do processo
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(module)s - %(message)s')

# --- Constantes ---
MODEL_PATH = "routing/models/" # Diretório para salvar modelos treinados
DEFAULT_MODEL_FILENAME = {
    "demand": "demand_predictor.joblib",
    "time": "time_predictor.joblib",
    "risk": "risk_predictor.joblib"
}

# --- Funções Auxiliares (Placeholders/Estrutura) ---

def _save_model(model, model_type="demand"):
    """Salva um modelo treinado em arquivo."""
    filename = DEFAULT_MODEL_FILENAME.get(model_type, f"{model_type}_predictor.joblib")
    filepath = MODEL_PATH + filename
    try:
        # Criar diretório se não existir (requer import os)
        # import os
        # os.makedirs(MODEL_PATH, exist_ok=True)
        joblib.dump(model, filepath)
        logging.info(f"Modelo '{model_type}' salvo em {filepath}")
    except Exception as e:
        logging.error(f"Erro ao salvar modelo '{model_type}' em {filepath}: {e}")

def _load_model(model_type="demand"):
    """Carrega um modelo treinado de um arquivo."""
    filename = DEFAULT_MODEL_FILENAME.get(model_type, f"{model_type}_predictor.joblib")
    filepath = MODEL_PATH + filename
    try:
        model = joblib.load(filepath)
        logging.info(f"Modelo '{model_type}' carregado de {filepath}")
        return model
    except FileNotFoundError:
        logging.warning(f"Arquivo do modelo '{model_type}' não encontrado em {filepath}. Nenhum modelo carregado.")
        return None
    except Exception as e:
        logging.error(f"Erro ao carregar modelo '{model_type}' de {filepath}: {e}")
        return None

def _prepare_features(data, feature_config):
    """
    Prepara as features para o modelo (Placeholder).
    Uma implementação real usaria StandardScaler, OneHotEncoder, etc.
    """
    # Exemplo: Selecionar colunas numéricas e categóricas
    numeric_features = feature_config.get('numeric', [])
    categorical_features = feature_config.get('categorical', [])
    all_features = numeric_features + categorical_features

    missing_cols = [col for col in all_features if col not in data.columns]
    if missing_cols:
        logging.error(f"Colunas de feature ausentes nos dados: {missing_cols}")
        raise ValueError(f"Colunas de feature ausentes: {missing_cols}")

    # Aqui entraria a lógica de pré-processamento (scaling, encoding)
    # Exemplo simplificado: apenas seleciona as colunas
    features_df = data[all_features].copy()
    # Tratar NaNs (exemplo: preencher com média/mediana/moda ou usar SimpleImputer)
    for col in numeric_features:
        if features_df[col].isnull().any():
            fill_value = features_df[col].median() # Ou mean()
            features_df[col] = features_df[col].fillna(fill_value)
            logging.debug(f"Valores nulos em '{col}' preenchidos com {fill_value}")
    for col in categorical_features:
         if features_df[col].isnull().any():
            fill_value = features_df[col].mode()[0] # Preenche com a moda
            features_df[col] = features_df[col].fillna(fill_value)
            logging.debug(f"Valores nulos em '{col}' preenchidos com '{fill_value}'")

    # Em uma implementação real, aplicaríamos transformadores (ex: OneHotEncoder para categóricas)
    # Exemplo com Pipeline (requer definição prévia dos transformers):
    # preprocessor = ColumnTransformer(transformers=[...])
    # pipeline = Pipeline(steps=[('preprocessor', preprocessor)])
    # features_processed = pipeline.fit_transform(features_df)
    # return features_processed

    # Placeholder retorna o DataFrame com NaNs tratados (sem encoding/scaling real)
    # Para modelos como RandomForest, isso pode funcionar, mas não para regressão linear.
    # Para simplificar o placeholder, vamos apenas retornar as colunas selecionadas e tratadas.
    # Se houver colunas categóricas, elas precisarão ser codificadas antes de usar em muitos modelos.
    # Exemplo de codificação dummy (simples):
    if categorical_features:
        features_df = pd.get_dummies(features_df, columns=categorical_features, drop_first=True, dummy_na=False)


    return features_df


# --- Funções Principais (Placeholders Melhorados) ---

def treinar_modelo_demanda(historico, config=None):
    """
    Treina um modelo para prever demanda.
    Placeholder: Treina um RandomForestRegressor simples.
    """
    if historico is None or not isinstance(historico, pd.DataFrame) or historico.empty:
        logging.error("treinar_modelo_demanda: Histórico inválido ou vazio.")
        return None

    config = config or {}
    target_col = config.get('target', 'Qtde. dos Itens')
    feature_config = config.get('features', {
        'numeric': ['dia_semana', 'mes', 'lag_demanda_1'], # Exemplo
        'categorical': ['regiao'] # Exemplo
    })

    # --- Implementação Real ---
    try:
        # 1. Feature Engineering (exemplo básico)
        historico = historico.copy()
        if 'Data Pedido' in historico.columns:
             historico['Data Pedido'] = pd.to_datetime(historico['Data Pedido'])
             historico['dia_semana'] = historico['Data Pedido'].dt.dayofweek
             historico['mes'] = historico['Data Pedido'].dt.month
        else:
             logging.warning("Coluna 'Data Pedido' não encontrada para criar features de tempo.")
             # Adicionar colunas dummy se não existirem
             if 'dia_semana' not in historico.columns: historico['dia_semana'] = 0
             if 'mes' not in historico.columns: historico['mes'] = 1


        # Exemplo de Lag feature (requer ordenação por data e grupo)
        if 'lag_demanda_1' not in historico.columns and 'regiao' in historico.columns and 'Data Pedido' in historico.columns:
             historico = historico.sort_values(by=['regiao', 'Data Pedido'])
             historico['lag_demanda_1'] = historico.groupby('regiao')[target_col].shift(1)
        elif 'lag_demanda_1' not in historico.columns:
             historico['lag_demanda_1'] = 0 # Dummy se não puder calcular

        # Verifica se target existe
        if target_col not in historico.columns:
             logging.error(f"Coluna target '{target_col}' não encontrada no histórico.")
             return None

        # Prepara features usando a função auxiliar
        X = _prepare_features(historico, feature_config)
        y = historico[target_col].fillna(historico[target_col].median()) # Trata NaNs no target

        # 2. Split
        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

        # 3. Model Selection & Training (Exemplo: RandomForest)
        model = RandomForestRegressor(n_estimators=100, random_state=42, n_jobs=-1, max_depth=10, min_samples_leaf=5)
        model.fit(X_train, y_train)

        # 4. Evaluation (Opcional, mas recomendado)
        y_pred = model.predict(X_test)
        rmse = np.sqrt(mean_squared_error(y_test, y_pred))
        logging.info(f"Modelo de demanda treinado. RMSE no teste: {rmse:.4f}")

        # 5. Save Model
        _save_model(model, model_type="demand")

        return model

    except Exception as e:
        logging.error(f"Erro durante o treinamento do modelo de demanda: {e}", exc_info=True)
        return None


def prever_demanda(pedidos_atuais, historico=None, modelo=None, config=None):
    """
    Prevê a demanda futura usando um modelo treinado ou lógica placeholder.
    """
    if modelo is None:
        modelo = _load_model(model_type="demand")

    if modelo is not None:
        logging.info("Usando modelo de ML treinado para prever demanda.")
        config = config or {}
        feature_config = config.get('features', {
            'numeric': ['dia_semana', 'mes', 'lag_demanda_1'], # Deve corresponder ao treino
            'categorical': ['regiao']
        })
        try:
            # Preparar features para dados atuais (requer lógica similar ao treino)
            pedidos_atuais = pedidos_atuais.copy()
            # Adicionar features de tempo, lag (pode precisar do último dado histórico)
            # Exemplo simplificado: usar valores padrão ou recentes se não disponíveis
            if 'Data Pedido' in pedidos_atuais.columns: # Assume que tem a data para prever
                 pedidos_atuais['Data Pedido'] = pd.to_datetime(pedidos_atuais['Data Pedido'])
                 pedidos_atuais['dia_semana'] = pedidos_atuais['Data Pedido'].dt.dayofweek
                 pedidos_atuais['mes'] = pedidos_atuais['Data Pedido'].dt.month
            else: # Usa defaults
                 pedidos_atuais['dia_semana'] = pd.Timestamp.now().dayofweek
                 pedidos_atuais['mes'] = pd.Timestamp.now().month

            # Lag: Idealmente buscaria o último valor real daquela região no histórico
            # Placeholder: usar a média histórica ou 0
            if 'lag_demanda_1' not in pedidos_atuais.columns:
                if historico is not None and 'regiao' in historico.columns and 'Qtde. dos Itens' in historico.columns:
                     last_demand = historico.sort_values('Data Pedido').groupby('regiao')['Qtde. dos Itens'].last()
                     pedidos_atuais = pd.merge(pedidos_atuais, last_demand.rename('lag_demanda_1'), on='regiao', how='left')
                     pedidos_atuais['lag_demanda_1'] = pedidos_atuais['lag_demanda_1'].fillna(historico['Qtde. dos Itens'].mean())
                else:
                     pedidos_atuais['lag_demanda_1'] = 0


            X_pred = _prepare_features(pedidos_atuais, feature_config)

            # Garantir que as colunas de X_pred correspondam às do treino
            # (pode ser necessário reordenar ou adicionar colunas dummy faltantes com valor 0)
            # Isso é crucial se usando pd.get_dummies
            # Exemplo: model.feature_names_in_ contém as features esperadas
            if hasattr(modelo, 'feature_names_in_'):
                missing_cols = set(modelo.feature_names_in_) - set(X_pred.columns)
                for c in missing_cols:
                    X_pred[c] = 0 # Adiciona colunas faltantes com 0
                extra_cols = set(X_pred.columns) - set(modelo.feature_names_in_)
                X_pred = X_pred.drop(columns=list(extra_cols)) # Remove colunas extras
                X_pred = X_pred[modelo.feature_names_in_] # Garante a ordem


            previsoes = modelo.predict(X_pred)
            pedidos_atuais['demanda_prevista'] = previsoes
            # Garante que previsão não seja negativa
            pedidos_atuais['demanda_prevista'] = pedidos_atuais['demanda_prevista'].apply(lambda x: max(x, 0))
            logging.info("Previsão de demanda realizada com modelo ML.")
            return pedidos_atuais

        except Exception as e:
            logging.error(f"Erro ao prever demanda com modelo ML: {e}. Usando placeholder.", exc_info=True)
            # Fallback para placeholder se o modelo falhar
            return _prever_demanda_placeholder(pedidos_atuais, historico)
    else:
        # Usa placeholder se nenhum modelo foi carregado/treinado
        logging.info("Modelo de ML não disponível. Usando placeholder para prever demanda.")
        return _prever_demanda_placeholder(pedidos_atuais, historico)


def _prever_demanda_placeholder(pedidos_atuais, historico=None):
    """Lógica placeholder original para previsão de demanda."""
    if historico is None or not isinstance(historico, pd.DataFrame) or historico.empty:
        logging.warning("_prever_demanda_placeholder: Histórico não fornecido.")
        pedidos_atuais['demanda_prevista'] = np.nan # Ou 0 ou outra estimativa
        return pedidos_atuais

    coluna_demanda = 'Qtde. dos Itens'
    coluna_agrupamento = 'regiao'

    if coluna_demanda not in historico.columns or coluna_agrupamento not in historico.columns:
        logging.warning(f"_prever_demanda_placeholder: Colunas '{coluna_demanda}' ou '{coluna_agrupamento}' ausentes.")
        pedidos_atuais['demanda_prevista'] = historico[coluna_demanda].mean() if coluna_demanda in historico else np.nan
        return pedidos_atuais

    media_demanda_por_grupo = historico.groupby(coluna_agrupamento)[coluna_demanda].mean().reset_index()
    media_demanda_por_grupo = media_demanda_por_grupo.rename(columns={coluna_demanda: 'demanda_prevista'})

    if coluna_agrupamento in pedidos_atuais.columns:
        pedidos_com_previsao = pd.merge(pedidos_atuais, media_demanda_por_grupo, on=coluna_agrupamento, how='left')
        media_geral = historico[coluna_demanda].mean()
        pedidos_com_previsao['demanda_prevista'] = pedidos_com_previsao['demanda_prevista'].fillna(media_geral)
        return pedidos_com_previsao
    else:
        pedidos_atuais['demanda_prevista'] = historico[coluna_demanda].mean()
        return pedidos_atuais


# --- Funções para Tempo de Entrega e Risco (Estrutura similar) ---

def treinar_modelo_tempo(historico, config=None):
    """Treina um modelo para prever tempo de entrega (Placeholder)."""
    logging.warning("treinar_modelo_tempo: Função de treinamento não implementada. Nenhum modelo treinado.")
    # Lógica similar a treinar_modelo_demanda, mas com target='tempo_real_entrega_h'
    # e features relevantes (distancia, paradas, trafego?, etc.)
    return None

def prever_tempo_entrega(pedidos, rotas_info, historico=None, modelo=None, config=None):
    """Prevê tempo de entrega usando modelo ou placeholder."""
    if modelo is None:
        modelo = _load_model(model_type="time")

    if modelo is not None:
        logging.info("Usando modelo de ML treinado para prever tempo de entrega.")
        # Lógica de preparação de features e previsão com modelo
        # ... (requer implementação detalhada de features a partir de pedidos/rotas_info)
        logging.warning("prever_tempo_entrega: Lógica de previsão com modelo ML não implementada. Usando placeholder.")
        return _prever_tempo_entrega_placeholder(pedidos, historico) # Fallback
    else:
        logging.info("Modelo de ML não disponível. Usando placeholder para prever tempo de entrega.")
        return _prever_tempo_entrega_placeholder(pedidos, historico)

def _prever_tempo_entrega_placeholder(pedidos, historico=None):
    """Lógica placeholder original para previsão de tempo."""
    if historico is None or not isinstance(historico, pd.DataFrame) or historico.empty:
        logging.warning("_prever_tempo_entrega_placeholder: Histórico não fornecido.")
        pedidos['tempo_entrega_previsto_h'] = np.nan
        return pedidos

    coluna_tempo_real = 'tempo_real_entrega_h'
    coluna_agrupamento = 'regiao'

    if coluna_tempo_real not in historico.columns or coluna_agrupamento not in historico.columns:
        logging.warning(f"_prever_tempo_entrega_placeholder: Colunas necessárias ausentes.")
        pedidos['tempo_entrega_previsto_h'] = historico[coluna_tempo_real].mean() if coluna_tempo_real in historico else np.nan
        return pedidos

    media_tempo_por_grupo = historico.groupby(coluna_agrupamento)[coluna_tempo_real].mean().reset_index()
    media_tempo_por_grupo = media_tempo_por_grupo.rename(columns={coluna_tempo_real: 'tempo_entrega_previsto_h'})

    if coluna_agrupamento in pedidos.columns:
        pedidos_com_previsao = pd.merge(pedidos, media_tempo_por_grupo, on=coluna_agrupamento, how='left')
        media_geral = historico[coluna_tempo_real].mean()
        pedidos_com_previsao['tempo_entrega_previsto_h'] = pedidos_com_previsao['tempo_entrega_previsto_h'].fillna(media_geral)
        return pedidos_com_previsao
    else:
        pedidos['tempo_entrega_previsto_h'] = historico[coluna_tempo_real].mean()
        return pedidos


def treinar_modelo_risco(historico, config=None):
    """Treina um modelo para prever risco de atraso (Placeholder)."""
    logging.warning("treinar_modelo_risco: Função de treinamento não implementada. Nenhum modelo treinado.")
    # Lógica similar a treinar_modelo_demanda, mas com target='atrasou' (binário)
    # e modelo de classificação (RandomForestClassifier, LogisticRegression)
    return None

def prever_risco_atraso(pedidos, rotas_info, historico=None, modelo=None, config=None, threshold_atraso_h=1.0):
    """Prevê risco de atraso usando modelo ou placeholder."""
    if modelo is None:
        modelo = _load_model(model_type="risk")

    if modelo is not None:
        logging.info("Usando modelo de ML treinado para prever risco de atraso.")
        # Lógica de preparação de features e previsão com modelo
        # ... (requer implementação detalhada de features)
        # Exemplo: previsoes_proba = modelo.predict_proba(X_pred)[:, 1]
        # pedidos['risco_atraso'] = np.where(previsoes_proba > 0.5, 'Alto', 'Baixo')
        logging.warning("prever_risco_atraso: Lógica de previsão com modelo ML não implementada. Usando placeholder.")
        return _prever_risco_atraso_placeholder(pedidos, historico, threshold_atraso_h) # Fallback
    else:
        logging.info("Modelo de ML não disponível. Usando placeholder para prever risco de atraso.")
        return _prever_risco_atraso_placeholder(pedidos, historico, threshold_atraso_h)

def _prever_risco_atraso_placeholder(pedidos, historico=None, threshold_atraso_h=1.0):
    """Lógica placeholder original para previsão de risco."""
    if historico is None or not isinstance(historico, pd.DataFrame) or historico.empty:
        logging.warning("_prever_risco_atraso_placeholder: Histórico não fornecido.")
        pedidos['risco_atraso'] = 'Indeterminado'
        pedidos['perc_atraso_historico'] = np.nan
        return pedidos

    coluna_tempo_real = 'tempo_real_entrega_h'
    coluna_tempo_estimado = 'tempo_estimado_entrega_h'
    coluna_agrupamento = 'regiao'
    perc_risco_threshold = 0.15

    if not all(c in historico.columns for c in [coluna_tempo_real, coluna_tempo_estimado, coluna_agrupamento]):
        logging.warning(f"_prever_risco_atraso_placeholder: Colunas necessárias ausentes.")
        pedidos['risco_atraso'] = 'Indeterminado'
        pedidos['perc_atraso_historico'] = np.nan
        return pedidos

    historico = historico.copy() # Evita SettingWithCopyWarning
    historico['atrasou'] = (historico[coluna_tempo_real] - historico[coluna_tempo_estimado]) > threshold_atraso_h
    historico['atrasou'] = historico['atrasou'].astype(int)

    risco_por_grupo = historico.groupby(coluna_agrupamento)['atrasou'].mean().reset_index()
    risco_por_grupo = risco_por_grupo.rename(columns={'atrasou': 'perc_atraso_historico'})

    if coluna_agrupamento in pedidos.columns:
        pedidos_com_risco = pd.merge(pedidos, risco_por_grupo, on=coluna_agrupamento, how='left')
        risco_medio = historico['atrasou'].mean()
        pedidos_com_risco['perc_atraso_historico'] = pedidos_com_risco['perc_atraso_historico'].fillna(risco_medio)
        pedidos_com_risco['risco_atraso'] = np.where(
            pedidos_com_risco['perc_atraso_historico'] > perc_risco_threshold, 'Alto', 'Baixo'
        )
        return pedidos_com_risco
    else:
        pedidos['perc_atraso_historico'] = historico['atrasou'].mean()
        pedidos['risco_atraso'] = np.where(pedidos['perc_atraso_historico'] > perc_risco_threshold, 'Alto', 'Baixo')
        return pedidos


# --- Bloco de Exemplo ---
if __name__ == '__main__':
    logging.info("--- Exemplo de Funções de Aprendizado (Estrutura Melhorada) ---")

    # Criar dados de exemplo
    pedidos_atuais_ex = pd.DataFrame({
        'ID Pedido': [101, 102, 103, 104, 105],
        'Data Pedido': pd.to_datetime(['2024-02-01', '2024-02-01', '2024-02-01', '2024-02-01', '2024-02-01']),
        'regiao': ['Centro', 'Norte', 'Sul', 'Centro', 'Norte'],
        'Peso dos Itens': [5, 10, 8, 12, 7]
    })

    historico_ex = pd.DataFrame({
        'ID Pedido': [1, 2, 3, 4, 5, 6, 7, 8, 9, 10],
        'Data Pedido': pd.to_datetime(['2024-01-10', '2024-01-11', '2024-01-12', '2024-01-13', '2024-01-14',
                                      '2024-01-15', '2024-01-16', '2024-01-17', '2024-01-18', '2024-01-19']),
        'regiao': ['Centro', 'Norte', 'Sul', 'Centro', 'Norte', 'Sul', 'Centro', 'Norte', 'Sul', 'Centro'],
        'Qtde. dos Itens': [10, 15, 12, 11, 16, 14, 9, 18, 13, 12],
        'Peso dos Itens': [5, 10, 8, 6, 11, 9, 4, 12, 7, 6],
        'tempo_estimado_entrega_h': [2.0, 3.0, 2.5, 2.1, 3.2, 2.8, 1.9, 3.5, 2.6, 2.2],
        'tempo_real_entrega_h': [2.1, 3.5, 2.4, 2.3, 3.1, 4.0, 1.8, 3.6, 3.0, 2.5] # Alguns atrasos > 0.5h
    })

    # 0. Treinar Modelos (Exemplo para demanda)
    print("\n--- Treinamento de Modelo de Demanda (Exemplo) ---")
    modelo_demanda_treinado = treinar_modelo_demanda(historico_ex)
    # Treinar outros modelos (tempo, risco) aqui se implementado

    # 1. Prever Demanda (Usando modelo treinado se disponível)
    print("\n--- Previsão de Demanda ---")
    pedidos_com_demanda = prever_demanda(pedidos_atuais_ex.copy(), historico_ex, modelo=modelo_demanda_treinado)
    if pedidos_com_demanda is not None:
        print(pedidos_com_demanda[['ID Pedido', 'regiao', 'Peso dos Itens', 'demanda_prevista']])
    else:
        print("Previsão de demanda falhou.")

    # 2. Prever Tempo de Entrega (Usando placeholder)
    print("\n--- Previsão de Tempo de Entrega ---")
    pedidos_com_tempo = prever_tempo_entrega(pedidos_atuais_ex.copy(), rotas_info=None, historico=historico_ex)
    if pedidos_com_tempo is not None:
        print(pedidos_com_tempo[['ID Pedido', 'regiao', 'tempo_entrega_previsto_h']])
    else:
        print("Previsão de tempo de entrega falhou.")

    # 3. Prever Risco de Atraso (Usando placeholder)
    print("\n--- Previsão de Risco de Atraso ---")
    pedidos_com_risco = prever_risco_atraso(pedidos_atuais_ex.copy(), rotas_info=None, historico=historico_ex, threshold_atraso_h=0.5) # Threshold de 30min
    if pedidos_com_risco is not None:
        print(pedidos_com_risco[['ID Pedido', 'regiao', 'perc_atraso_historico', 'risco_atraso']])
    else:
        print("Previsão de risco de atraso falhou.")