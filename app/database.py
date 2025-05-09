import sqlite3
import pandas as pd
import os
import logging

DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'database', 'wazelog.db')

# Conexão e criação das tabelas

def get_connection():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    return conn

def init_db():
    conn = get_connection()
    cur = conn.cursor()
    # Tabela frota
    cur.execute('''CREATE TABLE IF NOT EXISTS frota (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        placa TEXT,
        transportador TEXT,
        descricao TEXT,
        veiculo TEXT,
        capacidade_cx INTEGER,
        capacidade_kg REAL,
        disponivel INTEGER,
        id_veiculo TEXT,
        regioes_preferidas TEXT
    )''')
    # Tabela pedidos
    cur.execute('''CREATE TABLE IF NOT EXISTS pedidos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        numero_pedido TEXT,
        cod_cliente TEXT,
        cnpj TEXT,
        nome_cliente TEXT,
        grupo_cliente TEXT,
        regiao TEXT,
        endereco_completo TEXT,
        qtde_itens INTEGER,
        peso_itens REAL,
        latitude REAL,
        longitude REAL,
        janela_descarga INTEGER DEFAULT 30,
        anomalia INTEGER
    )''')
    # Tabela config para endereço de partida
    cur.execute('''CREATE TABLE IF NOT EXISTS config (
        chave TEXT PRIMARY KEY,
        valor TEXT,
        latitude REAL,
        longitude REAL
    )''')
    # Tabela coordenadas
    cur.execute('''CREATE TABLE IF NOT EXISTS coordenadas (
        endereco_completo TEXT PRIMARY KEY,
        latitude REAL,
        longitude REAL
    )''')
    # Tabela para resultados de busca de CNPJ
    cur.execute('''CREATE TABLE IF NOT EXISTS cnpj_enderecos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        cnpj TEXT,
        status TEXT,
        cod_edata TEXT,
        cod_mega TEXT,
        nome TEXT,
        endereco TEXT,
        latitude REAL,
        longitude REAL
    )''')
    conn.commit()
    conn.close()

# Funções para endereço de partida

def salvar_endereco_partida(endereco, latitude, longitude):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute('''INSERT OR REPLACE INTO config (chave, valor, latitude, longitude)
                   VALUES (?, ?, ?, ?)''', ("endereco_partida", endereco, latitude, longitude))
    conn.commit()
    conn.close()

def carregar_endereco_partida():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute('''SELECT valor, latitude, longitude FROM config WHERE chave = ?''', ("endereco_partida",))
    row = cur.fetchone()
    conn.close()
    if row:
        return row[0], row[1], row[2]
    return None, None, None

# Funções para Frota

def salvar_frota(df):
    conn = get_connection()
    df = df.copy()
    # Remove colunas duplicadas antes de qualquer operação
    df = df.loc[:, ~df.columns.duplicated()]
    
    # Garantir a existência da coluna 'Regiões Preferidas' e tratar NaNs
    if 'Regiões Preferidas' not in df.columns:
        df['Regiões Preferidas'] = ''
    df['Regiões Preferidas'] = df['Regiões Preferidas'].fillna('')

    # Garante que só existe uma coluna 'Disponível' e converte corretamente
    if 'Disponível' in df.columns:
        df['disponivel'] = df['Disponível'].astype(int)
    else:
        df['disponivel'] = 1  # Default para disponível se não existir
    df = df.rename(columns={
        'Placa': 'placa',
        'Transportador': 'transportador',
        'Descrição': 'descricao',
        'Veículo': 'veiculo',
        'Capacidade (Cx)': 'capacidade_cx',
        'Capacidade (Kg)': 'capacidade_kg',
        'ID Veículo': 'id_veiculo',
        'disponivel': 'disponivel',
        'Regiões Preferidas': 'regioes_preferidas'
    })
    # Garantir que todas as colunas esperadas pelo DB existam no DF antes de salvar
    colunas_db = ['placa', 'transportador', 'descricao', 'veiculo', 'capacidade_cx', 'capacidade_kg', 'disponivel', 'id_veiculo', 'regioes_preferidas']
    for col_db in colunas_db:
        if col_db not in df.columns:
            # Definir valor padrão apropriado se a coluna estiver faltando
            if col_db == 'disponivel':
                df[col_db] = 1 # Default para True
            elif col_db in ['capacidade_cx', 'capacidade_kg']:
                df[col_db] = 0
            else:
                df[col_db] = '' # Default para string vazia para colunas de texto

    df_para_salvar = df[colunas_db]
    df_para_salvar.to_sql('frota', conn, if_exists='replace', index=False)
    # Sempre exporta o CSV atualizado após salvar no banco
    # Reverte para nomes de colunas amigáveis para o CSV
    df_csv = df_para_salvar.rename(columns={
        'placa': 'Placa',
        'transportador': 'Transportador',
        'descricao': 'Descrição',
        'veiculo': 'Veículo',
        'capacidade_cx': 'Capacidade (Cx)',
        'capacidade_kg': 'Capacidade (Kg)',
        'disponivel': 'Disponível',
        'id_veiculo': 'ID Veículo',
        'regioes_preferidas': 'Regiões Preferidas'
    })
    # Ordena as colunas para o CSV
    colunas_ordem = [
        'Placa', 'Transportador', 'Descrição', 'Veículo',
        'Capacidade (Cx)', 'Capacidade (Kg)', 'Disponível', 'ID Veículo', 'Regiões Preferidas'
    ]
    colunas_presentes = [col for col in colunas_ordem if col in df_csv.columns]
    outras_colunas = [col for col in df_csv.columns if col not in colunas_presentes]
    df_csv = df_csv[colunas_presentes + outras_colunas]
    csv_path = os.path.join(os.path.dirname(__file__), '..', 'data', 'Frota.csv')
    df_csv.to_csv(csv_path, index=False, encoding='utf-8-sig')
    conn.close()

