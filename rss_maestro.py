# -*- coding: utf-8 -*-

import os
import requests
from bs4 import BeautifulSoup
from feedgen.feed import FeedGenerator
from datetime import datetime, timedelta, timezone
import urllib3
import time
import subprocess
import xml.etree.ElementTree as ET
from PIL import Image
from io import BytesIO
import pytesseract
import re
from concurrent.futures import ThreadPoolExecutor, TimeoutError


# ============================================================
# CONFIGURACIÓN GENERAL
# ============================================================

TZ_CANCUN = timezone(timedelta(hours=-5))

MAX_PAGES = 60

BASE_URL = "https://www.fgeqroo.gob.mx"


# ============================================================
# CONFIGURACIÓN DE RED
# ============================================================

# Número de intentos por solicitud
MAX_REINTENTOS = 4

# Tiempo base entre reintentos
ESPERA_REINTENTO = 3

# Timeout de conexión
TIMEOUT_CONEXION = 10

# Timeout de lectura
TIMEOUT_LECTURA = 30

# Pausa entre páginas
PAUSA_ENTRE_PAGINAS = 0.7

# Pausa adicional entre reintentos
PAUSA_REINTENTO_INCREMENTAL = 3


urllib3.disable_warnings(
    urllib3.exceptions.InsecureRequestWarning
)


# ============================================================
# SESSION HTTP
# ============================================================

SESSION = requests.Session()

SESSION.headers.update({

    "User-Agent":
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 "
        "(KHTML, like Gecko) "
        "Chrome/151.0.0.0 Safari/537.36",

    "Accept":
        "text/html,application/xhtml+xml,"
        "application/xml;q=0.9,image/avif,"
        "image/webp,*/*;q=0.8",

    "Accept-Language":
        "es-MX,es;q=0.9,en;q=0.8",

    "Accept-Encoding":
        "gzip, deflate",

    "Connection":
        "keep-alive",

    "Upgrade-Insecure-Requests":
        "1"
})


# ============================================================
# RSS A PROCESAR
# ============================================================

TIPOS = {

    "amber": {

        "titulo":
            "Alertas Amber Quintana Roo",

        "descripcion":
            "RSS de personas desaparecidas (Amber) "
            "en Quintana Roo",

        "url":
            BASE_URL + "/alertas/Amber",

        "rss":
            "amber_feed.xml",

        "ocr":
            True
    },


    "extraviado": {

        "titulo":
            "Personas Extraviadas Quintana Roo",

        "descripcion":
            "RSS de personas extraviadas "
            "en Quintana Roo",

        "url":
            BASE_URL + "/servicio-social/Extraviado",

        "rss":
            "extraviado_feed.xml",

        "ocr":
            True
    },


    "alba": {

        "titulo":
            "Protocolo Alba Quintana Roo",

        "descripcion":
            "RSS de mujeres desaparecidas (Alba) "
            "en Quintana Roo",

        "url":
            BASE_URL + "/protocolos/Alba",

        "rss":
            "alba_feed.xml",

        "ocr":
            True
    },


    "amber-localizados": {

        "titulo":
            "Localizados Amber Quintana Roo",

        "descripcion":
            "RSS de Alerta Amber Localizados "
            "en Quintana Roo",

        "url":
            BASE_URL +
            "/alerta-amber-localizadas/amber",

        "rss":
            "localizados_amber.xml",

        "ocr":
            False
    },
    
    "extraviados-localizados": {

        "titulo":
            "Extraviados-Localizados Quintana Roo",

        "descripcion":
            "RSS de Personas desaparecidas Localizadas "
            "en Quintana Roo",

        "url":
            BASE_URL +
            "/extraviadas-localizadas/Extraviado",

        "rss":
            "localizados_extraviados.xml",

        "ocr":
            False
    },
    
        "alba-localizados": {

        "titulo":
            "Localizados Protocolo Alba Quintana Roo",

        "descripcion":
            "RSS de Protocolos Alba Localizados "
            "en Quintana Roo",

        "url":
            BASE_URL +
            "/protocolo-alba-localizadas/alba",

        "rss":
            "localizados_feed.xml",

        "ocr":
            False
    },
}


