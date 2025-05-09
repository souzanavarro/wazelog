import pandas as pd
import os

PLACAS_PROIBIDAS = {"FLB1111", "FLB2222", "FLB3333", "FLB4444", "FLB5555", "FLB6666", "FLB7777", "FLB8888", "FLB9999"}

def _converter_para_booleano(valor):
    if isinstance(valor, bool):
        return valor
    if isinstance(valor, str):
        return valor.lower() in ['sim', 'yes', '1', 'true', 'verdadeiro', 'disponivel', 'disponível']
    if pd.api.types.is_number(valor):
        return bool(valor) # 1, 1.0 se tornam True; 0, 0.0 se tornam False
    return False # Padrão para False se não reconhecido ou NaN após fillna

def processar_frota(arquivo):
    # Detecta o formato do arquivo
    nome = arquivo.name if hasattr(arquivo, 'name') else str(arquivo)
    ext = os.path.splitext(nome)[-1].lower()
    if ext in ['.xlsx', '.xlsm']:
        df = pd.read_excel(arquivo, dtype=str) # Ler tudo como string inicialmente
    elif ext == '.csv':
        df = pd.read_csv(arquivo, dtype=str) # Ler tudo como string inicialmente
    elif ext == '.json':
        df = pd.read_json(arquivo, dtype=str) # Ler tudo como string inicialmente
    else:
        raise ValueError('Formato de arquivo não suportado.')

    # Verificar se a coluna 'Placa' existe (essencial)
    if 'Placa' not in df.columns:
        raise ValueError("A coluna 'Placa' é obrigatória na planilha da frota.")
    df['Placa'] = df['Placa'].fillna('').astype(str).str.upper()

    # Renomear 'Descrição Veículo' para 'Descrição' se 'Descrição Veículo' existir e 'Descrição' não.
    if 'Descrição Veículo' in df.columns and 'Descrição' not in df.columns:
        df.rename(columns={'Descrição Veículo': 'Descrição'}, inplace=True)

    # Garantir colunas de texto e preencher NaNs com string vazia
    for col_name in ['Transportador', 'Descrição', 'Veículo', 'Regiões Preferidas']:
        if col_name not in df.columns:
            df[col_name] = ''
        else:
            df[col_name] = df[col_name].fillna('').astype(str)

    # Geração de ID do veículo
    df['ID Veículo'] = df['Placa']

    # Garantir colunas de janela de tempo e preencher NaNs
    if 'Janela Início' not in df.columns:
        df['Janela Início'] = '00:00'
    else:
        df['Janela Início'] = df['Janela Início'].fillna('00:00')
    df['Janela Início'] = df['Janela Início'].astype(str)

    if 'Janela Fim' not in df.columns:
        df['Janela Fim'] = '23:59'
    else:
        df['Janela Fim'] = df['Janela Fim'].fillna('23:59')
    df['Janela Fim'] = df['Janela Fim'].astype(str)
        
    # Normalização de capacidade e preencher NaNs com 0
    if 'Capacidade (Cx)' not in df.columns:
        df['Capacidade (Cx)'] = 0
    else:
        df['Capacidade (Cx)'] = pd.to_numeric(df['Capacidade (Cx)'], errors='coerce').fillna(0)
    df['Capacidade (Cx)'] = df['Capacidade (Cx)'].astype(int)

    if 'Capacidade (Kg)' not in df.columns:
        df['Capacidade (Kg)'] = 0.0
    else:
        df['Capacidade (Kg)'] = pd.to_numeric(df['Capacidade (Kg)'], errors='coerce').fillna(0)
    df['Capacidade (Kg)'] = df['Capacidade (Kg)'].astype(float)
    
    # Processamento da coluna 'Disponível'
    if 'Disponível' not in df.columns:
        df['Disponível'] = True # Assume True para coluna ausente
    else:
        df['Disponível'] = df['Disponível'].fillna(True) # Assume True para NaN
    df['Disponível'] = df['Disponível'].apply(_converter_para_booleano)

    # Remove placas proibidas
    df = df[~df['Placa'].isin(PLACAS_PROIBIDAS)]
    
    # Verifica duplicidade de placas
    if df['Placa'].duplicated().any():
        placas_duplicadas = df[df['Placa'].duplicated(keep=False)]['Placa'].unique()
        raise ValueError(f"Placas duplicadas encontradas: {', '.join(placas_duplicadas)}")

    # Definir a ordem final e colunas a serem mantidas
    colunas_finais_obrigatorias = [
        "Placa", "Transportador", "Descrição", "Veículo",
        "Capacidade (Cx)", "Capacidade (Kg)", "Disponível", "Regiões Preferidas",
        "ID Veículo", "Janela Início", "Janela Fim"
    ]
    
    # Garantir que todas as colunas finais existam (fallback, a maioria já deve existir e ter tipo)
    for col in colunas_finais_obrigatorias:
        if col not in df.columns:
            # Este bloco é um seguro, idealmente não seria atingido com a lógica acima
            if col == 'ID Veículo': df[col] = df['Placa'] 
            elif col == 'Disponível': df[col] = True
            elif col == 'Capacidade (Cx)': df[col] = 0
            elif col == 'Capacidade (Kg)': df[col] = 0.0
            elif col == 'Janela Início': df[col] = '00:00'
            elif col == 'Janela Fim': df[col] = '23:59'
            else: df[col] = '' 

    df = df[colunas_finais_obrigatorias]
    
    return df
