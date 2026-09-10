import pandas as pd

def procesar_pestana_tc(filepath):
    """
    Procesa la pestaña 'TC' rellenando las fechas combinadas y concatenando 
    las métricas de Monto Mm Usd y Tipo Cambio Monto Mm Usd por Banco.
    """
    # 1. Leer desde la fila 8 (index 7 en Excel) donde están las columnas Fecha, Valores, BCR...
    df_raw = pd.read_excel(filepath, sheet_name='TC', skiprows=7)
    
    # 2. Rellenar hacia abajo las fechas nulas producidas por celdas combinadas
    df_raw['Fecha'] = df_raw['Fecha'].ffill()
    df_raw['Fecha'] = pd.to_datetime(df_raw['Fecha']).dt.strftime('%Y-%m-%d')
    
    # 3. Renombrar 'Total general' a 'Sistema' si existe
    if 'Total general' in df_raw.columns:
        df_raw.rename(columns={'Total general': 'Sistema'}, inplace=True)
        
    # 4. Filtrar por el contenido exacto de la columna 'Valores'
    df_monto = df_raw[df_raw['Valores'] == 'Monto Mm Usd'].drop(columns=['Valores'])
    df_tc_monto = df_raw[df_raw['Valores'] == 'Tipo Cambio Monto Mm Usd'].drop(columns=['Valores'])
    
    bancos = [col for col in df_monto.columns if col != 'Fecha']
    
    # 5. Transformar de formato ancho a formato largo (melt)
    melt_monto = df_monto.melt(id_vars=['Fecha'], value_vars=bancos, var_name='Banco', value_name='Monto_Mm_USD')
    melt_tc_monto = df_tc_monto.melt(id_vars=['Fecha'], value_vars=bancos, var_name='Banco', value_name='TC_Monto_Mm_USD')
    
    # 6. Unir los dos bloques y calcular el Tipo de Cambio (TC)
    df_tc = pd.merge(melt_monto, melt_tc_monto, on=['Fecha', 'Banco'])
    df_tc['TC'] = df_tc['TC_Monto_Mm_USD'] / df_tc['Monto_Mm_USD']
    
    # Ordenar manteniendo la secuencia original de los bancos
    df_tc['Banco'] = pd.Categorical(df_tc['Banco'], categories=bancos, ordered=True)
    df_tc = df_tc.sort_values(by=['Fecha', 'Banco']).reset_index(drop=True)
    df_tc['Banco'] = df_tc['Banco'].astype(str)
    
    # Retornar exactamente las columnas solicitadas
    return df_tc[['Fecha', 'Banco', 'Monto_Mm_USD', 'TC_Monto_Mm_USD', 'TC']]


