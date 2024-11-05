import pdfplumber
import pandas as pd
import re

# Ruta del PDF y nombre del archivo CSV de salida
pdf_path = "HSBC Visa Resumen 2024-09.pdf"  # Coloca el nombre correcto del archivo
output_csv = "resultado.csv"

# Lista para almacenar todas las transacciones
transactions = []

# Expresión regular para capturar filas de transacción, incluyendo comprobante con asterisco opcional
transaction_pattern = re.compile(
    r"(\d{2}\.\d{2}\.\d{2})\s+(\d+\w*\*?)\s+([\w\*\s]+)\s+(?:C\.(\d+)/(\d+)\s+)?([\d\.\-]+,\d{2}-?)"
)

# Función para convertir montos al formato numérico adecuado
def parse_amount(amount_str):
    # Eliminar puntos en miles y cambiar coma por punto en decimales
    clean_amount = amount_str.replace(".", "").replace(",", ".")
    # Convertir a negativo si termina en "-"
    return -float(clean_amount[:-1]) if clean_amount.endswith("-") else float(clean_amount)

# Abre el PDF
with pdfplumber.open(pdf_path) as pdf:
    for page in pdf.pages:
        text = page.extract_text()  # Extrae el texto de cada página

        # Dividir el texto por líneas para analizar cada una
        for line in text.splitlines():
            # Buscar coincidencias en la línea actual de transacción
            transaction_match = transaction_pattern.search(line)
            if transaction_match:
                fecha, comprobante, descripcion, numero_cuota, total_cuotas, monto = transaction_match.groups()
                monto = parse_amount(monto)

                # Agregar transacción a la lista de resultados
                transactions.append({
                    "Fecha": fecha,
                    "Comprobante": comprobante,
                    "Descripción": descripcion.strip(),
                    "Número de cuota": int(numero_cuota) if numero_cuota else None,
                    "Total cuotas": int(total_cuotas) if total_cuotas else None,
                    "Monto": monto
                })

# Convertir a DataFrame y exportar a CSV
df = pd.DataFrame(transactions)
df.to_csv(output_csv, index=False)

# Calcular los totales
consumos_total = df["Monto"].sum()

consumos_primera_cuota = df[(df["Número de cuota"].isna()) | (df["Número de cuota"] == 1)]["Monto"].sum()

consumos_cuotas_anteriores = df[(df["Número de cuota"] > 1)]["Monto"].sum()

consumos_restantes = df[df["Número de cuota"] > 1].apply(lambda x: x["Monto"] * (x["Total cuotas"] - x["Número de cuota"]), axis=1).sum()

consumos_actuales_a_futuro = df[df["Número de cuota"] == 1].apply(lambda x: x["Monto"] * x["Total cuotas"], axis=1).sum()

consumos_mes_siguiente = df[(df["Número de cuota"] == 1) & (df["Número de cuota"] < df["Total cuotas"])]["Monto"].sum()

# Imprimir los totales calculados
print("Totales calculados:")
print(f"Consumos del mes: ${consumos_total:.2f}")
print(f"Consumos del mes (primera cuota): ${consumos_primera_cuota:.2f}")
print(f"Consumos del mes (cuotas anteriores): ${consumos_cuotas_anteriores:.2f}")
print(f"Consumos en cuotas restantes: ${consumos_restantes:.2f}")
print(f"Consumos del mes (totales a futuro): ${consumos_actuales_a_futuro:.2f}")
print(f"Consumos cargados al mes siguiente: ${consumos_mes_siguiente:.2f}")