def carregar_frota():
    conn = get_connection()
    try:
        df = pd.read_sql('SELECT * FROM frota', conn)
    except pd.io.sql.DatabaseError:
        # Tabela pode não existir ou estar vazia, retorna DataFrame vazio com colunas esperadas
        df = pd.DataFrame(columns=['id', 'placa', 'transportador', 'descricao', 'veiculo', 'capacidade_cx', 'capacidade_kg', 'disponivel', 'id_veiculo', 'regioes_preferidas'])
    conn.close()
    if not df.empty:
        df = df.drop(columns=['id'], errors="ignore")
        df = df.rename(columns={
            'placa': 'Placa',
            'transportador': 'Transportador',
            'descricao': 'Descrição',
            'veiculo': 'Veículo',
            'capacidade_cx': 'Capacidade (Cx)',
            'capacidade_kg': 'Capacidade (Kg)',
            'id_veiculo': 'ID Veículo',
            'disponivel': 'Disponível',
            'regioes_preferidas': 'Regiões Preferidas'
        })
        if 'Disponível' in df.columns:
            df['Disponível'] = df['Disponível'].astype(bool)
        else:
            df['Disponível'] = True # Default se a coluna não existir por algum motivo
        
        # Garantir que 'Regiões Preferidas' exista e preencher NaNs
        if 'Regiões Preferidas' not in df.columns:
            df['Regiões Preferidas'] = ''
        df['Regiões Preferidas'] = df['Regiões Preferidas'].fillna('')

    else: # Se o DataFrame estiver vazio após carregar (ex: tabela não existe ou vazia)
        df = pd.DataFrame(columns=[
            'Placa', 'Transportador', 'Descrição', 'Veículo',
            'Capacidade (Cx)', 'Capacidade (Kg)', 'Disponível', 'ID Veículo', 'Regiões Preferidas'
        ])

    return df

def limpar_frota():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute('DELETE FROM frota')
    conn.commit()
    conn.close()

# Funções para Pedidos

