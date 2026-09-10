import pandas as pd
import numpy as np

# Mapeo oficial de grupos
GRUPOS_ENTIDADES = {
    'Bancos Múltiples': ['BCR', 'BME', 'BIS', 'BNB', 'BEC', 'BGA', 'BNA', 'BUN'],
    'Entidades Especializadas en Microfinanzas': ['PCO', 'PEF', 'BFO', 'BPR', 'BIE', 'BSO']
}

def obtener_grupo_entidad(banco):
    for grupo, bancos in GRUPOS_ENTIDADES.items():
        if banco in bancos:
            return grupo
    return 'Sistema'

# ==============================================================================
# 1. KPI TEMPORALES MEJORADOS
# ==============================================================================

def calcular_kpi_temporales_tc(df_tc, entidad='Sistema'):
    """
    Calcula variaciones Diaria, Semanal, Mensual y Acumulada del TC con etiquetas de referencia.
    """
    df_entidad = df_tc[df_tc['Banco'] == entidad].sort_values('Fecha_dt').copy()
    
    if df_entidad.empty:
        return pd.DataFrame()

    df_entidad['TC_Dia'] = df_entidad['TC']
    
    # 1. Variación Diaria
    df_entidad['Fecha_Prev_Dia'] = df_entidad['Fecha_dt'].shift(1).dt.strftime('%d/%m')
    df_entidad['TC_Prev_Dia'] = df_entidad['TC_Dia'].shift(1)
    df_entidad['Var_Diaria_%'] = ((df_entidad['TC_Dia'] / df_entidad['TC_Prev_Dia']) - 1) * 100

    # 2. Variación Semanal (7 capturas atrás)
    df_entidad['Fecha_Prev_Sem'] = df_entidad['Fecha_dt'].shift(7).dt.strftime('%d/%m')
    df_entidad['TC_Prev_Sem'] = df_entidad['TC_Dia'].shift(7)
    df_entidad['Var_Semanal_%'] = ((df_entidad['TC_Dia'] / df_entidad['TC_Prev_Sem']) - 1) * 100

    # 3. Variación Mensual (Respecto al cierre de mes anterior)
    df_entidad['Anio_Mes'] = df_entidad['Fecha_dt'].dt.to_period('M')
    cierres_mes = df_entidad.groupby('Anio_Mes')['TC_Dia'].last().shift(1)
    fechas_cierre_mes = df_entidad.groupby('Anio_Mes')['Fecha_dt'].last().shift(1).dt.strftime('%d/%m')
    
    df_entidad['TC_Cierre_Mes_Ant'] = df_entidad['Anio_Mes'].map(cierres_mes)
    df_entidad['Fecha_Cierre_Mes_Ant'] = df_entidad['Anio_Mes'].map(fechas_cierre_mes)
    df_entidad['Var_Mensual_%'] = ((df_entidad['TC_Dia'] / df_entidad['TC_Cierre_Mes_Ant']) - 1) * 100

    # 4. Variación Acumulada (Respecto al inicio de la serie)
    fecha_ini = df_entidad['Fecha_dt'].iloc[0].strftime('%d/%m/%Y')
    tc_inicial = df_entidad['TC_Dia'].iloc[0]
    df_entidad['Var_Acumulada_%'] = ((df_entidad['TC_Dia'] / tc_inicial) - 1) * 100
    df_entidad['Fecha_Inicio_Serie'] = fecha_ini

    cols_salida = [
        'Fecha', 'Fecha_dt', 'Banco', 'TC', 'Var_Diaria_%', 'Fecha_Prev_Dia',
        'Var_Semanal_%', 'Fecha_Prev_Sem', 'Var_Mensual_%', 'Fecha_Cierre_Mes_Ant',
        'Var_Acumulada_%', 'Fecha_Inicio_Serie'
    ]
    return df_entidad[cols_salida]

