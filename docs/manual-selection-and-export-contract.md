# Contrato de selección manual y exportación de altas

Estado: implementado en `main` · contrato funcional vigente  
Alcance: preparación y exportación de altas de productos del WooCommerce Catalog Toolkit  
No incluye: actualización de productos existentes, escritura directa en WooCommerce ni selección masiva.

Este documento describe el comportamiento que debe mantenerse en el código y en sus pruebas. No representa una lista de tareas de implementación pendientes.

## 1. Principios

1. La clasificación técnica y la selección comercial son decisiones independientes.
2. La herramienta no selecciona productos automáticamente.
3. El precio puede definir el orden inicial de presentación, pero nunca decide qué productos se incorporan.
4. La asignación de categoría destino es independiente de la selección de productos.
5. La exportación incluye exclusivamente productos seleccionados, técnicamente aptos y con destino confirmado.
6. No existen cupos, límites ni cuotas por categoría.
7. La preparación genera un archivo para WooCommerce; no escribe ni publica directamente en la tienda.

## 2. Identidad de producto

- La identidad de una fila dentro de una sesión de proveedor es `row_number`, correspondiente al número de fila original del CSV.
- La numeración comienza en 2 para contemplar la fila de encabezados.
- No usar SKU como clave de selección: puede faltar o estar duplicado.
- `row_number` debe conservarse al filtrar, buscar, ordenar, expandir o contraer categorías.
- La identidad solo es válida para el archivo de proveedor cargado en esa sesión.
- Reemplazar el archivo del proveedor inicia una sesión nueva y reinicia las decisiones asociadas.

## 3. Estado de selección

El estado comercial mínimo por fila es:

```python
selection_state = {
    row_number: "SELECTED" | "NOT_SELECTED"
}
```

Reglas:

- Todas las filas comienzan en `NOT_SELECTED`.
- Solo filas clasificadas como `READY` pueden pasar a `SELECTED`.
- Filas `REVIEW`, `BLOCKED` y `EXCLUDED` no pueden seleccionarse.
- La selección cambia mediante una acción explícita e individual del usuario.
- La selección persiste al navegar, buscar, filtrar, ordenar o cambiar la presentación de categorías durante la sesión.
- Reemplazar el archivo del proveedor reinicia todas las selecciones.
- Al recalcular la preparación, se conservan las selecciones de filas que continúan en estado `READY`.
- Una fila que deja de ser `READY` vuelve a `NOT_SELECTED`. Si posteriormente vuelve a ser `READY`, no se selecciona automáticamente.
- El estado es de sesión: no se persiste en base de datos ni entre sesiones.

Implementación de referencia:
- `src/application/product_selection.py`: inicialización, validación y modificación inmutable del estado; cálculo de filas exportables.
- `src/application/catalog_preparation.py`: integración entre clasificación técnica, estado comercial, destinos confirmados y filas de exportación.
- `src/ui/nicegui_app.py`: interacción individual y estado de la sesión en la interfaz.

## 4. Elegibilidad técnica

La clasificación técnica se delega en `prepare_add_products()`; la capa de selección no debe duplicar sus validaciones.

- `READY`: producto técnicamente apto para una posible alta.
- `REVIEW`: requiere revisión; no seleccionable.
- `BLOCKED`: no puede prepararse; no seleccionable.
- `EXCLUDED`: ya existe en la referencia de WooCommerce; no corresponde a un alta nueva.

La elegibilidad técnica no equivale a selección comercial. Un producto `READY` permanece `NOT_SELECTED` hasta que el usuario lo elija.

La falta de destino confirmado no cambia el estado técnico `READY`; solo impide que el producto sea exportable.

## 5. Destinos de categorías

- El destino WooCommerce se configura por categoría de proveedor.
- El destino es una decisión independiente de la selección de productos.
- Una categoría sin destino confirmado puede contener productos seleccionados.
- Cambiar un destino invalida su confirmación anterior.
- Una sugerencia automática no equivale a confirmación del usuario.
- Solo un destino confirmado habilita la exportación de los productos seleccionados y aptos de esa categoría.
- Confirmar o cambiar un destino no selecciona ni deselecciona productos.

La capa de preparación recibe los mapeos que ya fueron confirmados por la interfaz; no debe interpretar una sugerencia como confirmación.

## 6. Regla de exportación

Un producto es exportable si y solo si cumple simultáneamente:

```text
selection_state[row_number] == SELECTED
AND technical_status == READY
AND category_destination is confirmed
```

