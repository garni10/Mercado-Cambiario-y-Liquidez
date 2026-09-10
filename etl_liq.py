import pandas as pd
import re

def limpiar_descripcion(texto):
    """Elimina prefijos numéricos iniciales (ej. '111.01 Billetes...' -> 'Billetes...')"""
    if pd.isna(texto):
        return texto
    return re.sub(r'^\d+(\.\d+)*\s*', '', str(texto)).strip()

def procesar_pestana_bym(df_raw):
    """Procesa la pestaña AP-ByM (Cabeceras en fila 4 / índice 3)"""
    df = df_raw.copy()
    df.columns = df.iloc[3]
    df = df.iloc[4:].reset_index(drop=True)
    
    cols = list(df.columns)
    cols[0], cols[1], cols[2] = 'Fecha', 'Descripcion', 'Cod_Sigla'
    df.columns = cols
    
    if 'Total general' in df.columns:
        df = df.rename(columns={'Total general': 'Sistema'})

    df['Fecha'] = df['Fecha'].ffill()
    df['Fecha'] = pd.to_datetime(df['Fecha']).dt.strftime('%Y-%m-%d')
    df['Descripcion'] = df['Descripcion'].ffill().apply(limpiar_descripcion)

    mapa_moneda = {'MN': 'MN', 'MNMV': 'MN', 'MNUFV': 'MN', 'ME': 'ME'}
    df['Moneda_Grupo'] = df['Cod_Sigla'].astype(str).str.strip().map(mapa_moneda)
    df = df.dropna(subset=['Moneda_Grupo'])

    columnas_bancos = [c for c in df.columns if c not in ['Fecha', 'Descripcion', 'Cod_Sigla', 'Moneda_Grupo'] and pd.notna(c)]
    
    for c in columnas_bancos:
        df[c] = pd.to_numeric(df[c], errors='coerce').fillna(0)

    # Agregación MN y ME
    df_grouped = df.groupby(['Fecha', 'Descripcion', 'Moneda_Grupo'])[columnas_bancos].sum().reset_index()

    # Consolidado (MN + ME)
    df_cons = df_grouped.groupby(['Fecha', 'Descripcion'])[columnas_bancos].sum().reset_index()
    df_cons['Moneda_Grupo'] = 'Consolidado'

    df_wide = pd.concat([df_grouped, df_cons], ignore_index=True)

    df_long = df_wide.melt(
        id_vars=['Fecha', 'Descripcion', 'Moneda_Grupo'],
        value_vars=columnas_bancos,
        var_name='Banco',
        value_name='Monto_Mm_Bs'
    ).rename(columns={'Moneda_Grupo': 'Moneda'})

    return df_long

def procesar_pestana_pcpl(df_raw):
    """Procesa la pestaña PCPL (Cabeceras en fila 5 / índice 4)"""
    # Extraer nombre de la cuenta desde B1 (fila 0, col 1)
    cuenta_nombre = limpiar_descripcion(df_raw.iloc[0, 1]) 
    if not cuenta_nombre or cuenta_nombre == 'nan':
        cuenta_nombre = "Pasivo de corto plazo"

    df = df_raw.copy()
    df.columns = df.iloc[4] # Fila 5 de Excel
    df = df.iloc[5:].reset_index(drop=True)
    
    cols = list(df.columns)
    cols[0], cols[1] = 'Fecha', 'Cod_Sigla'
    df.columns = cols
    
    if 'Total general' in df.columns:
        df = df.rename(columns={'Total general': 'Sistema'})

    df['Fecha'] = df['Fecha'].ffill()
    df['Fecha'] = pd.to_datetime(df['Fecha']).dt.strftime('%Y-%m-%d')
    df['Descripcion'] = cuenta_nombre

    mapa_moneda = {'MN': 'MN', 'MNMV': 'MN', 'MNUFV': 'MN', 'ME': 'ME'}
    df['Moneda_Grupo'] = df['Cod_Sigla'].astype(str).str.strip().map(mapa_moneda)
    df = df.dropna(subset=['Moneda_Grupo'])

    columnas_bancos = [c for c in df.columns if c not in ['Fecha', 'Cod_Sigla', 'Descripcion', 'Moneda_Grupo'] and pd.notna(c)]
    
    for c in columnas_bancos:
        df[c] = pd.to_numeric(df[c], errors='coerce').fillna(0)

    # Agregación MN y ME
    df_grouped = df.groupby(['Fecha', 'Descripcion', 'Moneda_Grupo'])[columnas_bancos].sum().reset_index()

    # Consolidado (MN + ME)
    df_cons = df_grouped.groupby(['Fecha', 'Descripcion'])[columnas_bancos].sum().reset_index()
    df_cons['Moneda_Grupo'] = 'Consolidado'

    df_wide = pd.concat([df_grouped, df_cons], ignore_index=True)

    df_long = df_wide.melt(
        id_vars=['Fecha', 'Descripcion', 'Moneda_Grupo'],
        value_vars=columnas_bancos,
        var_name='Banco',
        value_name='Monto_Mm_Bs'
    ).rename(columns={'Moneda_Grupo': 'Moneda'})

    return df_long

def ejecutar_etl_liquidez(ruta_excel='data/Base PCam.xlsx'):
    """Carga y procesa ambas pestañas de Liquidez"""
    xls = pd.ExcelFile(ruta_excel)
    
    df_bym_raw = pd.read_excel(xls, sheet_name='AP-ByM', header=None)
    df_bym = procesar_pestana_bym(df_bym_raw)
    
    df_pcpl_raw = pd.read_excel(xls, sheet_name='PCPL', header=None)
    df_pcpl = procesar_pestana_pcpl(df_pcpl_raw)
    
    return df_bym, df_pcpl