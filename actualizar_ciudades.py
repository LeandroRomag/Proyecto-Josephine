import requests
import json
import unicodedata

def limpiar_texto(texto):
    """Quita tildes y pasa a minúsculas para armar las keys limpias."""
    texto = unicodedata.normalize('NFKD', texto).encode('ASCII', 'ignore').decode('utf-8')
    return texto.lower().replace(" ", "_")

print("Iniciando escaneo nacional. Esto puede tardar unos 10 o 15 segundos...")

# 1. Pedimos la lista oficial de todas las provincias argentinas
url_provincias = "https://apis.datos.gob.ar/georef/api/provincias"
respuesta_prov = requests.get(url_provincias).json()

datos_finales = {}

# 2. Recorremos provincia por provincia
for prov in respuesta_prov['provincias']:
    nombre_prov = prov['nombre']
    id_prov = prov['id']
    key_prov = limpiar_texto(nombre_prov)
    
    print(f"Descargando ciudades de: {nombre_prov}...")
    
    # 3. Traemos TODAS las localidades de esta provincia de una sola vez
    url_loc = f"https://apis.datos.gob.ar/georef/api/localidades?provincia={id_prov}&max=5000"
    respuesta_loc = requests.get(url_loc).json()
    
    ciudades_lista = []
    for loc in respuesta_loc['localidades']:
        # Mapeamos los datos oficiales a tu estructura exacta
        ciudades_lista.append({
            "name": loc['nombre'],
            "lat": loc['centroide']['lat'],
            "lng": loc['centroide']['lon'],
            "type": loc['categoria'] or "city"
        })
        
    # Ordenamos las ciudades alfabéticamente para que el menú de tu página quede prolijo
    ciudades_lista = sorted(ciudades_lista, key=lambda x: x['name'])
    
    # 4. Ensamblamos la estructura completa
    datos_finales[nombre_prov] = {
        "key": key_prov,
        "label": nombre_prov,
        "count": len(ciudades_lista),
        "cities": ciudades_lista
    }

# 5. Guardamos y sobrescribimos tu archivo con la base de datos nacional completa
with open('shipping_cities.json', 'w', encoding='utf-8') as file:
    json.dump(datos_finales, file, ensure_ascii=False, indent=4)

print("¡Éxito total! Tu archivo shipping_cities.json ahora tiene toda la Argentina.")