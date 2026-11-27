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

Estos criterios son una lista de verificación permanente para cambios futuros. Se distingue la cobertura automatizada disponible de la validación manual de interfaz. No marcar como automatizado un escenario que solo se haya inspeccionado en el código.

### 8.1. Cobertura automatizada existente

Los siguientes comportamientos tienen pruebas unitarias o de integración de aplicación en `tests/test_product_selection_state.py`, `tests/test_manual_product_selection.py`, `tests/test_catalog_preparation.py` y `tests/test_catalog_preparation_report.py`:

- [x] Al preparar un catálogo, todas las filas comienzan en `NOT_SELECTED`.
- [x] Un producto `READY` puede seleccionarse y deseleccionarse individualmente.
- [x] Un producto no elegible no puede seleccionarse.
- [x] Seleccionar o deseleccionar una fila no modifica las decisiones de otras filas.
- [x] Las decisiones se identifican mediante `row_number`; las filas fuera de la sesión se rechazan.
- [x] Los SKU existentes y duplicados no se exportan.
- [x] Una selección sin destino confirmado se conserva, pero no se exporta.
- [x] Un destino configurado no selecciona productos automáticamente.
- [x] Una fila que deja de ser `READY` vuelve a `NOT_SELECTED`.
- [x] La exportación exige selección, elegibilidad técnica y destino confirmado.
- [x] El orden de las filas exportables no depende del orden de entrada.
- [x] La preparación y exportación no mutan las filas ni el estado de selección recibidos.
- [x] El CSV conserva los campos y valores de alta acordados.

La prueba de SKU duplicados verifica que esas filas no se exporten. No debe interpretarse como evidencia de que un SKU duplicado sea seleccionable: su clasificación técnica impide esa selección.

### 8.2. Validación manual de interfaz pendiente de automatizar

Estos escenarios pertenecen al ciclo de vida de la interfaz NiceGUI y no están cubiertos por las pruebas unitarias anteriores:

- [ ] Seleccionar un producto, cambiar de categoría y volver: la selección permanece.
- [ ] Seleccionar un producto, aplicar y quitar un filtro de búsqueda: la selección permanece.
- [ ] Reemplazar el CSV del proveedor: se reinician selección, destinos y confirmaciones de la sesión anterior.
- [ ] Confirmar un destino, cambiarlo y comprobar que la confirmación anterior queda invalidada.
- [ ] Cambiar un destino no modifica las selecciones de productos.
- [ ] Una sugerencia automática no habilita la exportación hasta ser confirmada.
- [ ] Después de cada interacción, los contadores y la lista exportable reflejan el estado actual.

Para ejecutar esta validación manual, usar un CSV pequeño con al menos dos categorías, dos productos `READY` y una fila no seleccionable. Registrar los resultados y cualquier incidencia antes de solicitar revisión del PR.

### 8.3. Criterios permanentes para cambios futuros

- [ ] Al iniciar una sesión nueva, todas las filas están `NOT_SELECTED`.
- [ ] La identidad de cada fila depende de `row_number`, no del SKU ni del orden visual.
- [ ] Buscar, ordenar, filtrar, expandir y contraer no altera decisiones.
- [ ] Reemplazar el proveedor reinicia el estado de la sesión.
- [ ] Cambiar el destino invalida la confirmación anterior sin modificar la selección.
- [ ] Se exportan únicamente filas `SELECTED + READY + destino confirmado`.
- [ ] El CSV no incluye productos existentes, duplicados, bloqueados, en revisión o no seleccionados.
- [ ] La exportación no muta los datos de entrada ni el estado de selección.

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
