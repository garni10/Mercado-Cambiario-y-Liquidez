import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from etl_mc import ejecutar_etl_mercado_cambiario
from etl_liq import ejecutar_etl_liquidez
from indicadores_mc import (
    GRUPOS_ENTIDADES,
    calcular_kpi_temporales_tc,
    obtener_series_evolutivas_comparativas,
    estructura_mercado_completa,
    generar_resumen_inteligente,
    calcular_hhi_operaciones
)
from indicadores_liq import (
    calcular_ratio_bym_pcpl,
    calcular_posicion_act_pas,
    obtener_datos_cuadrante_liq
)

# 1. CONFIGURACIÓN INICIAL
st.set_page_config(
    page_title="Monitor Mercado Cambiario & Liquidez",
    page_icon="📈",
    layout="wide"
)

st.markdown("""
<style>
    .kpi-card {
        background-color: #0E1117;
        border: 1px solid #262730;
        border-radius: 10px;
        padding: 15px;
        text-align: center;
        margin-bottom: 10px;
    }
    .kpi-title { font-size: 13px; color: #A0A2A6; margin-bottom: 5px; font-weight: 500; }
    .kpi-value { font-size: 26px; font-weight: bold; color: #FFFFFF; margin-bottom: 8px; }
    .kpi-badge { display: inline-block; padding: 3px 10px; font-size: 11px; border-radius: 12px; font-weight: bold; }
    .badge-green { background-color: rgba(46, 204, 113, 0.15); color: #2ECC71; border: 1px solid #2ECC71; }
    .badge-red { background-color: rgba(231, 76, 60, 0.15); color: #E74C3C; border: 1px solid #E74C3C; }
</style>
""", unsafe_allow_html=True)

st.title("🏦 Plataforma de Seguimiento al Mercado Cambiario y Liquidez para el Sistema Financiero")
st.markdown("---")

# 2. CARGA BASE DE DATOS
@st.cache_data
def cargar_datos_totales():
    df_tc, df_cambiario = ejecutar_etl_mercado_cambiario('data/Base_Op_Cam.xlsx')
    df_bym, df_pcpl = ejecutar_etl_liquidez('data/Base PCam.xlsx')
    return df_tc, df_cambiario, df_bym, df_pcpl

try:
    df_tc, df_cambiario, df_bym, df_pcpl = cargar_datos_totales()
except Exception as e:
    st.error(f"Error al cargar las bases de datos: {e}")
    st.stop()

# Procesar indicadores de Liquidez
df_ratio_liq = calcular_ratio_bym_pcpl(df_bym, df_pcpl)
df_pos_actpas = calcular_posicion_act_pas(df_bym)

df_tc['Fecha_dt'] = pd.to_datetime(df_tc['Fecha'])
df_cambiario['Fecha_dt'] = pd.to_datetime(df_cambiario['Fecha'])

# 3. FILTROS EN BARRA LATERAL
st.sidebar.header("⚙️ Filtros Globales")

fechas_disponibles = df_tc['Fecha_dt'].dt.date.unique()
fecha_min, fecha_max = min(fechas_disponibles), max(fechas_disponibles)

fecha_seleccionada = st.sidebar.date_input(
    "📆 Fecha de Consulta Global:",
    value=fecha_max,
    min_value=fecha_min,
    max_value=fecha_max
)
fecha_str = fecha_seleccionada.strftime('%Y-%m-%d')
fecha_fmt_label = fecha_seleccionada.strftime('%d/%m/%Y')

st.sidebar.markdown("---")
st.sidebar.subheader("🎯 Filtros TC (Pestaña 1)")
bancos_todos = list(df_tc['Banco'].unique())
banco_kpi_sel = st.sidebar.selectbox("Entidad KPIs TC:", bancos_todos, index=bancos_todos.index('Sistema'))

grupos_opciones = list(GRUPOS_ENTIDADES.keys())
grupos_sel = st.sidebar.multiselect("Tipo Entidad TC:", grupos_opciones, default=grupos_opciones)

bancos_disponibles_grupos = [b for g in grupos_sel for b in GRUPOS_ENTIDADES[g]]
bancos_evol_sel = st.sidebar.multiselect("Bancos Específicos TC:", bancos_disponibles_grupos, default=[])

# 4. PESTAÑAS PRINCIPALES
tab_tc, tab_liquidez, tab_lcr = st.tabs(["💱 Tipo de Cambio (TC)", "💧 Liquidez del Sistema", "🏛️ LCR Basilea III"])