# ============================================================
# PATRONES PARA EXTRAER HECHOS
# ============================================================

PATRONES_FIN_HECHOS = [

    r'-\s*La\s+Ley\s+General\s+en\s+Materia\s+de\s+Desaparicion\s+Forzada\s+de\s+Personas',

    r'La\s+Ley\s+General\s+en\s+materia',

    r'Ley\s+General\s+en\s+materia',

    r'Si\s+conoces,'
]


PATRONES_FIN_HECHOS_RE = [

    re.compile(
        p,
        re.IGNORECASE
    )

    for p in PATRONES_FIN_HECHOS
]


# ============================================================
# FECHAS
# ============================================================

def parsear_fecha(texto):

    try:

        return datetime.strptime(

            texto.strip(),

            '%Y/%m/%d'

        ).replace(
            tzinfo=TZ_CANCUN
        )

    except Exception:

        return datetime.now(
            TZ_CANCUN
        )


# ============================================================
# SOLICITUD HTTP ROBUSTA
# ============================================================

def solicitar(url, timeout_conexion=None,
              timeout_lectura=None):

    if timeout_conexion is None:
        timeout_conexion = TIMEOUT_CONEXION

    if timeout_lectura is None:
        timeout_lectura = TIMEOUT_LECTURA


    ultimo_error = None


    for intento in range(
        1,
        MAX_REINTENTOS + 1
    ):

        try:

            print(
                f"🌐 Solicitud "
                f"{intento}/{MAX_REINTENTOS}: "
                f"{url}"
            )


            respuesta = SESSION.get(

                url,

                verify=False,

                timeout=(
                    timeout_conexion,
                    timeout_lectura
                )
            )


            respuesta.raise_for_status()


            return respuesta


        except Exception as e:

            ultimo_error = e


            print(

                f"⚠️ Fallo de conexión "
                f"(intento {intento}/"
                f"{MAX_REINTENTOS})"

            )

            print(
                f"   {e}"
            )


            if intento < MAX_REINTENTOS:

                espera = (

                    ESPERA_REINTENTO
                    +
                    (
                        intento - 1
                    )
                    *
                    PAUSA_REINTENTO_INCREMENTAL
                )


                print(

                    f"⏳ Reintentando en "
                    f"{espera} segundos..."

                )


                time.sleep(
                    espera
                )


    print(
        f"❌ No fue posible acceder a:"
    )

    print(
        f"   {url}"
    )

    print(
        f"   Último error: "
        f"{ultimo_error}"
    )


    return None


# ============================================================
# DESCARGAR PÁGINA
# ============================================================

def procesar_pagina(url):

    try:

        res = solicitar(
            url
        )


        if res is None:

            return None


        res.encoding = 'utf-8'


        soup = BeautifulSoup(

            res.text,

            'html.parser'
        )


        return soup.select(
            'div.detalle-com'
        )


    except Exception as e:

        print(
            f"⚠️ Error procesando "
            f"la respuesta de:"
        )

        print(
            f"   {url}"
        )

        print(
            f"   {e}"
        )

        return None


# ============================================================
# CARGAR RSS ANTERIOR
# ============================================================

