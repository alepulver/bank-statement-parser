# Esquema de salida (CSV)

Este proyecto genera **3 CSVs**:

## 1) `statements.csv` (1 fila por PDF)

| Columna | Tipo | Descripción |
|---|---:|---|
| `archivo` | string | Nombre del PDF procesado |
| `banco` | string | `"HSBC"` |
| `origen` | string | `"mastercard"`, `"visa"`, `"cuenta"` |
| `numero_resumen` | string/null | Nº de resumen (si se detecta) |
| `fecha_desde` | string/null | Inicio del período (si se detecta) |
| `fecha_hasta` | string/null | Fin del período / fecha de cierre (si se detecta) |
| `titular_nombre` | string/null | Titular (best-effort) |
| `moneda` | string/null | Moneda del statement si aplica (p.ej. en cuenta) |

## 2) `transactions.csv` (N filas por PDF)

| Columna | Tipo | Descripción |
|---|---:|---|
| `archivo` | string | PDF origen |
| `fecha` | string | Fecha del movimiento (formato del PDF) |
| `descripcion` | string | Texto del movimiento |
| `moneda` | string | `"ARS"` o `"USD"` (u otras si aparecen) |
| `importe` | number | **Con signo**: débito negativo / crédito positivo |
| `persona` | string | Persona asociada (titular/adicional cuando aplica) |
| `origen` | string | `"mastercard"`, `"visa"`, `"cuenta"` |

> Nota: En tarjetas, `importe` es el importe que figura en la línea (no hay conversión).  
> En cuenta, `importe` proviene de columnas Débito/Crédito (débito -> negativo).

## 3) `warnings.csv` (auditoría del parseo)

| Columna | Tipo | Descripción |
|---|---:|---|
| `archivo` | string | PDF origen |
| `level` | string | `"INFO"`, `"WARNING"`, `"ERROR"` |
| `code` | string | Código estable del warning |
| `message` | string | Texto |
| `context` | string/json/null | Contexto (best-effort) |
