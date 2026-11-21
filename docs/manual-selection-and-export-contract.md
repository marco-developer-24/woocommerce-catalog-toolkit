# Contrato de selección manual y exportación de altas

Estado: especificación para implementar  
Alcance: flujo de altas de productos del WooCommerce Catalog Toolkit  
No incluye: actualización de productos existentes, escritura directa en WooCommerce ni selección masiva.

## 1. Principios

1. La clasificación técnica y la selección comercial son decisiones distintas.
2. La herramienta nunca selecciona productos automáticamente.
3. El precio sirve para ordenar inicialmente la lista, no para decidir qué productos se incorporan.
4. La asignación de categoría destino es independiente de la selección comercial.
5. La exportación solo contiene productos seleccionados, técnicamente aptos y con destino confirmado.
6. No hay cupos, límites ni cuotas por categoría.

## 2. Identidad de producto

- La identidad de una fila dentro de una sesión de proveedor es `row_number`, correspondiente al número de fila original del CSV.
- No usar SKU como clave de selección: puede faltar o estar duplicado.
- `row_number` debe conservarse al filtrar, buscar, ordenar, expandir o contraer categorías.
- La identidad solo es válida para el archivo de proveedor cargado en esa sesión.

## 3. Estado de selección

Contrato mínimo:

```python
selection_state = {
    row_number: "SELECTED" | "NOT_SELECTED"
}
```

Reglas:

- Todas las filas comienzan en `NOT_SELECTED`.
- Solo filas clasificadas como `READY` pueden pasar a `SELECTED`.
- Filas `REVIEW`, `BLOCKED` y `EXCLUDED` no pueden seleccionarse.
- La selección se modifica únicamente por una acción explícita del usuario sobre un producto.
- La selección persiste mientras se navega, busca, filtra, ordena o cambia la presentación de categorías.
- Reemplazar el archivo de proveedor inicia una sesión nueva y reinicia todas las selecciones.
- Recalcular la comparación no debe crear selecciones nuevas. Se conservan las decisiones de la sesión para las mismas filas que continúen siendo `READY`; cualquier fila que deje de ser `READY` queda en `NOT_SELECTED`. Si vuelve a ser `READY`, no se selecciona automáticamente.

El estado vive en memoria durante la sesión. No implementar persistencia en base de datos ni almacenamiento entre sesiones.

## 4. Elegibilidad técnica

Reutilizar la clasificación existente de `prepare_add_products()`:

- `READY`: producto técnicamente apto para una posible alta.
- `REVIEW`: requiere revisión; no seleccionable.
- `BLOCKED`: no puede prepararse; no seleccionable.
- `EXCLUDED`: ya existe en la referencia WooCommerce; no es un alta nueva.

No duplicar en la capa de selección las validaciones de SKU, nombre, precio o stock que ya realiza la clasificación técnica.

La falta de categoría destino no modifica el estado técnico `READY`.

## 5. Destinos de categorías

- El destino WooCommerce se configura por categoría de proveedor.
- El destino es una decisión independiente de la selección de productos.
- Una categoría sin destino puede contener productos seleccionados.
- Cambiar o confirmar un destino no debe seleccionar ni deseleccionar productos.
- La sugerencia automática, cuando exista, no equivale a confirmación del usuario.
- Solo un destino confirmado habilita la exportación de productos de esa categoría.

## 6. Reglas de exportación

Un producto es exportable si y solo si cumple simultáneamente:

```text
selection_state[row_number] == SELECTED
AND technical_status == READY
AND category_destination is confirmed
```

- Construir las filas de exportación a partir de ese criterio, no desde una lista heredada de cupos ni desde el orden visual.
- La exportación debe conservar el número de fila de origen para trazabilidad interna, sin agregarlo al CSV de WooCommerce salvo que el formato lo requiera expresamente.
- Mantener el formato de altas ya acordado: producto simple, borrador (`Published = -1`), precio de proveedor mapeado y categoría destino confirmada.
- No incluir productos existentes, duplicados, bloqueados, en revisión, no seleccionados o sin destino confirmado.
- La generación de CSV no debe mutar la clasificación ni el estado de selección.

## 7. Interfaz y comportamiento

- Mostrar categorías y sus productos elegibles.
- Dentro de cada categoría, mostrar todos los productos aptos sin seleccionar inicialmente.
- Orden inicial por precio ascendente; permitir cambiar el orden sin afectar la selección.
- La selección es individual por producto.
- No mostrar controles de cupo ni «Incluir categoría».
- La participación de una categoría en el lote se deriva de que tenga uno o más productos seleccionados.
- Los productos no seleccionables deben mostrar su estado y motivo de revisión/bloqueo, sin checkbox habilitado.
- Mostrar de forma diferenciada, como mínimo, productos seleccionados y productos listos para exportar.
- Buscar, ordenar, expandir y contraer no deben alterar las decisiones.

## 8. Criterios de aceptación y pruebas

### Selección
- [ ] Al iniciar una preparación, todos los productos están `NOT_SELECTED`.
- [ ] Un producto `READY` puede seleccionarse y deseleccionarse individualmente.
- [ ] Un producto `REVIEW`, `BLOCKED` o `EXCLUDED` no puede seleccionarse.
- [ ] Dos filas con SKU duplicado mantienen estados de selección independientes por `row_number`.
- [ ] Ordenar o filtrar no cambia las selecciones.
- [ ] Reemplazar el proveedor reinicia el estado.
- [ ] Recalcular la comparación no selecciona productos automáticamente ni conserva selección en filas que dejaron de ser `READY`.

### Destinos
- [ ] Seleccionar un producto no exige tener destino confirmado.
- [ ] Cambiar el destino no modifica la selección.
- [ ] Una categoría sin destino confirmado no aporta filas al CSV.
- [ ] Confirmar un destino habilita para exportación los productos seleccionados y aptos de esa categoría, sin seleccionar otros.

### Exportación
- [ ] Se exportan únicamente filas `SELECTED + READY + destino confirmado`.
- [ ] Un producto seleccionado sin destino no se exporta.
- [ ] Un producto no seleccionado con destino confirmado no se exporta.
- [ ] Productos `REVIEW`, `BLOCKED` y `EXCLUDED` nunca aparecen en el CSV.
- [ ] El orden visual no altera el conjunto exportado.
- [ ] La exportación no muta los datos de entrada ni el estado de selección.
- [ ] El CSV conserva el formato de altas ya aprobado.

## 9. Fuera de alcance

- Selección automática por precio.
- Cupos, límites o cuotas por categoría.
- Selección masiva o «seleccionar todos».
- Recomendaciones comerciales automáticas.
- Persistencia entre sesiones.
- Actualización de productos existentes.
- API o escritura directa en la tienda.

## 10. Secuencia de implementación

1. Reemplazar tests del modelo de cupos por tests de selección manual.
2. Implementar el estado de selección independiente en la capa de aplicación.
3. Hacer que la preparación/exportación derive sus filas del estado y la elegibilidad vigentes.
4. Adaptar NiceGUI y eliminar controles y textos de cupos.
5. Recuperar la navegación por pestañas del PR #24 sin arrastrar su modelo anterior.
6. Ejecutar suite completa y pruebas de interacción con los CSV reales antes del merge.