# ==============================================================================
# PESTAÑA 1: TIPO DE CAMBIO
# ==============================================================================
with tab_tc:
    st.subheader(f"📊 Indicadores Mercado Cambiario — {fecha_fmt_label}")
    
    kpi_tc_df = calcular_kpi_temporales_tc(df_tc, entidad=banco_kpi_sel)
    kpi_dia = kpi_tc_df[kpi_tc_df['Fecha'] == fecha_str]
    
    if not kpi_dia.empty:
        tc_act = kpi_dia['TC'].values[0]
        v_d, f_d = kpi_dia['Var_Diaria_%'].values[0], kpi_dia['Fecha_Prev_Dia'].values[0]
        v_s, f_s = kpi_dia['Var_Semanal_%'].values[0], kpi_dia['Fecha_Prev_Sem'].values[0]
        v_m, f_m = kpi_dia['Var_Mensual_%'].values[0], kpi_dia['Fecha_Cierre_Mes_Ant'].values[0]
        v_a, f_a = kpi_dia['Var_Acumulada_%'].values[0], kpi_dia['Fecha_Inicio_Serie'].values[0]

        def helper_kpi_card(titulo, valor_var, subtexto, etiqueta_badge):
            if pd.isnull(valor_var):
                txt_val, badge_cls = "N/A", "badge-green"
            else:
                signo = "+" if valor_var > 0 else ""
                txt_val = f"{signo}{valor_var:.2f}%"
                badge_cls = "badge-green" if valor_var >= 0 else "badge-red"
            return f"""
            <div class="kpi-card">
                <div class="kpi-title">{titulo}</div>
                <div class="kpi-value">{txt_val}</div>
                <div class="kpi-badge {badge_cls}">↑ {etiqueta_badge}: {subtexto}</div>
            </div>
            """

        c1, c2, c3, c4, c5 = st.columns(5)
        c1.markdown(f'<div class="kpi-card"><div class="kpi-title">TC Ponderado ({banco_kpi_sel})</div><div class="kpi-value">{tc_act:.4f}</div><div class="kpi-badge badge-green">Cierre del Día</div></div>', unsafe_allow_html=True)
        c2.markdown(helper_kpi_card("Var. Diaria", v_d, f_d, "Base"), unsafe_allow_html=True)
        c3.markdown(helper_kpi_card("Var. 7 Capturas Atrás", v_s, f_s, "Base"), unsafe_allow_html=True)
        c4.markdown(helper_kpi_card("vs Mes Anterior", v_m, f_m, "Cierre mes anterior"), unsafe_allow_html=True)
        c5.markdown(helper_kpi_card("Var. vs Inicio", v_a, f_a, "Serie completa"), unsafe_allow_html=True)

    st.markdown("---")

    df_evol_tc, df_evol_ticket = obtener_series_evolutivas_comparativas(df_tc, df_cambiario, grupos_sel, bancos_evol_sel)
    col_g1, col_g2 = st.columns(2)

    with col_g1:
        st.markdown("**Evolutivo Comparativo del Tipo de Cambio**")
        fig_tc = go.Figure()
        for col in df_evol_tc.columns:
            if col != 'Fecha_dt':
                fig_tc.add_trace(go.Scatter(
                    x=df_evol_tc['Fecha_dt'], y=df_evol_tc[col], name=col, mode='lines+markers',
                    line=dict(width=3 if col == 'Sistema' else 2, dash='solid' if col in ['Sistema'] + grupos_opciones else 'dot')
                ))
        fig_tc.update_layout(hovermode="x unified", xaxis_title="Fecha", yaxis_title="TC", xaxis=dict(type='date', tickformat='%d/%m/%y'), legend=dict(orientation="h", y=1.15))
        st.plotly_chart(fig_tc, use_container_width=True)

    with col_g2:
        st.markdown("**Evolutivo del Monto Promedio por Operación (USD / Op)**")
        fig_ticket = go.Figure()
        for col in df_evol_ticket.columns:
            if col != 'Fecha_dt':
                fig_ticket.add_trace(go.Scatter(
                    x=df_evol_ticket['Fecha_dt'], y=df_evol_ticket[col], name=col, mode='lines+markers',
                    line=dict(width=3 if col == 'Sistema' else 2, dash='solid' if col in ['Sistema'] + grupos_opciones else 'dot')
                ))
        fig_ticket.update_layout(hovermode="x unified", xaxis_title="Fecha", yaxis_title="USD / Op", xaxis=dict(type='date', tickformat='%d/%m/%y'), legend=dict(orientation="h", y=1.15))
        st.plotly_chart(fig_ticket, use_container_width=True)

    st.markdown("---")

    col_sel, _ = st.columns([3, 3])
    with col_sel:
        metrica_sel = st.radio("Ver Estructura de Mercado por:", ["Monto", "Número de Operaciones"], horizontal=True)

    metrica_key = 'Monto' if metrica_sel == "Monto" else 'Operaciones'
    df_est = estructura_mercado_completa(df_cambiario, fecha_consulta=fecha_str, metrica=metrica_key)

    if not df_est.empty:
        g_c1, g_c2 = st.columns(2)
        df_compra_sorted = df_est.sort_values(by='Compra', ascending=False)
        orden_bancos_compra = df_compra_sorted['Banco'].tolist()

        with g_c1:
            fig_compra = px.bar(df_compra_sorted, x='Banco', y='Compra', title=f"Volumen de Compra ({'Mm USD' if metrica_key=='Monto' else 'Operaciones'})", color_discrete_sequence=['#2980B9'], text_auto='.2f' if metrica_key=='Monto' else 'd')
            st.plotly_chart(fig_compra, use_container_width=True)

        with g_c2:
            fig_venta = px.bar(df_est, x='Banco', y='Venta', title=f"Volumen de Venta ({'Mm USD' if metrica_key=='Monto' else 'Operaciones'}) [Ordenado por Compra]", color_discrete_sequence=['#E74C3C'], text_auto='.2f' if metrica_key=='Monto' else 'd')
            fig_venta.update_xaxes(categoryorder='array', categoryarray=orden_bancos_compra)
            st.plotly_chart(fig_venta, use_container_width=True)

        g_c3, g_c4 = st.columns(2)
        with g_c3:
            df_pos_sorted = df_est.sort_values(by='Posicion_Neta', ascending=False)
            fig_pos = px.bar(df_pos_sorted, x='Banco', y='Posicion_Neta', title=f"Posición Neta Compra-Venta ({'Mm USD' if metrica_key=='Monto' else 'Operaciones'})", color='Posicion_Neta', color_continuous_scale='Spectral', text_auto='.2f' if metrica_key=='Monto' else 'd')
            st.plotly_chart(fig_pos, use_container_width=True)

        with g_c4:
            fig_pareto = px.line(df_est, x='Banco', y='Pareto_%', markers=True, title="Acumulado % de Mercado (Curva de Pareto)", color_discrete_sequence=['#8E44AD'])
            fig_pareto.add_hline(y=80, line_dash="dash", line_color="red", annotation_text="80%")
            st.plotly_chart(fig_pareto, use_container_width=True)

        st.info(f"💡 **Resumen Analítico del Mercado:**\n\n{generar_resumen_inteligente(df_est, fecha_str, metrica=metrica_key)}")