# ==============================================================================
# 2. SERIES TEMPORALES PONDERADAS PARA GRÁFICOS EVOLUTIVOS COMPARATIVOS
# ==============================================================================

def obtener_series_evolutivas_comparativas(df_tc, df_cambiario, grupos_sel, bancos_sel):
    """
    Construye las series históricas de TC Ponderado y Monto Promedio por Operación
    para Sistema (fijo), Grupos seleccionados y Bancos específicos seleccionados.
    """
    df_tc_prep = df_tc.copy()
    df_tc_prep['Grupo'] = df_tc_prep['Banco'].apply(obtener_grupo_entidad)
    
    df_cam_prep = df_cambiario.copy()
    df_cam_prep['Grupo'] = df_cam_prep['Banco'].apply(obtener_grupo_entidad)

    # A. Serie Sistema (Fija)
    tc_sistema = df_tc_prep[df_tc_prep['Banco'] == 'Sistema'][['Fecha_dt', 'TC']].rename(columns={'TC': 'Sistema'})
    
    cam_sis = df_cam_prep[df_cam_prep['Banco'] == 'Sistema'].groupby('Fecha_dt').agg(
        Monto_Total=('Monto_Mm_USD', 'sum'),
        Op_Total=('Numero_Operaciones', 'sum')
    ).reset_index()
    cam_sis['Sistema'] = (cam_sis['Monto_Total'] * 1_000_000) / cam_sis['Op_Total']
    ticket_sistema = cam_sis[['Fecha_dt', 'Sistema']]

    # Listas de trazado
    df_evol_tc = tc_sistema.copy()
    df_evol_ticket = ticket_sistema.copy()

    # B. Agregación por Grupos de Entidades
    for grupo in grupos_sel:
        # TC Ponderado por Grupo
        tc_g = df_tc_prep[df_tc_prep['Grupo'] == grupo].groupby('Fecha_dt').agg(
            Monto_TC=('TC_Monto_Mm_USD', 'sum'),
            Monto_USD=('Monto_Mm_USD', 'sum')
        ).reset_index()
        tc_g[grupo] = tc_g['Monto_TC'] / tc_g['Monto_USD']
        df_evol_tc = pd.merge(df_evol_tc, tc_g[['Fecha_dt', grupo]], on='Fecha_dt', how='left')

        # Ticket Promedio por Grupo
        cam_g = df_cam_prep[df_cam_prep['Grupo'] == grupo].groupby('Fecha_dt').agg(
            Monto_Total=('Monto_Mm_USD', 'sum'),
            Op_Total=('Numero_Operaciones', 'sum')
        ).reset_index()
        cam_g[grupo] = (cam_g['Monto_Total'] * 1_000_000) / cam_g['Op_Total']
        df_evol_ticket = pd.merge(df_evol_ticket, cam_g[['Fecha_dt', grupo]], on='Fecha_dt', how='left')

    # C. Agregación por Bancos Individuales Seleccionados
    for banco in bancos_sel:
        tc_b = df_tc_prep[df_tc_prep['Banco'] == banco][['Fecha_dt', 'TC']].rename(columns={'TC': banco})
        df_evol_tc = pd.merge(df_evol_tc, tc_b, on='Fecha_dt', how='left')

        cam_b = df_cam_prep[df_cam_prep['Banco'] == banco].groupby('Fecha_dt').agg(
            Monto_Total=('Monto_Mm_USD', 'sum'),
            Op_Total=('Numero_Operaciones', 'sum')
        ).reset_index()
        cam_b[banco] = (cam_b['Monto_Total'] * 1_000_000) / cam_b['Op_Total']
        df_evol_ticket = pd.merge(df_evol_ticket, cam_b[['Fecha_dt', banco]], on='Fecha_dt', how='left')

    return df_evol_tc.sort_values('Fecha_dt'), df_evol_ticket.sort_values('Fecha_dt')

