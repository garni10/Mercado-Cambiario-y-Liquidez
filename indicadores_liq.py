import pandas as pd

def calcular_ratio_bym_pcpl(df_bym, df_pcpl):
    """Relaciona Billetes y Monedas (AP-ByM) contra Pasivos de Corto Plazo (PCPL)."""
    df_bym_filt = df_bym[
        df_bym['Descripcion'].str.contains('Billetes y moneda', case=False, na=False)
    ][['Fecha', 'Banco', 'Moneda', 'Monto_Mm_Bs']].rename(columns={'Monto_Mm_Bs': 'ByM_Mm_Bs'})

    df_pcpl_filt = df_pcpl[['Fecha', 'Banco', 'Moneda', 'Monto_Mm_Bs']].rename(columns={'Monto_Mm_Bs': 'Pasivos_CPL_Mm_Bs'})

    df_ratio = pd.merge(df_bym_filt, df_pcpl_filt, on=['Fecha', 'Banco', 'Moneda'], how='inner')

    df_ratio['Ratio_ByM_PCPL_%'] = (df_ratio['ByM_Mm_Bs'] / df_ratio['Pasivos_CPL_Mm_Bs'].replace(0, pd.NA)) * 100
    df_ratio['Ratio_ByM_PCPL_%'] = df_ratio['Ratio_ByM_PCPL_%'].fillna(0)
    df_ratio['Fecha_dt'] = pd.to_datetime(df_ratio['Fecha'])

    return df_ratio.sort_values(['Fecha_dt', 'Banco'])

def calcular_posicion_act_pas(df_bym):
    """Calcula Posición Neta: Activo Total - Pasivo Total (Mm Bs)."""
    df_act = df_bym[df_bym['Descripcion'].str.strip() == 'ACTIVO'][['Fecha', 'Banco', 'Moneda', 'Monto_Mm_Bs']].rename(columns={'Monto_Mm_Bs': 'Activo'})
    df_pas = df_bym[df_bym['Descripcion'].str.strip() == 'PASIVO'][['Fecha', 'Banco', 'Moneda', 'Monto_Mm_Bs']].rename(columns={'Monto_Mm_Bs': 'Pasivo'})

    df_pos = pd.merge(df_act, df_pas, on=['Fecha', 'Banco', 'Moneda'], how='inner')
    df_pos['Posicion_Neta_Mm_Bs'] = df_pos['Activo'] - df_pos['Pasivo']
    df_pos['Fecha_dt'] = pd.to_datetime(df_pos['Fecha'])

    return df_pos.sort_values(['Fecha_dt', 'Banco'])

def obtener_datos_cuadrante_liq(df_ratio, df_pos, fecha_sel):
    """
    Combina Ratio Liquidez ME (Y) y Posición Cambiaria ME (X).
    Cortes de cuadrantes basados en el Promedio de los 13 bancos.
    """
    r_me = df_ratio[(df_ratio['Fecha'] == fecha_sel) & (df_ratio['Moneda'] == 'ME') & (df_ratio['Banco'] != 'Sistema')]
    p_me = df_pos[(df_pos['Fecha'] == fecha_sel) & (df_pos['Moneda'] == 'ME') & (df_pos['Banco'] != 'Sistema')]

    df_quad = pd.merge(
        r_me[['Banco', 'Ratio_ByM_PCPL_%']],
        p_me[['Banco', 'Posicion_Neta_Mm_Bs', 'Activo', 'Pasivo']],
        on='Banco', how='inner'
    )

    if not df_quad.empty:
        avg_activos = df_quad['Activo'].mean()
        avg_pasivos = df_quad['Pasivo'].mean()
        avg_x = avg_activos - avg_pasivos
        avg_y = df_quad['Ratio_ByM_PCPL_%'].mean()
    else:
        avg_x, avg_y = 0, 0

    return df_quad, avg_x, avg_y