# ==============================================================================
# PESTAÑA 2: LIQUIDEZ Y BALANCES
# ==============================================================================
with tab_liquidez:
    st.subheader("💧 Análisis de Liquidez y Estructura de Balance")
    
    ult_fecha_liq = df_ratio_liq['Fecha'].max()
    ult_fecha_fmt = pd.to_datetime(ult_fecha_liq).strftime('%d/%m/%Y')

    col_m1, _ = st.columns([2, 4])
    with col_m1:
        moneda_liq_sel = st.selectbox("💱 Selecciona Moneda para los Gráficos:", ["Consolidado", "MN", "ME"], index=0)

    # Función flexible para armar evolutivos considerando el filtro dinámico de Entidades/Bancos
    def armar_evolutivo_liq_filtro(df_origen, col_valor, moneda, modo_agregacion='sum'):
        df_f = df_origen[df_origen['Moneda'] == moneda].copy()
        
        def assign_group(b):
            for g, lst in GRUPOS_ENTIDADES.items():
                if b in lst: return g
            return 'Sistema'
        
        df_f['Grupo'] = df_f['Banco'].apply(assign_group)
        
        # Base de datos pivoteada por entidad
        df_pivot = pd.DataFrame({'Fecha_dt': df_f['Fecha_dt'].unique()}).sort_values('Fecha_dt')
        
        # 1. Sistema siempre se incluye
        df_sis = df_f[df_f['Banco'] == 'Sistema'][['Fecha_dt', col_valor]].rename(columns={col_valor: 'Sistema'})
        df_pivot = pd.merge(df_pivot, df_sis, on='Fecha_dt', how='left')

        # 2. Agregar por Grupos seleccionados (BM, EEM, etc.)
        for g in grupos_sel:
            df_g = df_f[df_f['Grupo'] == g]
            if modo_agregacion == 'sum':
                # Suma de Balances (Activo - Pasivo)
                series_g = df_g.groupby('Fecha_dt')[col_valor].sum().reset_index().rename(columns={col_valor: g})
            else:
                # Promedio Ponderado / Simple para Ratios (%)
                series_g = df_g.groupby('Fecha_dt')[col_valor].mean().reset_index().rename(columns={col_valor: g})
            df_pivot = pd.merge(df_pivot, series_g, on='Fecha_dt', how='left')

        # 3. Agregar Bancos Específicos seleccionados en el sidebar
        for b in bancos_evol_sel:
            if b in df_f['Banco'].unique():
                series_b = df_f[df_f['Banco'] == b][['Fecha_dt', col_valor]].rename(columns={col_valor: b})
                df_pivot = pd.merge(df_pivot, series_b, on='Fecha_dt', how='left')

        return df_pivot.sort_values('Fecha_dt')