def procesar_pestana_cv_individual(filepath, sheet_name, col_value_name, es_entero=False):
    """
    Procesa las pestañas C-V para devolver un DataFrame intercalado por Banco (Compra/Venta).
    """
    df_temp = pd.read_excel(filepath, sheet_name=sheet_name, header=None, nrows=15)
    header_row = None
    for idx, row in df_temp.iterrows():
        if 'Fecha' in row.values:
            header_row = idx
            break
            
    if header_row is None:
        header_row = 8

    df_raw = pd.read_excel(filepath, sheet_name=sheet_name, skiprows=header_row)
    df_raw = df_raw.dropna(subset=['Fecha']).copy()
    df_raw['Fecha'] = pd.to_datetime(df_raw['Fecha']).dt.strftime('%Y-%m-%d')
    
    cols_totales = list(df_raw.columns)
    idx_corte = None
    for i, col in enumerate(cols_totales):
        col_str = str(col).strip()
        if 'Total Compra' in col_str or 'Unnamed: 15' in col_str:
            idx_corte = i
            break
            
    if idx_corte is None:
        idx_corte = 15

    df_compra = df_raw.iloc[:, :idx_corte+1].copy()
    df_venta = pd.concat([df_raw.iloc[:, :1], df_raw.iloc[:, idx_corte+1:]], axis=1).copy()
    
    def limpiar_columnas(df_block):
        new_cols = []
        for col in df_block.columns:
            c = str(col).split('.')[0].strip()
            if 'Total Compra' in c or 'Total Venta' in c or 'Unnamed' in c:
                new_cols.append('Sistema')
            else:
                new_cols.append(c)
        df_block.columns = new_cols
        return df_block

    df_compra = limpiar_columnas(df_compra)
    df_venta = limpiar_columnas(df_venta)
    
    bancos = [c for c in df_compra.columns if c not in ['Fecha', 'Valores']]
    
    melt_c = df_compra.melt(id_vars=['Fecha'], value_vars=bancos, var_name='Banco', value_name=col_value_name)
    melt_c['Operacion'] = 'Compra'
    
    melt_v = df_venta.melt(id_vars=['Fecha'], value_vars=bancos, var_name='Banco', value_name=col_value_name)
    melt_v['Operacion'] = 'Venta'
    
    df_cv = pd.concat([melt_c, melt_v], ignore_index=True)
    
    df_cv['Banco'] = pd.Categorical(df_cv['Banco'], categories=bancos, ordered=True)
    df_cv['Operacion'] = pd.Categorical(df_cv['Operacion'], categories=['Compra', 'Venta'], ordered=True)
    
    df_cv = df_cv.sort_values(by=['Fecha', 'Banco', 'Operacion']).reset_index(drop=True)
    
    df_cv['Banco'] = df_cv['Banco'].astype(str)
    df_cv['Operacion'] = df_cv['Operacion'].astype(str)
    
    if es_entero:
        df_cv[col_value_name] = pd.to_numeric(df_cv[col_value_name], errors='coerce').astype('Int64')
    
    return df_cv[['Fecha', 'Banco', 'Operacion', col_value_name]]


def ejecutar_etl_mercado_cambiario(filepath='data/Base_Op_Cam.xlsx'):
    """
    Retorna las tres tablas corregidas:
    1. df_tc (Fecha, Banco, Monto_Mm_USD, TC_Monto_Mm_USD, TC)
    2. df_cv_mon
    3. df_cv_nop
    """
    df_tc = procesar_pestana_tc(filepath)
    df_cv_mon = procesar_pestana_cv_individual(filepath, 'C-V Monto', 'Monto_Mm_USD', es_entero=False)
    df_cv_nop = procesar_pestana_cv_individual(filepath, 'C-V N Op', 'Numero_Operaciones', es_entero=True)
    
    return df_tc, df_cv_mon, df_cv_nop

def consolidar_operaciones_cambiarias(df_cv_mon, df_cv_nop):
    """ Une las tablas de montos y número de operaciones en df_cambiario. """
    df_cambiario = pd.merge(
        df_cv_mon, 
        df_cv_nop, 
        on=['Fecha', 'Banco', 'Operacion'], 
        how='inner'
    )
    # Ticket promedio en USD por operación (opcional)
    df_cambiario['Monto_por_Op_USD'] = (df_cambiario['Monto_Mm_USD'] * 1_000_000) / df_cambiario['Numero_Operaciones']
    return df_cambiario

def ejecutar_etl_mercado_cambiario(filepath='data/Base_Op_Cam.xlsx'):
    df_tc = procesar_pestana_tc(filepath)
    df_cv_mon = procesar_pestana_cv_individual(filepath, 'C-V Monto', 'Monto_Mm_USD', es_entero=False)
    df_cv_nop = procesar_pestana_cv_individual(filepath, 'C-V N Op', 'Numero_Operaciones', es_entero=True)
    
    # Merge consolidado
    df_cambiario = consolidar_operaciones_cambiarias(df_cv_mon, df_cv_nop)
    
    return df_tc, df_cambiario