def salvar_pedidos(df):
    conn = get_connection()
    df = df.copy()
    # Garante que as colunas Latitude e Longitude existam
    if 'Latitude' not in df.columns:
        df['Latitude'] = None
    if 'Longitude' not in df.columns:
        df['Longitude'] = None
    # Garante que a coluna Janela de Descarga exista
    if 'Janela de Descarga' not in df.columns:
        df['Janela de Descarga'] = 30
    # Remove colunas duplicadas de anomalia antes de renomear/criar
    for col in ['anomalia', 'Anomalia']:
        if col in df.columns:
            df = df.drop(columns=[col])
    # Renomeia colunas
    df = df.rename(columns={
        'Nº Pedido': 'numero_pedido',
        'Cód. Cliente': 'cod_cliente',
        'CNPJ': 'cnpj',
        'Nome Cliente': 'nome_cliente',
        'Grupo Cliente': 'grupo_cliente',
        'Região': 'regiao',
        'Endereço Completo': 'endereco_completo',
        'Qtde. dos Itens': 'qtde_itens',
        'Peso dos Itens': 'peso_itens',
        'Latitude': 'latitude',
        'Longitude': 'longitude',
        'Janela de Descarga': 'janela_descarga'
    })
    # Cria coluna 'anomalia' final
    df['anomalia'] = 0
    if 'Anomalia' in df.columns:
        df['anomalia'] = df['Anomalia'].astype(int)
    df.to_sql('pedidos', conn, if_exists='replace', index=False)
    # Sempre exporta o CSV atualizado após salvar no banco
    # Reverte para nomes de colunas amigáveis para o CSV
    df_csv = df.rename(columns={
        'numero_pedido': 'Nº Pedido',
        'cod_cliente': 'Cód. Cliente',
        'cnpj': 'CNPJ',
        'nome_cliente': 'Nome Cliente',
        'grupo_cliente': 'Grupo Cliente',
        'regiao': 'Região',
        'endereco_completo': 'Endereço Completo',
        'qtde_itens': 'Qtde. dos Itens',
        'peso_itens': 'Peso dos Itens',
        'latitude': 'Latitude',
        'longitude': 'Longitude',
        'janela_descarga': 'Janela de Descarga',
        'anomalia': 'Anomalia'
    })
    # Ordena as colunas para o CSV
    colunas_ordem = [
        "Nº Pedido", "Cód. Cliente", "CNPJ", "Nome Cliente", "Grupo Cliente",
        "Região", "Endereço Completo", "Qtde. dos Itens", "Peso dos Itens",
        "Latitude", "Longitude", "Janela de Descarga", "Anomalia"
    ]
    colunas_presentes = [col for col in colunas_ordem if col in df_csv.columns]
    outras_colunas = [col for col in df_csv.columns if col not in colunas_presentes]
    df_csv = df_csv[colunas_presentes + outras_colunas]
    csv_path = os.path.join(os.path.dirname(__file__), '..', 'data', 'Pedidos.csv')
    df_csv.to_csv(csv_path, index=False, encoding='utf-8-sig')
    conn.close()

def carregar_pedidos():
    conn = get_connection()
    df = pd.read_sql('SELECT * FROM pedidos', conn)
    conn.close()
    if not df.empty:
        df = df.drop(columns=['id'], errors="ignore")
        df = df.rename(columns={
            'numero_pedido': 'Nº Pedido',
            'cod_cliente': 'Cód. Cliente',
            'cnpj': 'CNPJ',
            'nome_cliente': 'Nome Cliente',
            'grupo_cliente': 'Grupo Cliente',
            'regiao': 'Região',
            'endereco_completo': 'Endereço Completo',
            'qtde_itens': 'Qtde. dos Itens',
            'peso_itens': 'Peso dos Itens',
            'latitude': 'Latitude',
            'longitude': 'Longitude',
            'janela_descarga': 'Janela de Descarga',
            'anomalia': 'Anomalia'
        })
        # Remover colunas de endereço originais se existirem
        for col in ["Endereço de Entrega", "Bairro de Entrega", "Cidade de Entrega"]:
            if col in df.columns:
                df = df.drop(columns=[col])
        # Reorganizar colunas na ordem desejada
        colunas_ordem = [
            "Nº Pedido", "Cód. Cliente", "CNPJ", "Nome Cliente", "Grupo Cliente",
            "Região", "Endereço Completo", "Qtde. dos Itens", "Peso dos Itens",
            "Latitude", "Longitude", "Janela de Descarga", "Anomalia"
        ]
        df = df[[col for col in colunas_ordem if col in df.columns]]
        if 'Anomalia' in df.columns:
            df['Anomalia'] = df['Anomalia'].astype(bool)
    return df

def salvar_coordenada(endereco_completo, latitude, longitude):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute('''INSERT OR REPLACE INTO coordenadas (endereco_completo, latitude, longitude)
                   VALUES (?, ?, ?)''', (endereco_completo, latitude, longitude))
    conn.commit()
    conn.close()

def buscar_coordenada(endereco_completo):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute('''SELECT latitude, longitude FROM coordenadas WHERE endereco_completo = ?''', (endereco_completo,))
    row = cur.fetchone()
    conn.close()
    if row and row[0] is not None and row[1] is not None:
        return row[0], row[1]
    return None, None