# --- BLOQUE 1: INDICADOR ByM / PCPL (%) ---
    df_evol_bym = armar_evolutivo_liq_filtro(df_ratio_liq, 'Ratio_ByM_PCPL_%', moneda_liq_sel, modo_agregacion='mean')
    
    col_l1, col_l2 = st.columns(2)
    with col_l1:
        st.markdown(f"**Evolutivo Cobertura ByM / Pasivos CPL (%) — [{moneda_liq_sel}]**")
        fig_e_bym = go.Figure()
        for col in df_evol_bym.columns:
            if col != 'Fecha_dt':
                fig_e_bym.add_trace(go.Scatter(
                    x=df_evol_bym['Fecha_dt'], y=df_evol_bym[col], name=col, mode='lines+markers',
                    line=dict(width=3 if col=='Sistema' else 2)
                ))
        fig_e_bym.update_layout(
            hovermode="x unified",
            yaxis_title="Ratio (%)",
            xaxis=dict(type='date', tickformat='%d/%m/%y'),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
        )
        st.plotly_chart(fig_e_bym, use_container_width=True)

    with col_l2:
        st.markdown(f"**Cobertura ByM / Pasivos CPL por Banco — [{ult_fecha_fmt}]**")
        df_bar_bym = df_ratio_liq[
            (df_ratio_liq['Fecha'] == ult_fecha_liq) & 
            (df_ratio_liq['Moneda'] == moneda_liq_sel) & 
            (df_ratio_liq['Banco'] != 'Sistema')
        ].copy()
        
        # 1. Forzar tipo de dato numérico continuo para evitar interpretación de texto/categoría
        df_bar_bym['Ratio_ByM_PCPL_%'] = pd.to_numeric(df_bar_bym['Ratio_ByM_PCPL_%'], errors='coerce').fillna(0)
        df_bar_bym = df_bar_bym.sort_values(by='Ratio_ByM_PCPL_%', ascending=False)
        
        # 2. Construcción explícita de escala continua
        fig_b_bym = px.bar(
            df_bar_bym, 
            x='Banco', 
            y='Ratio_ByM_PCPL_%',
            color='Ratio_ByM_PCPL_%', 
            color_continuous_scale='Viridis', 
            labels={'Ratio_ByM_PCPL_%': 'Ratio_ByM_PCPL_%'},
            text_auto='.2f'
        )
        
        # 3. Asegurar que la barra de color continua esté habilitada explícitamente
        fig_b_bym.update_layout(
            xaxis_type='category',
            coloraxis_showscale=True
        )
        st.plotly_chart(fig_b_bym, use_container_width=True)

    st.markdown("---")

    # --- BLOQUE 2: POSICIÓN ACTIVO - PASIVO (Mm Bs) ---
    df_evol_pos = armar_evolutivo_liq_filtro(df_pos_actpas, 'Posicion_Neta_Mm_Bs', moneda_liq_sel, modo_agregacion='sum')

    col_l3, col_l4 = st.columns(2)
    with col_l3:
        st.markdown(f"**Evolutivo Posición Neta Activo - Pasivo (Mm Bs) — [{moneda_liq_sel}]**")
        fig_e_pos = go.Figure()
        for col in df_evol_pos.columns:
            if col != 'Fecha_dt':
                fig_e_pos.add_trace(go.Scatter(
                    x=df_evol_pos['Fecha_dt'], y=df_evol_pos[col], name=col, mode='lines+markers',
                    line=dict(width=3 if col=='Sistema' else 2)
                ))
        fig_e_pos.update_layout(
            hovermode="x unified",
            yaxis_title="Mm Bs",
            xaxis=dict(type='date', tickformat='%d/%m/%y'),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
        )
        st.plotly_chart(fig_e_pos, use_container_width=True)

    with col_l4:
        st.markdown(f"**Posición Neta Activo - Pasivo por Banco — [{ult_fecha_fmt}]**")
        df_bar_pos = df_pos_actpas[
            (df_pos_actpas['Fecha'] == ult_fecha_liq) & 
            (df_pos_actpas['Moneda'] == moneda_liq_sel) & 
            (df_pos_actpas['Banco'] != 'Sistema')
        ].sort_values(by='Posicion_Neta_Mm_Bs', ascending=False)
        
        # Se activa la escala de color visible al lado derecho
        fig_b_pos = px.bar(
            df_bar_pos, x='Banco', y='Posicion_Neta_Mm_Bs',
            color='Posicion_Neta_Mm_Bs', 
            color_continuous_scale='Tealgrn', 
            labels={'Posicion_Neta_Mm_Bs': 'Posicion_Neta'},
            text_auto='.2f'
        )
        fig_b_pos.update_layout(
            xaxis_type='category'
        )
        st.plotly_chart(fig_b_pos, use_container_width=True)

    st.markdown("---")