def cargar_anteriores(rss_filename):

    fichas = {}

    last_build = None


    if not os.path.exists(
        rss_filename
    ):

        return fichas, last_build


    try:

        tree = ET.parse(
            rss_filename
        )

        root = tree.getroot()

        channel = root.find(
            'channel'
        )


        if channel is None:

            return fichas, last_build


        # --------------------------------------------
        # LAST BUILD
        # --------------------------------------------

        tag = channel.find(
            'lastBuildDate'
        )


        if tag is not None and tag.text:

            try:

                last_build = datetime.strptime(

                    tag.text.strip(),

                    '%a, %d %b %Y %H:%M:%S %z'

                )

            except Exception:

                pass


        # --------------------------------------------
        # ITEMS
        # --------------------------------------------

        for item in channel.findall(
            'item'
        ):

            guid_tag = item.find(
                'guid'
            )


            if (
                guid_tag is None
                or
                not guid_tag.text
            ):

                continue


            guid = guid_tag.text.strip()


            pub_tag = item.find(
                'pubDate'
            )


            if (
                pub_tag is None
                or
                not pub_tag.text
            ):

                continue


            try:

                pubdate = datetime.strptime(

                    pub_tag.text.strip(),

                    '%a, %d %b %Y %H:%M:%S %z'

                )

            except Exception:

                continue


            title_tag = item.find(
                'title'
            )


            title_text = (

                title_tag.text.strip()

                if (
                    title_tag is not None
                    and
                    title_tag.text
                )

                else ""
            )


            lugar_hechos = ""


            if " - " in title_text:

                lugar_hechos = (

                    title_text.split(
                        " - ",
                        1
                    )[1].strip()
                )


            desc_tag = item.find(
                'description'
            )


            desc_text = (

                desc_tag.text

                if (
                    desc_tag is not None
                    and
                    desc_tag.text
                )

                else ""
            )


            hechos = ""


            m = re.search(

                r"<br><strong>Hechos:</strong>\s*(.*)",

                desc_text,

                re.IGNORECASE
            )


            if m:

                hechos = m.group(
                    1
                ).strip()


            fichas[guid] = {

                "pubdate":
                    pubdate,

                "lugar_hechos":
                    lugar_hechos,

                "hechos":
                    hechos
            }


    except Exception as e:

        print(

            f"⚠️ No se pudo leer "
            f"{rss_filename}: {e}"

        )


    return fichas, last_build


# ============================================================
# LIMPIEZA DE TEXTO
# ============================================================

def limpiar_texto(texto):

    if not texto:

        return ""


    texto = texto.replace(
        '\r',
        ' '
    )


    texto = re.sub(
        r'[\n\t]+',
        ' ',
        texto
    )


    texto = re.sub(
        r'\s{2,}',
        ' ',
        texto
    )


    texto = ''.join(

        c
        for c in texto
        if c.isprintable()
    )


    return texto.strip()


# ============================================================
# OCR
# ============================================================

def _download_and_ocr(url):

    res = solicitar(

        url,

        timeout_conexion=10,

        timeout_lectura=20
    )


    if res is None:

        return ""


    img = Image.open(

        BytesIO(
            res.content
        )
    )


    return pytesseract.image_to_string(

        img,

        lang='spa'
    )


# ============================================================
# OCR CON TIMEOUT
# ============================================================

def ocr_with_timeout(
    url,
    timeout=20
):

    with ThreadPoolExecutor(
        max_workers=1
    ) as ex:

        future = ex.submit(

            _download_and_ocr,

            url
        )


        try:

            return future.result(

                timeout=timeout
            ) or ""


        except TimeoutError:

            future.cancel()


            print(

                f"⏱️ OCR TIMEOUT "
                f"{timeout}s para {url}"

            )


            return ""


        except Exception as e:

            print(

                f"⚠️ OCR error "
                f"{url}: {e}"

            )


            return ""


# ============================================================
# EXTRAER LUGAR DE LOS HECHOS
# ============================================================

