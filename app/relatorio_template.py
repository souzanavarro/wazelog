def gerar_relatorio_html(cenario):
    """
    Gera um relatório HTML resumido do cenário de roteirização.
    Args:
        cenario (dict): Dicionário com dados do cenário (igual ao salvo na sessão).
    Returns:
        str: HTML do relatório.
    """
    html = f"""
    <html>
    <head>
        <title>Relatório de Roteirização</title>
        <style>
            body {{ font-family: Arial, sans-serif; margin: 2em; }}
            h1 {{ color: #1976d2; }}
            table {{ border-collapse: collapse; width: 100%; margin-top: 1em; }}
            th, td {{ border: 1px solid #bbb; padding: 8px; text-align: left; }}
            th {{ background: #e3f2fd; }}
        </style>
    </head>
    <body>
        <h1>Relatório de Roteirização</h1>
        <h2>Resumo do Cenário</h2>
        <ul>
            <li><b>Data:</b> {cenario.get('data','')}</li>
            <li><b>Tipo:</b> {cenario.get('tipo','')}</li>
            <li><b>Pedidos Roteirizados:</b> {cenario.get('qtd_pedidos_roteirizados','')}</li>
            <li><b>Veículos Utilizados:</b> {cenario.get('qtd_veiculos_utilizados','')}</li>
            <li><b>Distância Total:</b> {cenario.get('distancia_total_real_m',0)/1000:.1f} km</li>
            <li><b>Peso Empenhado:</b> {cenario.get('peso_total_empenhado_kg',0):.1f} kg</li>
            <li><b>Status:</b> {cenario.get('status_solver','')}</li>
        </ul>
        <h2>Rotas Geradas</h2>
        <table>
            <tr><th>Veículo</th><th>Sequência</th><th>ID Pedido</th><th>Cliente</th><th>Endereço</th><th>Demanda</th></tr>
            {''.join(f'<tr><td>{row["Veículo"]}</td><td>{row["Sequencia"]}</td><td>{row.get("ID Pedido","")}</td><td>{row.get("Cliente","")}</td><td>{row.get("Endereço","")}</td><td>{row["Demanda"]}</td></tr>' for _, row in cenario.get('rotas',[]).iterrows()) if cenario.get('rotas') is not None else ''}
        </table>
    </body>
    </html>
    """
    return html