# --- BLOQUE 3: DISPERSIÓN DE 4 CUADRANTES (ME) ---
    st.markdown("### 🧭 Matriz de Dispersión y Diagnóstico de Riesgo (Moneda Extranjera)")
    st.caption("Eje Y: Ratio Liquidez (ByM/PCPL) | Eje X: Posición Cambiaria (Activo - Pasivo ME) | Tamaño Burbuja: Activos ME")

    fechas_list_liq = sorted(list(df_ratio_liq['Fecha'].unique()))
    fecha_quad_str = st.select_slider(
        "🎛️ Desplaza para evaluar el comportamiento en el tiempo:",
        options=fechas_list_liq,
        value=ult_fecha_liq
    )

    df_quad, avg_x_pos, avg_y_liq = obtener_datos_cuadrante_liq(df_ratio_liq, df_pos_actpas, fecha_quad_str)

    if not df_quad.empty:
        fig_quad = px.scatter(
            df_quad,
            x='Posicion_Neta_Mm_Bs',
            y='Ratio_ByM_PCPL_%',
            size='Activo',
            text='Banco',
            color='Banco',
            size_max=45,
            title=f"Matriz Liquidez vs Posición Cambiaria ME al {pd.to_datetime(fecha_quad_str).strftime('%d/%m/%Y')}"
        )

        # 1. Línea vertical delgada en 0 (Límite Posición Corta/Larga)
        fig_quad.add_vline(
            x=0, 
            line_width=1, 
            line_dash="solid", 
            line_color="rgba(255, 255, 255, 0.2)", # Mismo todo gris tenue de la grilla Plotly
            annotation_text="Posición Corta (x < 0)", 
            annotation_position="top left"
        )

        # 2. Cortantes centrados en el Promedio de los 13 Bancos
        fig_quad.add_vline(x=avg_x_pos, line_dash="dash", line_color="#E74C3C", annotation_text=f"Prom. 13 Bancos ({avg_x_pos:,.1f} Mm)")
        fig_quad.add_hline(y=avg_y_liq, line_dash="dash", line_color="#2ECC71", annotation_text=f"Prom. 13 Bancos ({avg_y_liq:.2f}%)")

        fig_quad.update_traces(textposition='top center')
        fig_quad.update_layout(
            xaxis_title="Posición Cambiaria ME (Activo - Pasivo Mm Bs)",
            yaxis_title="Ratio Cobertura Liquidez ME (%)",
            height=600,
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
        )

        st.plotly_chart(fig_quad, use_container_width=True)
    else:
        st.warning("No existen suficientes registros de Moneda Extranjera para la fecha seleccionada.")

# ==============================================================================
# PESTAÑA 3: LCR BASILEA III
# ==============================================================================
with tab_lcr:
    st.subheader("🏛️ Ratio de Cobertura de Liquidez (LCR) — Basilea III")
    st.markdown("---")
    st.warning("⚠️ **Módulo en construcción Papus** 🚧")
    st.markdown("""
    Próximas integraciones analíticas:
    * **HQLA** (Activos Líquidos de Alta Calidad Nivel 1 y Nivel 2).
    * **Salidas y Entradas Netas de Efectivo Estresadas a 30 días**.
    * **NSFR** (Ratio de Fondeo Estable Neto).
    """)