def extraer_lugar_de_texto(raw_text):

    if not raw_text:

        return ""


    txt = raw_text.replace(
        '\r',
        '\n'
    )


    label_re = re.compile(

        r'(?:Lugar\s+de\s+los\s+hechos:|'
        r'Lugar\s+del\s+hecho:|'
        r'Lugar\s+de\s+hecho:|'
        r'Lugar\s+de\s+hechos:)',

        flags=re.IGNORECASE
    )


    m = label_re.search(
        txt
    )


    if not m:

        for part in txt.splitlines():

            part = part.strip()


            if re.match(

                r'(?i)^lugar '
                r'(de los|del|de)?\s*hecho',

                part
            ):

                try:

                    return re.sub(

                        r'\s+',
                        ' ',

                        part.split(
                            ':',
                            1
                        )[1].strip()
                    )


                except Exception:

                    continue


        return ""


    start_pos = m.end()


    campos_fin = [

        "edad:",
        "sexo:",
        "género:",
        "genero:",
        "nacionalidad:",
        "tez:",
        "complexión:",
        "complexion:",
        "cabello:",
        "ojos:",
        "estatura:"
    ]


    lower_txt = txt.lower()


    candidatos = [

        lower_txt.find(
            token,
            start_pos
        )

        for token in campos_fin

        if lower_txt.find(
            token,
            start_pos
        ) != -1
    ]


    end_pos = (

        min(candidatos)

        if candidatos

        else len(txt)
    )


    found = txt[
        start_pos:end_pos
    ].strip()


    found = re.sub(
        r'[\n\t]+',
        ' ',
        found
    )


    found = re.sub(
        r'[|(){}\[\]]+',
        ' ',
        found
    )


    found = re.sub(
        r'\s{2,}',
        ' ',
        found
    )


    found = re.sub(

        r'\bQuintana\s+y\s+Roo\b',

        'Quintana Roo',

        found,

        flags=re.IGNORECASE
    )


    return found.strip()


# ============================================================
# EXTRAER HECHOS
# ============================================================

def extraer_hechos_de_texto(raw_text):

    if not raw_text:

        return ""


    cleaned = limpiar_texto(
        raw_text
    )


    inicio_re = re.compile(

        r'se\s+solicita\s+el\s+apoyo',

        flags=re.IGNORECASE
    )


    m_start = inicio_re.search(
        cleaned
    )


    if not m_start:

        return ""


    start_idx = m_start.start()

    end_idx = len(cleaned)


    for pat in PATRONES_FIN_HECHOS_RE:

        m = pat.search(

            cleaned,

            pos=start_idx
        )


        if (
            m
            and
            m.start() < end_idx
        ):

            end_idx = m.start()


    hechos = cleaned[
        start_idx:end_idx
    ].strip()


    hechos = re.sub(

        r'\s{2,}',

        ' ',

        hechos
    )


    return hechos


# ============================================================
# GENERACIÓN DEL RSS
# ============================================================

