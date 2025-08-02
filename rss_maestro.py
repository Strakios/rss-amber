import requests
from bs4 import BeautifulSoup
from feedgen.feed import FeedGenerator
from datetime import datetime, timedelta, timezone
import urllib3
import time
import subprocess
import xml.etree.ElementTree as ET

# 🌎 Zona horaria Cancún
TZ_CANCUN = timezone(timedelta(hours=-5))
MAX_PAGES = 10
BASE_URL = "https://www.fgeqroo.gob.mx"
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Configuración por tipo de alerta
TIPOS = {
    "amber": {
        "titulo": "Alertas Amber Quintana Roo",
        "descripcion": "RSS de personas desaparecidas (Amber) en Quintana Roo",
        "url": BASE_URL + "/alertas/Amber",
        "rss": "amber_feed.xml"
    },
    "extraviado": {
        "titulo": "Personas Extraviadas Quintana Roo",
        "descripcion": "RSS de personas extraviadas en Quintana Roo",
        "url": BASE_URL + "/servicio-social/Extraviado",
        "rss": "extraviado_feed.xml"
    },
    "alba": {
        "titulo": "Protocolo Alba Quintana Roo",
        "descripcion": "RSS de mujeres desaparecidas (Alba) en Quintana Roo",
        "url": BASE_URL + "/protocolos/Alba",
        "rss": "alba_feed.xml"
    }
}

def parsear_fecha(texto):
    try:
        return datetime.strptime(texto.strip(), '%Y/%m/%d').replace(tzinfo=TZ_CANCUN)
    except:
        return datetime.now(TZ_CANCUN)

def procesar_pagina(url):
    res = requests.get(url, verify=False)
    res.encoding = 'utf-8'
    soup = BeautifulSoup(res.text, 'html.parser')
    return soup.select('div.detalle-com')

def cargar_anteriores(rss_filename):
    fichas = {}
    last_build = None
    try:
        tree = ET.parse(rss_filename)
        root = tree.getroot()
        channel = root.find('channel')
        if channel is not None:
            tag = channel.find('lastBuildDate')
            if tag is not None:
                last_build = datetime.strptime(tag.text.strip(), '%a, %d %b %Y %H:%M:%S %z')
            for item in channel.findall('item'):
                guid = item.find('guid').text.strip()
                pub = item.find('pubDate').text.strip()
                fichas[guid] = datetime.strptime(pub, '%a, %d %b %Y %H:%M:%S %z')
    except:
        pass
    return fichas, last_build

def generar_rss(tipo, config):
    print(f"\n🔍 Procesando {tipo.upper()}")
    fg = FeedGenerator()
    fg.title(config["titulo"])
    fg.link(href=config["url"], rel='alternate')
    fg.description(config["descripcion"])
    fg.language("es")

    anteriores, last_build_prev = cargar_anteriores(config["rss"])
    ahora = datetime.now(TZ_CANCUN)
    fg.lastBuildDate(ahora)

    fichas = []
    for page in range(1, MAX_PAGES + 1):
        url = config["url"] if page == 1 else f"{config['url']}?page={page}"
        soup = procesar_pagina(url)
        if not soup:
            break
        for ficha in soup:
            h3 = ficha.find('h3')
            small = ficha.find('small')
            img = ficha.find('img')
            if not (h3 and img): continue
            nombre = h3.text.strip()
            fecha_texto = small.text.strip() if small else ""
            fecha_dt = parsear_fecha(fecha_texto)
            img_url = BASE_URL + img['src'] if img['src'].startswith('/') else img['src']
            fichas.append({
                "nombre": nombre,
                "fecha": fecha_dt,
                "texto_fecha": fecha_texto,
                "imagen": img_url
            })
        time.sleep(0.5)

    fichas.sort(key=lambda x: x['fecha'], reverse=True)
    if not last_build_prev:
        last_build_prev = ahora - timedelta(hours=1)

    total_nuevas = sum(1 for f in fichas if f['imagen'] not in anteriores) or 1
    intervalo = (ahora - last_build_prev) / total_nuevas

    nuevas = 0
    indice = 0
    for f in fichas:
        guid = f["imagen"]
        if guid in anteriores:
            pubdate = anteriores[guid]
        else:
            hora_estim = last_build_prev + intervalo * indice
            pubdate = datetime(
                year=f["fecha"].year,
                month=f["fecha"].month,
                day=f["fecha"].day,
                hour=hora_estim.hour,
                minute=hora_estim.minute,
                second=hora_estim.second,
                tzinfo=TZ_CANCUN
            )
            nuevas += 1
            indice += 1

        entry = fg.add_entry()
        entry.title(f"{f['nombre']} - {f['texto_fecha']}")
        entry.link(href=f['imagen'])
        entry.guid(f['imagen'], permalink=True)
        entry.pubDate(pubdate)
        entry.description(
            f"<strong>{f['nombre']}</strong><br>Fecha: {f['texto_fecha']}<br><img src='{f['imagen']}' width='300' />"
        )

    fg.rss_file(config["rss"], pretty=True)
    return config["rss"], nuevas

def subir_a_github(archivo):
    print(f"📤 Subiendo {archivo} a GitHub...")
    try:
        subprocess.run(["git", "pull"], check=True)
        subprocess.run(["git", "add", archivo], check=True)
        subprocess.run(["git", "commit", "-m", f"Actualización {archivo}"], check=True)
        subprocess.run(["git", "push"], check=True)
        print(f"✅ Subido: {archivo}")
    except:
        print(f"[❌] Error al subir {archivo}")

if __name__ == "__main__":
    for tipo, config in TIPOS.items():
        archivo, nuevas = generar_rss(tipo, config)
        if nuevas > 0:
            subir_a_github(archivo)
        else:
            print(f"ℹ️ No hay nuevas fichas en {archivo}")
