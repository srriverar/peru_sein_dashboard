# Cómo contribuir

¡Gracias por su interés! Este proyecto se construye con datos abiertos y criterio técnico.

## Tipos de aporte
1. **Datos con fuente** — tablas de centrales (COES), capacidades térmicas de líneas, demanda horaria, caudales (ANA), Niño costero (ENFEN).
2. **Correcciones** — si detecta un valor ESTIMADO que no cuadra con una fuente oficial, indique la fuente y el valor.
3. **Código** — nuevas páginas, pruebas, mejoras del modelo (flujo DC/AC, DLR con IEEE 738).
4. **Documentación** — metodología, casos de estudio, traducciones.

## Flujo de trabajo
1. Abra un *issue* describiendo el dato o la mejora.
2. Haga un *fork* o rama, edite el CSV correspondiente en `data/reference/` manteniendo las columnas.
3. Pruebe localmente: `streamlit run app.py` y revise la pestaña 🔴 Congestión y GET con el panel *Usar datos propios*.
4. Abra un *pull request* incluyendo en la descripción: **fuente**, **fecha de consulta** y **unidad**.

## Reglas para los datos
- Cada cambio debe citar fuente oficial o publicación verificable.
- No suba datos con restricciones de licencia sin autorización.
- Mantenga las unidades: MW, MWh, km, kV, USD/MWh.
- Si un valor es supuesto, márquelo como `ESTIMADO` en la columna de fuente.

## Código de conducta
Trato respetuoso, críticas técnicas con evidencia y atribución clara de los aportes.