def generar_rss(
    tipo,
    config
):

    print(
        f"\n🔍 Procesando "
        f"{tipo.upper()}"
    )


    fg = FeedGenerator()


    fg.title(
        config["titulo"]
    )


    fg.link(

        href=config["url"],

        rel='alternate'
    )


    fg.description(
        config["descripcion"]
    )


    fg.language(
        "es"
    )


    anteriores, last_build_prev = (

        cargar_anteriores(
            config["rss"]
        )
    )


    ahora = datetime.now(
        TZ_CANCUN
    )


    fichas = []


    # ========================================================
    # DESCARGA DE TODAS LAS PÁGINAS
    # ========================================================

    for page in range(

        1,

        MAX_PAGES + 1
    ):

        url = (

            config["url"]

            if page == 1

            else
            f"{config['url']}?page={page}"
        )


        soup = procesar_pagina(
            url
        )


        # --------------------------------------------
        # SITIO FUERA DE LÍNEA
        # --------------------------------------------

        if soup is None:

            print(

                f"⚠️ Sitio no disponible "
                f"para {tipo.upper()}."

            )


            print(

                f"🛡️ Se conserva "
                f"{config['rss']} "
                f"sin modificaciones."

            )


            return None, 0


        if not soup:

            break


        for ficha in soup:

            h3 = ficha.find(
                'h3'
            )


            small = ficha.find(
                'small'
            )


            img = ficha.find(
                'img'
            )


            if not (
                h3
                and
                img
            ):

                continue


            nombre = h3.text.strip()


            fecha_texto = (

                small.text.strip()

                if small

                else ""
            )


            fecha_dt = parsear_fecha(
                fecha_texto
            )


            src = img.get(
                'src',
                ''
            )


            if not src:

                continue


            img_url = (

                BASE_URL + src

                if src.startswith('/')

                else src
            )


            fichas.append({

                "nombre":
                    nombre,

                "fecha":
                    fecha_dt,

                "texto_fecha":
                    fecha_texto,

                "imagen":
                    img_url
            })


        time.sleep(
            PAUSA_ENTRE_PAGINAS
        )


    # ========================================================
    # VALIDACIÓN
    # ========================================================

    if not fichas:

        print(

            f"⚠️ No se encontraron "
            f"registros en {tipo.upper()}."

        )


        print(

            f"🛡️ Se conserva "
            f"{config['rss']} "
            f"sin modificaciones."

        )


        return None, 0


    # ========================================================
    # ORDENAR
    # ========================================================

    fichas.sort(

        key=lambda x: x['fecha'],

        reverse=True
    )


    if not last_build_prev:

        last_build_prev = (

            ahora -
            timedelta(hours=1)
        )


    total_nuevas = sum(

        1

        for f in fichas

        if f['imagen']
        not in anteriores
    )


    intervalo = (

        (
            ahora -
            last_build_prev
        )
        /
        total_nuevas

        if total_nuevas > 0

        else timedelta(
            seconds=0
        )
    )


    nuevas = 0

    indice = 0


    # ========================================================
    # LAST BUILD
    # ========================================================

    fg.lastBuildDate(
        ahora
    )


    # ========================================================
    # GENERAR ITEMS
    # ========================================================

    for f in fichas:

        guid = f["imagen"]


        if guid in anteriores:

            pubdate = (

                anteriores[guid][
                    "pubdate"
                ]
            )


            lugar_hechos = (

                anteriores[guid].get(

                    "lugar_hechos",

                    ""
                )
            )


            hechos_texto = (

                anteriores[guid].get(

                    "hechos",

                    ""
                )
            )


        else:

            if total_nuevas > 0:

                hora_estim = (

                    last_build_prev
                    +
                    intervalo
                    *
                    (
                        total_nuevas
                        - 1
                        - indice
                    )
                )


            else:

                hora_estim = (

                    last_build_prev
                )


            pubdate = datetime(

                year=f["fecha"].year,

                month=f["fecha"].month,

                day=f["fecha"].day,

                hour=hora_estim.hour,

                minute=hora_estim.minute,

                second=hora_estim.second,

                tzinfo=TZ_CANCUN
            )


            lugar_hechos = ""

            hechos_texto = ""


            # =================================================
            # OCR
            # =================================================

            if config.get(
                "ocr",
                False
            ):

                raw_text = (

                    ocr_with_timeout(

                        f["imagen"],

                        timeout=20
                    )
                )


                if raw_text:

                    lugar_hechos = (

                        extraer_lugar_de_texto(

                            raw_text
                        )
                    )


                    hechos_texto = (

                        extraer_hechos_de_texto(

                            raw_text
                        )
                    )


            nuevas += 1

            indice += 1


        # ====================================================
        # CREAR ITEM
        # ====================================================

        entry = fg.add_entry()


        titulo_lista = (

            f["nombre"]
        )


        if lugar_hechos:

            titulo_lista += (

                f" - "
                f"{lugar_hechos}"
            )


        else:

            titulo_lista += (

                f" - "
                f"{f['texto_fecha']}"
            )


        entry.title(
            titulo_lista
        )


        entry.link(

            href=f["imagen"]
        )


        entry.guid(

            f["imagen"],

            permalink=True
        )


        entry.pubDate(
            pubdate
        )


        desc = (

            f"<img src='{f['imagen']}' "
            f"width='600' />"
        )


        if hechos_texto:

            desc += (

                f"<br>"
                f"<strong>Hechos:</strong> "
                f"{hechos_texto}"
            )


        entry.description(
            desc
        )


    # ========================================================
    # GUARDAR RSS
    # ========================================================

    fg.rss_file(

        config["rss"],

        pretty=True
    )


    print(

        f"✅ Generado "
        f"{config['rss']} "
        f"({nuevas} nuevas)"
    )


    return (

        config["rss"],

        nuevas
    )


# ============================================================
# GIT
# ============================================================

