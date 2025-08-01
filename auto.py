import requests
from bs4 import BeautifulSoup
from feedgen.feed import FeedGenerator
import urllib3
import time
import os
import subprocess

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ---------- CONFIGURACIÓN ----------
BASE_URL = "https://www.fgeqroo.gob.mx"
ROOT_URL = BASE_URL + "/alertas/Amber"
MAX_PAGES = 5
RSS_FILENAME = "amber_feed.xml"
GIT_REPO_PATH = r"C:\apps\RSS\rss-amber"  # Ajusta si tu carpeta cambia
# ------------------------------------

def procesar_pagina(url):
    print(f"[🔎] Procesando: {url}")
    res = requests.get(url, verify=False)
    res.encoding = 'utf-8'
    soup = BeautifulSoup(res.text, 'html.parser')
    return soup.select('div.detalle-com')

def generar_rss():
    fg = FeedGenerator()
    fg.title("Alerta Amber Quintana Roo")
    fg.link(href=ROOT_URL, rel='alternate')
    fg.description("Actualizaciones de fichas de personas desaparecidas en Quintana Roo.")
    fg.language("es")

    total_fichas = 0

    for page in range(1, MAX_PAGES + 1):
        page_url = ROOT_URL if page == 1 else f"{ROOT_URL}?page={page}"
        try:
            fichas = procesar_pagina(page_url)
            if not fichas:
                print(f"[⚠️] Página {page} vacía. Fin del recorrido.")
                break

            for ficha in fichas:
                nombre_tag = ficha.find('h3')
                fecha_tag = ficha.find('small')
                imagen_tag = ficha.find('img')

                if not (nombre_tag and imagen_tag):
                    continue

                nombre = nombre_tag.text.strip()
                fecha = fecha_tag.text.strip() if fecha_tag else ""
                imagen_url = imagen_tag['src']
                if imagen_url.startswith('/'):
                    imagen_url = BASE_URL + imagen_url

                entry = fg.add_entry()
                entry.title(f"{nombre} - {fecha}")
                entry.link(href=imagen_url)
                entry.guid(imagen_url, permalink=True)
                entry.description(
                    f"<strong>{nombre}</strong><br>Fecha: {fecha}<br><img src='{imagen_url}' width='300' />"
                )

                total_fichas += 1

            time.sleep(0.5)

        except Exception as e:
            print(f"[❌] Error en página {page}: {e}")
            break

    output_path = os.path.join(GIT_REPO_PATH, RSS_FILENAME)
    fg.rss_file(output_path, pretty=True)
    print(f"\n✅ RSS generado con {total_fichas} fichas: {output_path}")
    return output_path

def subir_a_github(rss_path):
    print("\n📤 Subiendo archivo a GitHub...")

    try:
        os.chdir(GIT_REPO_PATH)
        subprocess.run(["git", "add", "."], check=True)
        subprocess.run(["git", "commit", "-m", "🔄 Feed actualizado automáticamente"], check=True)
        subprocess.run(["git", "push"], check=True)
        print("✅ Archivo subido exitosamente a GitHub.")
    except subprocess.CalledProcessError as e:
        print(f"[❌] Error al subir a GitHub: {e}")

# ----------- EJECUCIÓN --------------
archivo = generar_rss()
subir_a_github(archivo)
