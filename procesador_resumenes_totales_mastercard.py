import pdfplumber
import pandas as pd
import re

# Ruta del PDF y nombre del archivo CSV de salida
pdf_path = "HSBC MasterCard 2024-09.pdf"
output_csv = "resultado_mastercard.csv"

# Lista para almacenar todas las transacciones
transactions = []

# Expresión regular ajustada para capturar transacciones con y sin cuotas
transaction_pattern = re.compile(
    r"(\d{2}-[A-Za-z]{3}-\d{2})\s+(.+?)\s+(?:(\d{1,2}/\d{1,2})\s+)?(\d{5})?\s+([\d\.\-]+,\d{2}-?)"
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
                fecha, descripcion, cuotas, comprobante, monto = transaction_match.groups()
                monto = parse_amount(monto)
                
                # Detectar moneda en la descripción
                moneda = "DOLARES" if "USA" in descripcion or "USD" in descripcion else "PESOS"

                # Procesar las cuotas si están presentes
                numero_cuota, total_cuotas = (map(int, cuotas.split("/")) if cuotas else (None, None))

                # Agregar transacción a la lista de resultados
                transactions.append({
                    "Fecha": fecha,
                    "Comprobante": comprobante if comprobante else "N/A",
                    "Descripción": descripcion.strip(),
                    "Número de cuota": numero_cuota,
                    "Total cuotas": total_cuotas,
                    "Monto": monto,
                    "Moneda": moneda
                })

# Convertir a DataFrame y exportar a CSV
df = pd.DataFrame(transactions)
df.to_csv(output_csv, index=False)

# Imprimir resultados si hay coincidencias
if not df.empty:
    print(f"Se encontraron {len(df)} transacciones. Archivo CSV generado exitosamente en: {output_csv}")
else:
    print("No se encontraron coincidencias en el PDF.")