def subir_a_github(
    archivos,
    nuevas_total
):

    if nuevas_total == 0:

        print(

            "\nℹ️ No hay nuevos "
            "registros."
        )

        return


    print(

        "\n📤 Preparando "
        "subida a GitHub..."
    )


    try:

        # --------------------------------------------
        # ACTUALIZAR REPOSITORIO
        # --------------------------------------------

        print(
            "🔄 Actualizando "
            "repositorio..."
        )


        resultado_pull = subprocess.run(

            [
                "git",
                "pull",
                "--rebase"
            ],

            check=True
        )


        # --------------------------------------------
        # AGREGAR SOLO RSS
        # --------------------------------------------

        for archivo in archivos:

            if os.path.exists(
                archivo
            ):

                subprocess.run(

                    [
                        "git",
                        "add",
                        archivo
                    ],

                    check=True
                )


        # --------------------------------------------
        # VERIFICAR CAMBIOS
        # --------------------------------------------

        resultado = subprocess.run(

            [
                "git",
                "diff",
                "--cached",
                "--quiet"
            ]
        )


        if resultado.returncode == 0:

            print(

                "ℹ️ No hay cambios "
                "que subir a GitHub."
            )

            return


        # --------------------------------------------
        # COMMIT
        # --------------------------------------------

        fecha_commit = (

            datetime.now(
                TZ_CANCUN
            ).strftime(
                "%Y-%m-%d %H:%M:%S"
            )
        )


        subprocess.run(

            [
                "git",
                "commit",
                "-m",
                (
                    "Actualización RSS FGE - "
                    f"{fecha_commit}"
                )
            ],

            check=True
        )


        # --------------------------------------------
        # PUSH
        # --------------------------------------------

        print(
            "📤 Enviando a GitHub..."
        )


        subprocess.run(

            [
                "git",
                "push"
            ],

            check=True
        )


        print(

            "✅ RSS enviados "
            "correctamente a GitHub."
        )


    except subprocess.CalledProcessError as e:

        print(
            f"[❌] Error Git: {e}"
        )


    except Exception as e:

        print(
            f"[❌] Error inesperado Git: {e}"
        )


# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":

    print(
        "\n======================================"
    )


    print(
        " RSS MAESTRO FGE QUINTANA ROO"
    )


    print(
        "======================================"
    )


    print(
        f"🌐 Servidor: {BASE_URL}"
    )


    print(
        f"🔁 Reintentos por solicitud: "
        f"{MAX_REINTENTOS}"
    )


    archivos_generados = []

    nuevas_total = 0


    tipos_exitosos = 0

    tipos_fallidos = 0


    # ========================================================
    # PROCESAR TIPOS
    # ========================================================

    for tipo, config in TIPOS.items():

        try:

            archivo, nuevas = (

                generar_rss(

                    tipo,

                    config
                )
            )


            # ----------------------------------------
            # SITIO NO DISPONIBLE
            # ----------------------------------------

            if archivo is None:

                tipos_fallidos += 1

                continue


            # ----------------------------------------
            # ÉXITO
            # ----------------------------------------

            tipos_exitosos += 1


            if archivo:

                archivos_generados.append(
                    archivo
                )


            nuevas_total += nuevas


        except Exception as e:

            tipos_fallidos += 1


            print(

                f"\n[❌] Error procesando "
                f"{tipo.upper()}: {e}"
            )


    # ========================================================
    # RESUMEN
    # ========================================================

    print(
        "\n======================================"
    )


    print(
        " RESUMEN"
    )


    print(
        "======================================"
    )


    print(
        f"✅ Categorías procesadas: "
        f"{tipos_exitosos}"
    )


    print(
        f"⚠️ Categorías con error: "
        f"{tipos_fallidos}"
    )


    print(
        f"🆕 Nuevos registros: "
        f"{nuevas_total}"
    )


    # ========================================================
    # GIT UNA SOLA VEZ
    # ========================================================

    if nuevas_total > 0:

        subir_a_github(

            archivos_generados,

            nuevas_total
        )

    else:

        print(

            "\nℹ️ No se ejecutará "
            "GitHub porque no hay "
            "nuevos registros."
        )


    print(
        "\n======================================"
    )


    print(
        " PROCESO TERMINADO"
    )


    print(
        "======================================\n"
    )