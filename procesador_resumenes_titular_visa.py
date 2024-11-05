import pdfplumber
import pandas as pd
import re

# Ruta del PDF y nombre del archivo CSV de salida
pdf_path = "HSBC Visa Resumen 2024-09.pdf"  # Coloca el nombre correcto del archivo
output_csv = "resultado.csv"

# Lista para almacenar todas las transacciones y un grupo temporal para cada titular
transactions = []
temp_transactions = []

# Expresión regular para capturar filas de transacción, incluyendo comprobante con asterisco opcional
transaction_pattern = re.compile(
    r"(\d{2}\.\d{2}\.\d{2})\s+(\d+\w*\*?)\s+([\w\*\s]+)\s+(?:C\.(\d+)/(\d+)\s+)?([\d\.\-]+,\d{2}-?)"
)

# Expresión regular para detectar la línea de titular de tarjeta
cardholder_pattern = re.compile(r"TARJETA \d+ Total Consumos de ([\w\s]+)\s([\d\.\-]+,\d{2})")

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
            # Verificar si es una línea de titular de tarjeta
            holder_match = cardholder_pattern.search(line)
            if holder_match:
                # Captura el nombre del titular y el total de consumos al final del grupo
                current_holder = holder_match.group(1).strip()
                total_consumo = parse_amount(holder_match.group(2))

                # Asigna el nombre del titular a todas las transacciones en el grupo temporal
                for transaction in temp_transactions:
                    transaction["Titular"] = current_holder
                
                # Mover transacciones del grupo temporal a la lista principal
                transactions.extend(temp_transactions)
                temp_transactions = []  # Limpiar el grupo temporal para el siguiente titular
                continue
            
            # Buscar coincidencias en la línea actual de transacción
            transaction_match = transaction_pattern.search(line)
            if transaction_match:
                fecha, comprobante, descripcion, numero_cuota, total_cuotas, monto = transaction_match.groups()
                monto = parse_amount(monto)

                # Agregar transacción al grupo temporal sin titular aún asignado
                temp_transactions.append({
                    "Fecha": fecha,
                    "Comprobante": comprobante,
                    "Descripción": descripcion.strip(),
                    "Número de cuota": int(numero_cuota) if numero_cuota else None,
                    "Total cuotas": int(total_cuotas) if total_cuotas else None,
                    "Monto": monto,
                    "Titular": None  # Se asignará después
                })

# Convertir a DataFrame y exportar a CSV
df = pd.DataFrame(transactions)
df.to_csv(output_csv, index=False)

print(f"Archivo CSV generado exitosamente en: {output_csv}")