- La elegibilidad se obtiene de la clasificación técnica vigente.
- La confirmación del destino debe corresponder a la categoría del producto.
- Las filas exportables se derivan de esas condiciones, nunca de un cupo ni del orden visual.
- La exportación debe conservar `row_number` para trazabilidad interna, sin agregarlo al CSV de WooCommerce salvo que el formato lo requiera expresamente.
- Mantener el formato de altas acordado: producto simple, borrador (`Published = -1`), precio de proveedor mapeado y categoría destino confirmada.
- No incluir productos existentes, duplicados, bloqueados, en revisión, no seleccionados o sin destino confirmado.
- Generar el CSV no debe mutar los datos de entrada ni el estado de selección.

Implementación de referencia: `get_exportable_row_numbers()` en `src/application/product_selection.py` y construcción de `export_rows` en `src/application/catalog_preparation.py`.

## 7. Interfaz y flujo

El flujo vigente se organiza en cuatro etapas:

1. **Archivos:** carga y configuración de los archivos de proveedor y WooCommerce.
2. **Validación:** clasificación técnica y comparación del catálogo.
3. **Selección:** configuración de destinos y selección individual de productos.
4. **Exportación:** revisión del conjunto exportable y descarga del CSV.

Reglas de interfaz:

- Mostrar los productos agrupados por categoría de proveedor.
- Presentar los productos elegibles sin seleccionar inicialmente.
- Permitir selección individual; no mostrar controles de cupo ni acciones de inclusión automática por categoría.
- Los productos no seleccionables muestran su estado y motivo, sin control de selección habilitado.
- Mostrar por separado los productos seleccionados y los que están efectivamente listos para exportar.
- Buscar, ordenar, filtrar, expandir y contraer no debe alterar las decisiones.
- El orden inicial por precio es una ayuda de revisión, no una recomendación ni una selección automática.
- La categoría participa en el lote cuando contiene uno o más productos seleccionados; esto no sustituye la confirmación del destino.

## 8. Criterios de aceptación y regresión

Estos criterios son una lista de verificación permanente para cambios futuros. Una modificación del flujo debe mantenerlos o documentar explícitamente el cambio de contrato.

### Selección

- [ ] Al iniciar una sesión, todas las filas están `NOT_SELECTED`.
- [ ] Un producto `READY` puede seleccionarse y deseleccionarse individualmente.
- [ ] Un producto `REVIEW`, `BLOCKED` o `EXCLUDED` no puede seleccionarse.
- [ ] Dos filas con SKU duplicado mantienen estados independientes por `row_number`.
- [ ] Ordenar, filtrar o navegar no cambia las selecciones.
- [ ] Reemplazar el proveedor reinicia el estado.
- [ ] Recalcular no selecciona productos automáticamente.
- [ ] Una fila que deja de ser `READY` pierde su selección.

### Destinos

- [ ] Seleccionar un producto no exige tener destino confirmado.
- [ ] Cambiar el destino invalida la confirmación anterior.
- [ ] Cambiar el destino no modifica la selección.
- [ ] Una categoría sin destino confirmado no aporta filas al CSV.
- [ ] Confirmar un destino habilita únicamente los productos seleccionados y aptos de esa categoría.

### Exportación

- [ ] Se exportan únicamente filas `SELECTED + READY + destino confirmado`.
- [ ] Un producto seleccionado sin destino no se exporta.
- [ ] Un producto no seleccionado con destino confirmado no se exporta.
- [ ] Productos `REVIEW`, `BLOCKED` y `EXCLUDED` nunca aparecen en el CSV.
- [ ] El orden visual no altera el conjunto exportado.
- [ ] La exportación no muta los datos de entrada ni el estado de selección.
- [ ] El CSV conserva el formato de altas acordado.

## 9. Fuera de alcance

- Selección automática por precio.
- Cupos, límites o cuotas por categoría.
- Selección masiva o «seleccionar todos».
- Recomendaciones comerciales automáticas.
- Persistencia de la selección entre sesiones.
- Actualización de productos existentes.
- Escritura directa en WooCommerce mediante API.

## 10. Mantenimiento del contrato

Ante cambios en selección, elegibilidad, destinos o exportación:

1. Actualizar las pruebas de regresión correspondientes.
2. Mantener separadas la clasificación técnica y la decisión comercial.
3. Verificar que la identidad siga dependiendo de `row_number`, no del SKU ni del orden de presentación.
4. Verificar que la exportación aplique las tres condiciones de forma conjunta.
5. Validar la interacción de la interfaz y la generación del CSV con los archivos de prueba representativos.
6. Actualizar este documento cuando cambie deliberadamente el comportamiento contractual.

La navegación por etapas forma parte del flujo vigente en `src/ui/nicegui_app.py`; no depende del modelo anterior de cupos del PR #24.
