import streamlit as st
from frota import processar_frota
from database import carregar_frota, salvar_frota
import pandas as pd

def show():
    if 'df_frota' not in st.session_state:
        st.session_state.df_frota = carregar_frota()
  
    st.header("Gerenciar Frota", divider="rainbow")
    st.write("Gerencie, importe, visualize, edite, adicione ou remova veículos da sua frota de forma fácil e rápida")
   
    if not st.session_state.df_frota.empty:
        st.session_state.df_frota = st.session_state.df_frota.reset_index(drop=True)
        st.session_state.df_frota.columns = [str(col) for col in st.session_state.df_frota.columns]

    df_display = st.session_state.df_frota.copy()

    # Garante a existência da coluna 'Regiões Preferidas' mesmo se não existir na planilha
    if 'Regiões Preferidas' not in df_display.columns:
        df_display['Regiões Preferidas'] = ''
    # Garante a existência da coluna 'Descrição' (pode ter vindo como 'Descrição Veículo')
    if 'Descrição' not in df_display.columns and 'Descrição Veículo' in df_display.columns:
        df_display.rename(columns={'Descrição Veículo': 'Descrição'}, inplace=True)
    elif 'Descrição' not in df_display.columns:
        df_display['Descrição'] = ''
    # Garante a existência das colunas de manutenção
    if 'Em Manutenção' not in df_display.columns:
        df_display['Em Manutenção'] = False
    if 'Qtd. Manutenções' not in df_display.columns:
        df_display['Qtd. Manutenções'] = 0

    if not df_display.empty:
        df_display = df_display.loc[:, ~df_display.columns.duplicated()]
        df_display.columns = [str(col) if col else f"Coluna_{i}" for i, col in enumerate(df_display.columns)]
        
        # Remover apenas colunas técnicas, mas manter 'Regiões Preferidas'
        cols_remover_display = ['Janela Início', 'Janela Fim', 'ID Veículo']
        # Adicionar 'Descrição Veículo' à lista de remoção se 'Descrição' já existir, para evitar duplicidade na exibição
        if 'Descrição' in df_display.columns and 'Descrição Veículo' in df_display.columns:
            cols_remover_display.append('Descrição Veículo')

        df_display = df_display.drop(columns=[col for col in cols_remover_display if col in df_display.columns], errors='ignore')

        # Garante que 'Regiões Preferidas' está presente e visível
        # Reorganiza para mostrar após 'Disponível' (ou ao final se não existir)
        colunas_ordenadas = [
            'Placa', 'Transportador', 'Descrição', 'Veículo',
            'Capacidade (Cx)', 'Capacidade (Kg)', 'Disponível', 'Em Manutenção', 'Qtd. Manutenções', 'Regiões Preferidas'
        ]
        # Filtrar colunas_ordenadas para incluir apenas aquelas que realmente existem em df_display
        colunas_ordenadas_existentes = [c for c in colunas_ordenadas if c in df_display.columns]
        
        outras_colunas = [c for c in df_display.columns if c not in colunas_ordenadas_existentes]
        df_display = df_display[colunas_ordenadas_existentes + outras_colunas]

        # --- Custom CSS for beautiful cards ---
        st.markdown('''
        <style>
        .kpi-card {
            background: #fff;
            border-radius: 18px;
            box-shadow: 0 2px 12px 0 rgba(0,0,0,0.07);
            padding: 1.2rem 1.5rem 1.2rem 1.5rem;
            margin-bottom: 1.2rem;
            min-height: 120px;
            display: flex;
            flex-direction: column;
            align-items: flex-start;
            justify-content: center;
            border: 1.5px solid #e6e6e6;
        }
        .kpi-title {
            font-size: 1.1rem;
            font-weight: 600;
            color: #3a3a3a;
            margin-bottom: 0.2rem;
        }
        .kpi-sub {
            font-size: 0.95rem;
            color: #888;
            margin-bottom: 0.5rem;
        }
        .kpi-value {
            font-size: 2.2rem;
            font-weight: 700;
            color: #1a1a1a;
            margin-bottom: 0.1rem;
        }
        </style>
        ''', unsafe_allow_html=True)
        st.subheader("📊 Resumo da Frota")
        col1, col2, col3 = st.columns(3)
        # Calcula totais e ativos
        total_veiculos = len(df_display)
        # Ativo = Disponível == True e Em Manutenção == False
        if 'Disponível' in df_display.columns and 'Em Manutenção' in df_display.columns:
            ativos = ((df_display['Disponível'] == True) & (df_display['Em Manutenção'] == False)).sum()
            df_ativos = df_display[(df_display['Disponível'] == True) & (df_display['Em Manutenção'] == False)]
        elif 'Disponível' in df_display.columns:
            ativos = df_display['Disponível'].sum()
            df_ativos = df_display[df_display['Disponível'] == True]
        else:
            ativos = total_veiculos
            df_ativos = df_display
        # Capacidade Total (Kg)
        cap_kg_total = df_display['Capacidade (Kg)'].sum() if 'Capacidade (Kg)' in df_display.columns and pd.api.types.is_numeric_dtype(df_display['Capacidade (Kg)']) else 0
        cap_kg_ativos = df_ativos['Capacidade (Kg)'].sum() if 'Capacidade (Kg)' in df_ativos.columns and pd.api.types.is_numeric_dtype(df_ativos['Capacidade (Kg)']) else 0
        # Capacidade Total (Cx)
        cap_cx_total = df_display['Capacidade (Cx)'].sum() if 'Capacidade (Cx)' in df_display.columns and pd.api.types.is_numeric_dtype(df_display['Capacidade (Cx)']) else 0
        cap_cx_ativos = df_ativos['Capacidade (Cx)'].sum() if 'Capacidade (Cx)' in df_ativos.columns and pd.api.types.is_numeric_dtype(df_ativos['Capacidade (Cx)']) else 0
        with col1:
            st.markdown(f'''<div class="kpi-card">
                <div class="kpi-title">Veículos (Total / Ativos)</div>
                <div class="kpi-sub">Total / Ativos</div>
                <div class="kpi-value">{total_veiculos}/{int(ativos)}</div>
            </div>''', unsafe_allow_html=True)
        with col2:
            st.markdown(f'''<div class="kpi-card">
                <div class="kpi-title">Capacidade Total (Kg)</div>
                <div class="kpi-sub">Total (Kg)</div>
                <div class="kpi-value">{cap_kg_total:,.0f} / {cap_kg_ativos:,.0f}</div>
            </div>''', unsafe_allow_html=True)
        with col3:
            st.markdown(f'''<div class="kpi-card">
                <div class="kpi-title">Capacidade Total (Cx)</div>
                <div class="kpi-sub">Total (Cx)</div>
                <div class="kpi-value">{cap_cx_total:,.0f} / {cap_cx_ativos:,.0f}</div>
            </div>''', unsafe_allow_html=True)

        with st.container(border=True):
            arquivo = st.file_uploader("Selecione um arquivo (.xlsx, .xlsm, .csv, .json)", type=["xlsx", "xlsm", "csv", "json"], key="frota_uploader")
            if arquivo:
                try:
                    df_importada = processar_frota(arquivo)
                    if not st.session_state.df_frota.empty and 'Placa' in st.session_state.df_frota.columns and 'Placa' in df_importada.columns:
                        df_importada = df_importada.drop_duplicates(subset=['Placa'], keep='last')
                        st.session_state.df_frota = pd.concat([
                            st.session_state.df_frota[~st.session_state.df_frota['Placa'].isin(df_importada['Placa'])],
                            df_importada
                        ]).reset_index(drop=True)
                    else:
                        st.session_state.df_frota = df_importada.copy()
                    
                    salvar_frota(st.session_state.df_frota)
                    st.success("Frota importada/atualizada com sucesso!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Erro ao processar a frota: {e}")

        with st.container(border=True):
            st.subheader("✏️ Editar Frota")
            placa_col_display = 'Placa' if 'Placa' in df_display.columns else None
            veiculo_sel_edit = None
            if placa_col_display:
                placas_display = sorted(df_display[placa_col_display].dropna().unique().tolist())
                veiculo_sel_edit = st.selectbox(
                    "Filtrar por placa para edição rápida (ou edite abaixo)", 
                    ["Todos"] + placas_display,
                    key="filtro_placa_editor"
                )
                if veiculo_sel_edit != "Todos":
                    df_to_edit = df_display[df_display[placa_col_display] == veiculo_sel_edit].copy()
                else:
                    df_to_edit = df_display.copy()
            else:
                df_to_edit = df_display.copy()

            colunas_editor = [c for c in df_to_edit.columns if c not in ['ID Veículo']]
            # Garante que as colunas de manutenção estão presentes
            if 'Em Manutenção' not in colunas_editor:
                colunas_editor.append('Em Manutenção')
            if 'Qtd. Manutenções' not in colunas_editor:
                colunas_editor.append('Qtd. Manutenções')

            edited_df = st.data_editor(
                df_to_edit[colunas_editor],
                num_rows="dynamic", 
                use_container_width=True, 
                key="frota_data_editor",
                column_config={
                    "Disponível": st.column_config.CheckboxColumn(
                        "Disponível?", 
                        default=True, 
                        help="Marque se o veículo está disponível para roteirização"
                    ),
                    "Em Manutenção": st.column_config.CheckboxColumn(
                        "Em Manutenção?", 
                        default=False, 
                        help="Marque se o veículo está em manutenção. Se sim, não será considerado disponível."
                    ),
                    "Qtd. Manutenções": st.column_config.NumberColumn(
                        format="%d",
                        help="Quantidade de vezes que o veículo foi colocado em manutenção."
                    ),
                    "Capacidade (Kg)": st.column_config.NumberColumn(format="%.2f"),
                    "Capacidade (Cx)": st.column_config.NumberColumn(format="%d")
                }
            )

            col_save, col_limpar_frota = st.columns(2)
            with col_save:
                if st.button("💾 Salvar Alterações do Editor", key="save_editor_frota"):
                    if 'Placa' in edited_df.columns:
                        current_frota = st.session_state.df_frota.copy()
                        edited_df_com_id = edited_df.copy()
                        if 'ID Veículo' not in edited_df_com_id.columns and 'Placa' in edited_df_com_id.columns:
                             edited_df_com_id['ID Veículo'] = edited_df_com_id['Placa']

                        # Atualiza contador de manutenções se houve mudança para True
                        if 'Em Manutenção' in edited_df_com_id.columns and 'Qtd. Manutenções' in edited_df_com_id.columns:
                            for idx, row in edited_df_com_id.iterrows():
                                placa = row['Placa']
                                em_manut = row['Em Manutenção']
                                # Busca valor anterior
                                prev = current_frota[current_frota['Placa'] == placa]
                                if not prev.empty:
                                    prev_em_manut = prev.iloc[0].get('Em Manutenção', False)
                                    prev_qtd = prev.iloc[0].get('Qtd. Manutenções', 0)
                                    # Se mudou de False para True, incrementa
                                    if not prev_em_manut and em_manut:
                                        edited_df_com_id.at[idx, 'Qtd. Manutenções'] = int(prev_qtd) + 1
                                    # Se mudou de True para False, mantém o contador
                                    elif prev_em_manut and not em_manut:
                                        edited_df_com_id.at[idx, 'Qtd. Manutenções'] = int(prev_qtd)
                                else:
                                    # Novo veículo, se já está em manutenção, começa com 1
                                    if em_manut:
                                        edited_df_com_id.at[idx, 'Qtd. Manutenções'] = 1
                                    else:
                                        edited_df_com_id.at[idx, 'Qtd. Manutenções'] = 0

                        if veiculo_sel_edit == "Todos" or not placa_col_display:
                            st.session_state.df_frota = edited_df_com_id.copy()
                        else:
                            idx_original = current_frota[current_frota['Placa'] == veiculo_sel_edit].index
                            if not idx_original.empty:
                                for col in edited_df_com_id.columns:
                                    if col in current_frota.columns:
                                        current_frota.loc[idx_original, col] = edited_df_com_id[col].values[0]
                                st.session_state.df_frota = current_frota
                            else:
                                st.session_state.df_frota = pd.concat([current_frota, edited_df_com_id], ignore_index=True)

                        if 'Placa' in st.session_state.df_frota.columns:
                            if 'ID Veículo' not in st.session_state.df_frota.columns:
                                st.session_state.df_frota['ID Veículo'] = st.session_state.df_frota['Placa']
                            st.session_state.df_frota = st.session_state.df_frota.drop_duplicates(subset=['Placa'], keep='last')
                        
                        salvar_frota(st.session_state.df_frota)
                        st.success("Alterações salvas com sucesso!")
                        st.rerun()
                    else:
                        st.warning("Coluna 'Placa' é necessária para salvar alterações do editor.")
            
            with col_limpar_frota:
                if st.button("🗑️ Limpar Toda a Frota", type="secondary", help="Remove todos os veículos da base de dados.", key="limpar_frota_editor_section"):
                    from database import limpar_frota
                    limpar_frota()
                    st.session_state.df_frota = pd.DataFrame()
                    st.success("Toda a frota foi limpa com sucesso!")
                    st.rerun()

    else:
        st.info("Nenhum veículo na frota. Importe uma planilha ou adicione manualmente.")

    st.markdown("<div class='wrapper-for-floating-card'>", unsafe_allow_html=True)
    with st.container(border=True):
        st.subheader("➕ Adicionar / 📝 Editar Veículo Individualmente")
        
        df_atual_frota = st.session_state.get('df_frota', pd.DataFrame())
        placas_existentes = []
        if not df_atual_frota.empty and 'Placa' in df_atual_frota.columns:
            placas_existentes = sorted(df_atual_frota['Placa'].dropna().unique().tolist())
        
        placa_para_editar_ou_adicionar = st.selectbox(
            "Selecione a placa para editar, ou '(Novo Veículo)' para adicionar", 
            ["(Novo Veículo)"] + placas_existentes, 
            key="placa_form_select"
        )

        default_values = {
            'placa': "", 'transportador': "", 'descricao': "", 'veiculo': "",
            'capacidade_cx': 0, 'capacidade_kg': 0.0, 'disponivel': "Sim",
            'em_manutencao': False, 'qtd_manutencoes': 0,
            'regioes_preferidas': ""
        }

        if placa_para_editar_ou_adicionar != "(Novo Veículo)":
            veic_data = df_atual_frota[df_atual_frota['Placa'] == placa_para_editar_ou_adicionar].iloc[0].to_dict()
            default_values['placa'] = veic_data.get('Placa', placa_para_editar_ou_adicionar)
            default_values['transportador'] = veic_data.get('Transportador', '')
            # Prioriza 'Descrição', mas usa 'Descrição Veículo' como fallback se necessário
            default_values['descricao'] = veic_data.get('Descrição', veic_data.get('Descrição Veículo', ''))
            default_values['veiculo'] = veic_data.get('Veículo', '')
            default_values['capacidade_cx'] = int(veic_data.get('Capacidade (Cx)', 0))
            default_values['capacidade_kg'] = float(veic_data.get('Capacidade (Kg)', 0.0))
            disponivel_bool = veic_data.get('Disponível', True)
            if isinstance(disponivel_bool, str):
                disponivel_bool = disponivel_bool.lower() in ['true', 'sim', '1', 'yes']
            default_values['disponivel'] = "Sim" if bool(disponivel_bool) else "Não"
            default_values['em_manutencao'] = veic_data.get('Em Manutenção', False)
            default_values['qtd_manutencoes'] = int(veic_data.get('Qtd. Manutenções', 0))
            default_values['regioes_preferidas'] = veic_data.get('Regiões Preferidas', '')
        
        with st.form("add_edit_veiculo_form", clear_on_submit=True):
            st.write("**Detalhes do Veículo:**")
            c1, c2, c3 = st.columns(3)
            with c1:
                placa_form = st.text_input("Placa*", value=default_values['placa'], key="placa_form_input", help="Obrigatório")
                transportador_form = st.text_input("Transportador", value=default_values['transportador'])
            with c2:
                descricao_form = st.text_input("Descrição", value=default_values['descricao'])
                veiculo_form = st.text_input("Tipo/Modelo do Veículo", value=default_values['veiculo'])
            with c3:
                capacidade_cx_form = st.number_input("Capacidade (Cx)", min_value=0, step=1, value=default_values['capacidade_cx'])
                capacidade_kg_form = st.number_input("Capacidade (Kg)", min_value=0.0, step=1.0, format="%.2f", value=default_values['capacidade_kg'])
                disponivel_form = st.selectbox("Disponível?", ["Sim", "Não"], index=0 if default_values['disponivel'] == "Sim" else 1)
                em_manutencao_form = st.checkbox("Em Manutenção?", value=default_values['em_manutencao'], help="Se marcado, o veículo não será considerado disponível.")
                qtd_manutencoes_form = st.number_input("Qtd. Manutenções", min_value=0, step=1, value=default_values['qtd_manutencoes'], help="Quantidade de vezes que o veículo foi colocado em manutenção.", disabled=True)
            regioes_preferidas_form = st.text_input(
                "Regiões Preferidas",
                value=default_values['regioes_preferidas'],
                help="Exemplo: Zona Sul, Barueri, Osasco. Separe por vírgula. Deixe vazio para aceitar qualquer região."
            )
            col_form1, col_form2, col_form3 = st.columns([1,1,1])
            with col_form1:
                submit_label = "💾 Salvar Alterações" if placa_para_editar_ou_adicionar != "(Novo Veículo)" else "➕ Adicionar Veículo"
                submitted_form = st.form_submit_button(submit_label)
            with col_form2:
                if st.session_state.df_frota.shape[0] > 0:
                    if st.form_submit_button("🗑️ Limpar Toda a Frota", type="secondary"):
                        from database import limpar_frota
                        limpar_frota()
                        st.session_state.df_frota = pd.DataFrame()
                        st.success("Toda a frota foi limpa com sucesso!")
                        st.rerun()
            with col_form3:
                if placa_para_editar_ou_adicionar != "(Novo Veículo)":
                    if st.form_submit_button("❌ Remover Veículo", type="secondary"):
                        current_df = st.session_state.get('df_frota', pd.DataFrame()).copy()
                        current_df = current_df[current_df['Placa'] != placa_para_editar_ou_adicionar]
                        st.session_state.df_frota = current_df.reset_index(drop=True)
                        salvar_frota(st.session_state.df_frota)
                        st.success(f"Veículo {placa_para_editar_ou_adicionar} removido com sucesso!")
                        st.rerun()
            if submitted_form:
                if not placa_form.strip():
                    st.error("O campo 'Placa' é obrigatório.")
                else:
                    current_df = st.session_state.get('df_frota', pd.DataFrame()).copy()
                    placa_upper = placa_form.strip().upper()
                    # Busca valores anteriores para controle do contador de manutenções
                    prev = current_df[current_df['Placa'] == placa_upper]
                    prev_em_manut = prev.iloc[0]['Em Manutenção'] if not prev.empty and 'Em Manutenção' in prev.columns else False
                    prev_qtd = int(prev.iloc[0]['Qtd. Manutenções']) if not prev.empty and 'Qtd. Manutenções' in prev.columns else 0
                    # Lógica do contador de manutenções
                    if not prev_em_manut and em_manutencao_form:
                        qtd_manutencoes_final = prev_qtd + 1
                    else:
                        qtd_manutencoes_final = prev_qtd if prev_qtd > 0 else (1 if em_manutencao_form else 0)

                    novo_ou_editado_veiculo = {
                        "Placa": placa_upper,
                        "Transportador": transportador_form.strip(),
                        "Descrição": descricao_form.strip(),
                        "Veículo": veiculo_form.strip(),
                        "Capacidade (Cx)": capacidade_cx_form,
                        "Capacidade (Kg)": capacidade_kg_form,
                        "Disponível": disponivel_form == "Sim",
                        "Em Manutenção": em_manutencao_form,
                        "Qtd. Manutenções": qtd_manutencoes_final,
                        "ID Veículo": placa_upper,
                        "Regiões Preferidas": regioes_preferidas_form.strip()
                    }
                    if placa_para_editar_ou_adicionar != "(Novo Veículo)":
                        current_df = current_df[current_df['Placa'] != placa_para_editar_ou_adicionar]
                    current_df = current_df[current_df['Placa'] != placa_upper]
                    current_df = current_df.loc[:, ~current_df.columns.duplicated()]
                    novo_df = pd.DataFrame([novo_ou_editado_veiculo])
                    novo_df = novo_df.loc[:, ~novo_df.columns.duplicated()]
                    st.session_state.df_frota = pd.concat([current_df, novo_df], ignore_index=True)
                    st.session_state.df_frota = st.session_state.df_frota.drop_duplicates(subset=['Placa'], keep='last').reset_index(drop=True)
                    salvar_frota(st.session_state.df_frota)
                    action = "atualizado" if placa_para_editar_ou_adicionar != "(Novo Veículo)" else "adicionado"
                    st.success(f"Veículo {action} com sucesso!")
                    st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)