# ==============================================================================
# 3. ESTRUCTURA DE MERCADO Y RESUMEN
# ==============================================================================

def estructura_mercado_completa(df_cambiario, fecha_consulta, metrica='Monto'):
    col_valor = 'Monto_Mm_USD' if metrica == 'Monto' else 'Numero_Operaciones'
    
    df_dia = df_cambiario[(df_cambiario['Fecha'] == fecha_consulta) & (df_cambiario['Banco'] != 'Sistema')].copy()
    if df_dia.empty:
        return pd.DataFrame()

    pivot = df_dia.pivot(index='Banco', columns='Operacion', values=col_valor).fillna(0).reset_index()
    
    if 'Compra' not in pivot.columns: pivot['Compra'] = 0
    if 'Venta' not in pivot.columns: pivot['Venta'] = 0

    pivot['Total_Transado'] = pivot['Compra'] + pivot['Venta']
    pivot['Posicion_Neta'] = pivot['Compra'] - pivot['Venta']
    
    total_sistema = pivot['Total_Transado'].sum()
    pivot = pivot.sort_values(by='Total_Transado', ascending=False).reset_index(drop=True)
    
    pivot['Participacion_%'] = (pivot['Total_Transado'] / total_sistema * 100) if total_sistema > 0 else 0
    pivot['Pareto_%'] = pivot['Participacion_%'].cumsum()
    pivot['Rank'] = range(1, len(pivot) + 1)

    return pivot

def generar_resumen_inteligente(df_est, fecha_str, metrica='Monto'):
    if df_est.empty:
        return "Sin información suficiente para el resumen."

    fecha_fmt = pd.to_datetime(fecha_str).strftime('%d/%m/%Y')
    unidad = "Mm USD" if metrica == 'Monto' else "operaciones"
    
    top3 = df_est.head(3)
    part_top3_sum = top3['Participacion_%'].sum()
    texto_top3 = ", ".join([f"**{row['Banco']}** ({row['Participacion_%']:.2f}%)" for _, row in top3.iterrows()])
    
    max_comprador = df_est.sort_values(by='Posicion_Neta', ascending=False).iloc[0]
    max_vendedor = df_est.sort_values(by='Posicion_Neta', ascending=True).iloc[0]

    resumen = (
        f"Al **{fecha_fmt}**, la estructura operativa de **{metrica.lower()}s** muestra una alta concentración: "
        f"los tres principales actores son {texto_top3}, consolidando conjuntamente el **{part_top3_sum:.2f}%** del mercado total. "
        f"En términos de liquidez neta, **{max_comprador['Banco']}** lidera la posición compradora con "
        f"**+{max_comprador['Posicion_Neta']:,.2f} {unidad}**, mientras que **{max_vendedor['Banco']}** absorbe la mayor liquidez de venta "
        f"con **{max_vendedor['Posicion_Neta']:,.2f} {unidad}**."
    )
    return resumen

def calcular_hhi_operaciones(df_cambiario, metrica='Monto'):
    col_valor = 'Monto_Mm_USD' if metrica == 'Monto' else 'Numero_Operaciones'
    df_bancos = df_cambiario[df_cambiario['Banco'] != 'Sistema'].copy()

    def _hhi_dia(group):
        total = group[col_valor].sum()
        if total == 0: return 0
        part = (group[col_valor] / total) * 100
        return (part ** 2).sum()

    df_hhi = df_bancos.groupby('Fecha').apply(_hhi_dia).reset_index(name='HHI')
    
    condiciones = [
        (df_hhi['HHI'] < 1500),
        (df_hhi['HHI'] >= 1500) & (df_hhi['HHI'] <= 2500),
        (df_hhi['HHI'] > 2500)
    ]
    categorias = ['Baja Concentración', 'Moderadamente Concentrado', 'Altamente Concentrado']
    df_hhi['Nivel_Concentracion'] = np.select(condiciones, categorias, default='Sin datos')

    return df_hhi