def salvar_cnpj_enderecos(df):
    conn = get_connection()
    df = df.copy()
    # Corrigir valores do tipo tuple em todas as colunas
    for col in df.columns:
        df[col] = df[col].apply(lambda x: str(x) if isinstance(x, tuple) else x)
    # Padronizar nomes de colunas
    col_renomear = {}
    for col in df.columns:
        if col.lower() == 'cnpj' and col != 'CNPJ':
            col_renomear[col] = 'CNPJ'
        if col.lower() == 'status' and col != 'Status':
            col_renomear[col] = 'Status'
        if col.lower() in ['cód. edata', 'cod_edata', 'cod. edata'] and col != 'Cód. Edata':
            col_renomear[col] = 'Cód. Edata'
        if col.lower() in ['cód. mega', 'cod_mega', 'cod. mega'] and col != 'Cód. Mega':
            col_renomear[col] = 'Cód. Mega'
        if col.lower() == 'nome' and col != 'Nome':
            col_renomear[col] = 'Nome'
        if col.lower() in ['endereco', 'endereço'] and col != 'Endereco':
            col_renomear[col] = 'Endereco'
        if col.lower() == 'latitude' and col != 'Latitude':
            col_renomear[col] = 'Latitude'
        if col.lower() == 'longitude' and col != 'Longitude':
            col_renomear[col] = 'Longitude'
        if col.lower() in ['google maps', 'googlemaps', 'maps'] and col != 'Google Maps':
            col_renomear[col] = 'Google Maps'
    if col_renomear:
        df = df.rename(columns=col_renomear)
    # Remover colunas duplicadas
    df = df.loc[:, ~df.columns.duplicated()]
    # Garantir todas as colunas padrão
    colunas_padrao = [
        'CNPJ', 'Status', 'Cód. Edata', 'Cód. Mega', 'Nome',
        'Endereco', 'Latitude', 'Longitude', 'Google Maps'
    ]
    for col in colunas_padrao:
        if col not in df.columns:
            df[col] = ''
    # Reordenar colunas
    df = df[[col for col in colunas_padrao if col in df.columns]]
    # Mesclar com o banco existente para não perder dados antigos
    try:
        df_db = pd.read_sql('SELECT * FROM cnpj_enderecos', conn)
        # Padronizar colunas do banco
        col_renomear_db = {}
        for col in df_db.columns:
            if col.lower() == 'cnpj' and col != 'CNPJ':
                col_renomear_db[col] = 'CNPJ'
            if col.lower() == 'status' and col != 'Status':
                col_renomear_db[col] = 'Status'
            if col.lower() in ['cód. edata', 'cod_edata', 'cod. edata'] and col != 'Cód. Edata':
                col_renomear_db[col] = 'Cód. Edata'
            if col.lower() in ['cód. mega', 'cod_mega', 'cod. mega'] and col != 'Cód. Mega':
                col_renomear_db[col] = 'Cód. Mega'
            if col.lower() == 'nome' and col != 'Nome':
                col_renomear_db[col] = 'Nome'
            if col.lower() in ['endereco', 'endereço'] and col != 'Endereco':
                col_renomear_db[col] = 'Endereco'
            if col.lower() == 'latitude' and col != 'Latitude':
                col_renomear_db[col] = 'Latitude'
            if col.lower() == 'longitude' and col != 'Longitude':
                col_renomear_db[col] = 'Longitude'
            if col.lower() in ['google maps', 'googlemaps', 'maps'] and col != 'Google Maps':
                col_renomear_db[col] = 'Google Maps'
        if col_renomear_db:
            df_db = df_db.rename(columns=col_renomear_db)
        df_db = df_db.loc[:, ~df_db.columns.duplicated()]
        for col in colunas_padrao:
            if col not in df_db.columns:
                df_db[col] = ''
        df_db = df_db[[col for col in colunas_padrao if col in df_db.columns]]
        # Mesclar pelo CNPJ (atualiza existentes, adiciona novos)
        df_final = pd.concat([df_db, df]).drop_duplicates(subset=['CNPJ'], keep='last').reset_index(drop=True)
    except Exception:
        df_final = df
    # Salvar no banco
    cur = conn.cursor()
    cur.execute('DROP TABLE IF EXISTS cnpj_enderecos')
    conn.commit()
    df_final.to_sql('cnpj_enderecos', conn, if_exists='replace', index=False)
    conn.close()

def carregar_cnpj_enderecos():
    conn = get_connection()
    try:
        df = pd.read_sql('SELECT * FROM cnpj_enderecos', conn)
    except Exception:
        df = pd.DataFrame()
    conn.close()
    if not df.empty:
        df = df.drop(columns=['id'], errors="ignore")
    return df

def limpar_cnpj_enderecos():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute('DELETE FROM cnpj_enderecos')
    conn.commit()
    conn.close()

def buscar_cnpj_no_banco(cnpj):
    """
    Busca informações de um CNPJ no banco de dados.

    Args:
        cnpj (str): O CNPJ a ser buscado.

    Returns:
        dict: Um dicionário com as informações do CNPJ, ou None se não encontrado.
    """
    conn = get_connection()
    try:
        query = "SELECT * FROM cnpj_enderecos WHERE CNPJ = ?"
        df = pd.read_sql_query(query, conn, params=(cnpj,))
        if not df.empty:
            return df.iloc[0].to_dict()
    except Exception as e:
        logging.error(f"Erro ao buscar CNPJ no banco: {e}")
    finally:
        conn.close()
    return None
