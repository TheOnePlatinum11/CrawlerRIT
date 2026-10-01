#Elaborado por: Elias e Ignacio

import html as html_lib
import logging
import os
import queue
import re
import threading
import time
from logging.handlers import RotatingFileHandler
from urllib.parse import urljoin, urlparse, urlsplit, urlunsplit
from urllib.robotparser import RobotFileParser

import requests
from bs4 import BeautifulSoup

import sqlite3

import unicodedata

listaURLs = set()
NUM_ITERS = 40  # unas 40 ???
DELAY = 1.0
RENDER_WAIT = 2.5

TIMEOUT_HTTP = (6, 12)  # (conectar, leer): tope corto para no atascar el hilo

PAUSA_MS = 250  # separación mínima entre peticiones al mismo host
MIN_HTML_PARSE = 2000  # páginas más pequeñas no se parsean (basura/redirect)

MIN_CHARS_JS = 400
MIN_PRUEBAS_JS = 12

MIN_RELEVANCIA = 4
MAX_POR_LOTE = 1000  # tope de la cola por iteracion, no de la base de datos

EXCLUSIONES_URL = re.compile(
    r"(/login|/signup|/logout|/register|/cart|/checkout|/account|/privacy|"
    r"/terms|/password|/search|/archive\.php|\.(jpg|jpeg|png|gif|svg|webp|ico|"
    r"mp4|avi|mov|webm|mp3|wav|zip|tar|gz|exe|pdf|css|js|woff2?|ttf)\b)",
    re.I,
)

TERMINOS_RELEVANTES = re.compile(
    r"\b(intervenci\w+|intervencionismo|intervent\w+|intervenç\w+|"
    r"golpe de estado|golpe militar|invas\w+|invad\w+|ocupaci\w+|"
    r"occupi\w+|occupied|embargo|bloqueo|blockade|sanctions?|sanciones|"
    r"dictadur\w+|dictatorship|dictador|guerra fr\w*|cold war|"
    r"doctrina monroe|monroe doctrine|doutrina monroe|operaci.n c.nd|"
    r"operation condor|c.ndor|condor|misil\w+|missiles?|crisis de los misiles|"
    r"missile crisis|bah.a de cochinos|bay of pigs|latinoam\w+|latin america|"
    r"latin american|america latina|centroam\w+|central america|south america|"
    r"estados unidos|united states|estadounid\w+|norteamerican\w+|imperial\w+|"
    r"imperialism|hegemon\w+|hegemony|revoluci\w+|revoluç\w+|revolut\w+|"
    r"guerrilla|sandinista|contrainsurgencia|contras?|somoza|pinochet|"
    r"allende|castro|arbenz|torrijos|noriega|batista|trujillo|represi\w+|"
    r"repression|desclasific\w+|injerencia|interference|yanqui|diplomaci\w+|"
    r"diplomatic|canal de panama|espionaje|espionage|subvers\w+|subversion|"
    r"guerra sucia|regime change|cambio de regimen|covert|destabiliz\w+|"
    r"proxy war|guerra por poderes|drug war|guantanam\w+|chile|argentina|cuba|"
    r"nicaragua|guatemala|panama|honduras|el salvador|mexic\w+|colombia|"
    r"venezuela|peru|bolivia|uruguay|paraguay|brasil\w+|brazil|puerto rico|"
    r"haiti|granada|grenada|republica dominicana|república dominicana|"
    r"dominican republic|the caribbean|caribe)\b",
    re.I,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(threadName)s] %(message)s",
    handlers=[
        logging.StreamHandler(),
        RotatingFileHandler("bitacora.log", maxBytes=50 * 1024 * 1024,
                            backupCount=5, encoding="utf-8"),
    ],
)
logger = logging.getLogger("crawler")

ultimoAcceso = {}
crawlLock = threading.Lock()

robotsCache = {}
robotsLock = threading.Lock()
robotsDescartados = set()  # claves base conocidas como prohibidas por robots

driverLocal = threading.local()
sesionLocal = threading.local()

SEMAFORO_JS = threading.Semaphore(2)
hostsConJS = set()
presupuestoJS = [MIN_PRUEBAS_JS]
presupuestoLock = threading.Lock()

_dominiosJS = None
_dominiosJSLock = threading.Lock()


def cargarDominiosJS(ruta: str = "assets/JS0.txt") -> set[str]:
    global _dominiosJS
    with _dominiosJSLock:
        if _dominiosJS is not None:
            return _dominiosJS
        dominios = set()
        if os.path.exists(ruta):
            with open(ruta, "r", encoding="utf-8") as archivo:
                for linea in archivo:
                    dominio = linea.split("#", 1)[0].strip().lower()
                    if not dominio:
                        continue
                    dominio = re.sub(r"^https?://", "", dominio)
                    dominio = dominio.split("/", 1)[0].split(":", 1)[0]
                    dominio = dominio.removeprefix("www.")
                    if dominio:
                        dominios.add(dominio)
            logger.info(f"Dominios con JS forzado ({len(dominios)}): {sorted(dominios)}")
        else:
            logger.info(f"Sin lista de JS forzado: {ruta} no existe")
        _dominiosJS = dominios
        return _dominiosJS


def _hostForzadoJS(host: str) -> bool:
    for d in cargarDominiosJS():
        if host == d or host.endswith("." + d):
            return True
    return False


_dominiosBloqueados = None
_dominiosBloqueadosLock = threading.Lock()


def cargarDominiosBloqueados(ruta: str = "assets/Bloqueados0.txt") -> set[str]:
    global _dominiosBloqueados
    with _dominiosBloqueadosLock:
        if _dominiosBloqueados is not None:
            return _dominiosBloqueados
        dominios = set()
        if os.path.exists(ruta):
            with open(ruta, "r", encoding="utf-8") as archivo:
                for linea in archivo:
                    dominio = linea.split("#", 1)[0].strip().lower()
                    if dominio:
                        dominios.add(dominio)
            logger.info(f"Dominios bloqueados ({len(dominios)}): {sorted(dominios)}")
        else:
            logger.warning(f"Sin lista de dominios bloqueados: {ruta} no existe")
        _dominiosBloqueados = dominios
        return _dominiosBloqueados


def configurarPausa(pausa_ms: int):
    global PAUSA_MS
    PAUSA_MS = max(pausa_ms, 0)


USAR_JS = False


def setUsarJS(flag: bool):
    global USAR_JS
    USAR_JS = flag


def _sesion() -> requests.Session:
    sesion = getattr(sesionLocal, "sesion", None)
    if sesion is None:
        sesion = requests.Session()
        sesion.headers.update({
            "User-Agent": "BreteRIT/1.0",
            "Accept-Encoding": "gzip, deflate, br",
        })
        sesionLocal.sesion = sesion
    return sesion


def _driver():
    driver = getattr(driverLocal, "driver", None)
    if driver is None:
        from selenium import webdriver
        from selenium.webdriver.chrome.options import Options

        opciones = Options()
        opciones.add_argument("--headless=new")
        opciones.add_argument("--no-sandbox")
        opciones.add_argument("--disable-dev-shm-usage")
        opciones.add_argument("--disable-gpu")
        opciones.add_argument("--disable-blink-features=AutomationControlled")
        opciones.add_argument("--blink-settings=imagesEnabled=false")
        opciones.add_argument("--user-agent=BreteRIT/1.0")
        opciones.page_load_strategy = "eager"
        driver = webdriver.Chrome(options=opciones)
        driver.set_page_load_timeout(60)
        try:
            driver.execute_cdp_cmd("Network.enable", {})
            driver.execute_cdp_cmd("Network.setBlockedURLs", {"urls": [
                "*://*/*.png", "*://*/*.jpg", "*://*/*.jpeg", "*://*/*.gif",
                "*://*/*.webp", "*://*/*.svg", "*://*/*.ico", "*://*/*.avif",
                "*://*/*.woff", "*://*/*.woff2", "*://*/*.ttf", "*://*/*.otf",
                "*://*/*.mp4", "*://*/*.mp3", "*://*/*.avi", "*://*/*.mov",
            ]})
        except Exception:
            pass
        driverLocal.driver = driver
    return driver


def cerrarDrivers():
    driver = getattr(driverLocal, "driver", None)
    if driver is not None:
        driver.quit()
        driverLocal.driver = None


def guardarLinks(links: set[str], nomArchivo: str):
    with open(f"assets/URLs{nomArchivo}.txt", "a") as archivo:
        for link in links:
            archivo.write(f"{link}\n")


def depurarLinks():
    listaURLs.clear()
    i = 0
    while i < NUM_ITERS:
        with open(f"assets/URLs{i}.txt", "r") as archivo:
            for linea in archivo:
                link = linea.strip()
                if link:
                    listaURLs.add(link)
        i += 1

    guardarLinks(listaURLs, "Explorados")
    return listaURLs


def leerURLs(filePath: str):
    with open(filePath) as archivo:
        URLs = set(linea.strip() for linea in archivo)
    return URLs


def normalizarURL(url: str) -> str:
    url = url.split("#", 1)[0]
    try:
        partes = urlsplit(url)
    except ValueError:
        return ""
    if partes.scheme not in ("http", "https"):
        return ""
    claves = [p for p in partes.query.split("&")
              if p and not re.match(r"^(utm_|fbclid|gclid|mc_|ref_|via_|hs_|spm_)",
                                    p.split("=")[0].lower())]
    consulta = "&".join(claves)
    reconstruida = urlunsplit((partes.scheme, partes.netloc, partes.path, consulta, ""))
    if not partes.query and partes.path.endswith("/") and partes.path != "/":
        reconstruida = reconstruida.rstrip("/")
    return reconstruida


def _hostRaiz(host: str) -> str:
    host = host.lower().split(":")[0]
    return host.removeprefix("www.")


def _hostPermitido(host: str) -> bool:
    host = _hostRaiz(host)
    for b in cargarDominiosBloqueados():
        if host == b or host.endswith("." + b):
            return False
    return True


def esURLUtil(url: str) -> bool:
    try:
        host = urlparse(url).netloc
    except ValueError:
        return False
    if not host or not _hostPermitido(host):
        return False
    if EXCLUSIONES_URL.search(url):
        return False
    return True


def hostRaizURL(url: str) -> str:
    return _hostRaiz(urlparse(url).netloc)


def esFalloHost(codigo) -> bool:
    if codigo is None:
        return True
    return codigo in (403, 429) or codigo >= 500


HINT_PISTAS = (
    "interven", "estados-unidos", "america-latina", "latinoamerica", "golpe",
    "condor", "embargo", "cuba", "chile", "nicaragua", "guatemala", "venezuela",
    "doctrina", "misiles", "guerra", "united-states", "latin-america",
    "regime-change", "coup", "intervention", "dictator",
)


def _hintURL(url: str, ancla: str = "") -> bool:
    texto = f"{url.lower()} {ancla.lower()}"
    return any(t in texto for t in HINT_PISTAS)


def seleccionarFrontera(links) -> list[str]:
    normalizados = set()
    for u, ancla in links:
        n = normalizarURL(u)
        if n and esURLUtil(n):
            normalizados.add((n, ancla))
    return [u for u, _ in sorted(normalizados, key=lambda x: (not _hintURL(x[0], x[1]), x))]


PISTAS_RAPIDAS = (
    "guerra", "cuba", "chile", "intervenci", "estados unidos", "revoluci",
    "dictadur", "golpe de estado", "regimen", "embargo", "pinochet", "condor",
    "mexic", "nicaragua", "guatemala", "argentina", "colombia", "venezuela",
    "latinoam", "america latina", "united states", "imperial", "sandinista",
    "castro", "allende", "panama", "honduras", "peru", "bolivia", "brasil",
    "haiti", "caribe", "guerrilla", "dictatorship", "intervent", "invas",
    "invad", "ocupaci", "occupi", "blockade", "sanction", "sanciones",
    "dictador", "guerra fr", "cold war", "doctrina monroe", "monroe doctrine",
    "operaci", "operation condor", "misil", "missile", "crisis de los misiles",
    "missile crisis", "bah", "bay of pigs", "latin america", "latin american",
    "centroam", "central america", "south america", "estadounid", "norteamerican",
    "imperialism", "hegemon", "hegemony", "revoluç", "revolut", "contrainsurgencia",
    "contra", "somoza", "arbenz", "torrijos", "noriega", "batista", "trujillo",
    "represi", "repression", "desclasific", "injerencia", "interference",
    "yanqui", "diplomaci", "diplomatic", "canal de panama", "espionaje",
    "espionage", "subvers", "subversion", "guerra sucia", "regime change",
    "cambio de regimen", "covert", "destabiliz", "proxy war", "guerra por poderes",
    "drug war", "guantanam", "el salvador", "puerto rico", "granada", "grenada",
    "republica dominicana", "república dominicana", "dominican republic",
    "the caribbean", "intervencionismo", "intervenç", "occupied", "bloqueo",
    "doutrina monroe", "uruguay", "paraguay", "brazil",
)


def puntajeRelevancia(texto: str) -> int:
    if not texto:
        return 0
    bajo = texto.lower()
    if not any(p in bajo for p in PISTAS_RAPIDAS):
        return 0
    return len(set(TERMINOS_RELEVANTES.findall(texto)))


def _leerRobotsTXT(host: str) -> list[str]:
    # urllib/RobotFileParser.read() usa un UA genérico (Python-urllib) que muchos
    # sitios responden 403, y no soporta gzip ni timeout. Se descarga con requests.
    for esquema in ("https", "http"):
        try:
            r = requests.get(f"{esquema}://{host}/robots.txt",
                             headers={"User-Agent": "BreteRIT/1.0"},
                             timeout=15)
            if r.status_code == 404:
                return []
            r.raise_for_status()
            return r.text.splitlines()
        except requests.RequestException as e:
            logger.warning(f"robots.txt de {host} ({esquema}) no accesible: {e}")
    return None


def _claveRobots(url: str) -> str:
    # Reduce ?action=edit&section=N (en cualquier orden) a su URL base, para que
    # la decision de robots de la base aplique a todas sus variaciones de edicion.
    partes = urlsplit(url)
    parametros = [p for p in partes.query.split("&") if p]
    if any(p == "action=edit" for p in parametros):
        parametros = [p for p in parametros
                      if p.split("=", 1)[0] not in ("action", "section")]
    return urlunsplit((partes.scheme, partes.netloc, partes.path,
                       "&".join(parametros), ""))


def esRobotsPermitido(url: str) -> bool:
    clave = _claveRobots(url)
    if url != clave:
        with robotsLock:
            if clave in robotsDescartados:
                return False
    host = urlparse(url).netloc
    if not host:
        return False
    parser = robotsCache.get(host)
    if parser is None:
        parser = RobotFileParser()
        lineas = _leerRobotsTXT(host)
        if lineas is None:
            logger.error(f"[ROBOTS] {host}: robots.txt ilegible, se permite (fail-open)")
            parser.parse(["User-agent: *", "Allow: /"])
        else:
            parser.parse(lineas)
        with robotsLock:
            robotsCache[host] = parser
    permitido = parser.can_fetch("BreteRIT/1.0", url)
    if not permitido:
        with robotsLock:
            robotsDescartados.add(clave)
    return permitido


RE_BLOQUES = re.compile(r"(?is)<(script|style|noscript)\b[^>]*>.*?</\1\s*>")
RE_ETIQUETAS = re.compile(r"(?s)<[^>]+>")
RE_ESPACIOS = re.compile(r"\s+")
RE_HREF = re.compile(r"""(?is)<a\b[^>]*\shref\s*=""")
RE_SHELL = re.compile(
    r"""(?i)(id=["'](?:root|app|__next|___gatsby)["']"""
    r"""|data-reactroot|\bng-app\b|__NUXT__|__NEXT_DATA__"""
    r"""|data-svelte|window\.__INITIAL_STATE__)""",
)
RE_DESAFIO = re.compile(
    r"(?i)(just a moment|checking your browser"
    r"|attention required.{0,20}cloudflare|cf-browser-verification|cf_chl_"
    r"|enable javascript and cookies|verifying you are human"
    r"|captcha-delivery|px-captcha"
    r"|request unsuccessful.{0,40}incapsula|access denied|unusual traffic)",
)


def _textoVisible(html: str) -> str:
    sinBloques = RE_BLOQUES.sub(" ", html)
    sinEtiquetas = RE_ETIQUETAS.sub(" ", sinBloques)
    return RE_ESPACIOS.sub(" ", sinEtiquetas).strip()


def _htmlNecesitaJS(html: str, codigoEstado: int | None) -> bool:
    if not html or codigoEstado is None:
        return False
    if codigoEstado in (403, 429, 503) and RE_DESAFIO.search(html):
        return True
    if codigoEstado >= 400:
        return False
    texto = _textoVisible(html)
    if len(texto) < MIN_CHARS_JS:
        return not RE_HREF.search(html)
    if len(texto) >= MIN_CHARS_JS * 2:
        return False
    return bool(RE_SHELL.search(html))


def _pareceContenidoReal(html: str) -> bool:
    if not html or len(html) < MIN_CHARS_JS:
        return False
    return len(_textoVisible(html)) >= MIN_CHARS_JS


def _puedeRenderizar(host: str) -> bool:
    with presupuestoLock:
        if host in hostsConJS:
            return True
        if presupuestoJS[0] <= 0:
            return False
        presupuestoJS[0] -= 1
        return True


def _marcarHostConJS(host: str):
    with presupuestoLock:
        hostsConJS.add(host)


def descargarHTML(url: str, incluirEstado: bool = False):
    try:
        respuesta = _sesion().get(url, timeout=TIMEOUT_HTTP)
        if incluirEstado:
            return respuesta.text, respuesta.status_code
        return respuesta.text
    except requests.RequestException as e:
        logger.error(f"Error al descargar {url} con requests: {e}")
        if incluirEstado:
            return "", None
        return ""


def descargarRenderizado(url: str, incluirEstado: bool = False):
    with SEMAFORO_JS:
        try:
            driver = _driver()
            driver.get(url)
            # Espera adaptativa: salir apenas el documento esté listo en vez de
            # dormir RENDER_WAIT fijo en cada página.
            paso = 0.2
            transcurrido = 0.0
            while transcurrido < RENDER_WAIT:
                listo = driver.execute_script("return document.readyState")
                if listo == "complete":
                    break
                time.sleep(paso)
                transcurrido += paso
            if transcurrido < RENDER_WAIT:
                time.sleep(0.3)
            html = driver.page_source
            if incluirEstado:
                codigoEstado = driver.execute_script(
                    "const nav = performance.getEntriesByType('navigation')[0]; "
                    "return nav ? (nav.responseStatus || null) : null;"
                )
                return html, codigoEstado
            return html
        except Exception as e:
            logger.error(f"Error al renderizar {url} con Selenium: {e}")
            if incluirEstado:
                return "", None
            return ""


def descargarPagina(url: str, incluirEstado: bool = False):
    if not USAR_JS:
        return descargarHTML(url, incluirEstado)
    logger.info(f"Descargando: {url}")
    host = _hostRaiz(urlparse(url).netloc)
    if _hostForzadoJS(host):
        logger.info(f"[JS] {host}: dominio forzado, renderizando con Chrome")
        render = descargarRenderizado(url, incluirEstado)
        htmlRender = render[0] if incluirEstado else render
        if htmlRender:
            return render
        logger.info(f"[JS] {url}: render fallo, se usa el HTML estatico")
        return descargarHTML(url, incluirEstado)
    resultado = descargarHTML(url, incluirEstado)
    html, codigoEstado = resultado if incluirEstado else (resultado, None)
    if not _htmlNecesitaJS(html, codigoEstado):
        return resultado
    if not _puedeRenderizar(host):
        logger.info(f"[JS] {url}: sin presupuesto de render, se usa el HTML estatico")
        return resultado
    logger.info(f"[JS] {url}: HTML estatico insuficiente, renderizando con Chrome")
    render = descargarRenderizado(url, incluirEstado)
    htmlRender = render[0] if incluirEstado else render
    if _pareceContenidoReal(htmlRender):
        _marcarHostConJS(host)
        logger.info(f"[JS] {host}: marcado como host con JS, se renderiza siempre")
    return render


def nombreArchivo(nomArchivo: str) -> str:
    nombre = re.sub(r'[<>:"/\\|?*]', '_', nomArchivo)
    return f"HTMLs/{nombre}.txt"


def yaDescargado(nomArchivo: str) -> bool:
    return bool(nomArchivo) and os.path.exists(nombreArchivo(nomArchivo))

def cortarTexto(texto: str):
    textocort = ""
    palabras = texto.replace("/"," ").replace("-"," ").replace("_"," ").split()

    for palabra in palabras: 
        
        palabra = unicodedata.normalize('NFD', palabra)
        palabra = re.sub(r'[^a-zA-Z0-9]', '', palabra)
        palabra: str = palabra.lower()
        """if len(palabra) > 6:
            palabra = palabra[:6]"""
        
        
        textocort += ''.join(c for c in palabra if unicodedata.category(c) != 'Mn') + " "
    return textocort

def guardarTexto(texto: str, nomArchivo: str) -> int:
    if not nomArchivo:
        return 0
    os.makedirs("HTMLs", exist_ok=True)
    with open(nombreArchivo(nomArchivo), "w", encoding="utf-8") as archivo:
        contenido = cortarTexto(texto)
        archivo.write(contenido)
        return len(contenido.encode("utf-8"))


def esperarCrawlDelay(url: str):
    if PAUSA_MS <= 0:
        return
    host = urlparse(url).netloc
    gap = PAUSA_MS / 1000.0
    with crawlLock:
        ahora = time.time()
        prev = ultimoAcceso.get(host)
        if prev is None:
            ultimoAcceso[host] = ahora + gap
            espera = 0.0
        else:
            disponible = max(prev, ahora) + gap
            ultimoAcceso[host] = disponible
            espera = max(disponible - ahora, 0.0)
    if espera > 0:
        time.sleep(espera)


def parsearPagina(html: str, urlBase: str = ""):
    if not html or len(html) < MIN_HTML_PARSE:
        return "", set()
    soup = BeautifulSoup(html, "lxml")
    for tag in soup.find_all(["script", "style"]):
        tag.decompose()
    texto = soup.get_text()
    links = set()
    for link in soup.find_all("a"):
        href = link.get("href")
        if not href:
            continue
        n = normalizarURL(urljoin(urlBase, href))
        if n and esURLUtil(n):
            links.add((n, ""))
    return texto, links


def inicializarBD(
    rutaBD: str = "crawler.db",
    archivoSemillas: str = "assets/URLs0.txt",
    cantidadSemillas: int | None = None,
):
    conexion = sqlite3.connect(rutaBD, timeout=30)
    try:
        conexion.execute("PRAGMA journal_mode = WAL")
        conexion.execute("PRAGMA busy_timeout = 30000")
        conexion.execute("PRAGMA wal_autocheckpoint = 1000")
        conexion.execute(
            """CREATE TABLE IF NOT EXISTS paginas (
                   id INTEGER PRIMARY KEY AUTOINCREMENT,
                   url TEXT NOT NULL UNIQUE,
                   titulo TEXT,
                   codigo_estado INTEGER,
                   scrapeada INTEGER NOT NULL DEFAULT 0
                       CHECK (scrapeada IN (0, 1)),
                   fecha_visita TEXT
               )"""
        )
        conexion.execute(
            "CREATE INDEX IF NOT EXISTS idx_paginas_pendientes "
            "ON paginas (scrapeada, id)"
        )
        columnas = {fila[1] for fila in conexion.execute("PRAGMA table_info(paginas)")}
        if "reservada" not in columnas:
            conexion.execute(
                "ALTER TABLE paginas ADD COLUMN reservada INTEGER NOT NULL DEFAULT 0"
            )
        if conexion.execute(
            "SELECT 1 FROM paginas WHERE scrapeada = 0 AND reservada = 1 LIMIT 1"
        ).fetchone():
            while True:
                n = conexion.execute(
                    "UPDATE paginas SET reservada = 0 WHERE id IN ("
                    "SELECT id FROM paginas WHERE scrapeada = 0 AND reservada = 1 "
                    "LIMIT 10000)"
                ).rowcount
                if n == 0:
                    break
        if os.path.exists(archivoSemillas) and (
            cantidadSemillas is None or cantidadSemillas > 0
        ):
            semillas = []
            with open(archivoSemillas, "r", encoding="utf-8") as archivo:
                for linea in archivo:
                    url = normalizarURL(linea.strip())
                    if url:
                        semillas.append((url,))
                    if (
                        cantidadSemillas is not None
                        and len(semillas) >= cantidadSemillas
                    ):
                        break
            conexion.executemany(
                "INSERT OR IGNORE INTO paginas (url) VALUES (?)", semillas
            )
        conexion.commit()
    finally:
        conexion.close()


def registrarURLsBD(urls, rutaBD: str = "crawler.db") -> int:
    registros = []
    for url in urls:
        normalizada = normalizarURL(url)
        if normalizada:
            registros.append((normalizada,))

    conexion = sqlite3.connect(rutaBD, timeout=30)
    try:
        conexion.execute("PRAGMA busy_timeout = 30000")
        cursor = conexion.executemany(
            "INSERT OR IGNORE INTO paginas (url) VALUES (?)", registros
        )
        conexion.commit()
        return cursor.rowcount
    finally:
        conexion.close()


def obtenerURLsPendientesBD(
    rutaBD: str = "crawler.db",
    limite: int | None = None,
    aleatorio: bool = False,
) -> list[str]:
    conexion = sqlite3.connect(rutaBD, timeout=30)
    try:
        consulta = "SELECT url FROM paginas WHERE scrapeada = 0"
        parametros = ()
        if limite is not None:
            if limite <= 0:
                return []
            # Aleatorio reparte el lote entre miles de hosts:
            consulta += " ORDER BY RANDOM()" if aleatorio else " ORDER BY id"
            consulta += " LIMIT ?"
            parametros = (limite,)
        filas = conexion.execute(consulta, parametros).fetchall()
        return [fila[0] for fila in filas]
    finally:
        conexion.close()


def reclamarLoteBD(rutaBD: str = "crawler.db", limite: int = 1000) -> list[str]:
    if limite <= 0:
        return []
    conexion = sqlite3.connect(rutaBD, timeout=30)
    try:
        conexion.execute("PRAGMA busy_timeout = 30000")
        filas = conexion.execute(
            "UPDATE paginas SET reservada = 1 WHERE id IN ("
            "SELECT id FROM paginas WHERE scrapeada = 0 AND reservada = 0 "
            "ORDER BY RANDOM() LIMIT ?) RETURNING url",
            (limite,),
        ).fetchall()
        conexion.commit()
        return [fila[0] for fila in filas]
    finally:
        conexion.close()


_colaResultados: queue.Queue | None = None
_escritorThread: threading.Thread | None = None
_escritorStop = threading.Event()


def iniciarEscritor(rutaBD: str = "crawler.db"):
    global _colaResultados, _escritorThread
    _colaResultados = queue.Queue()
    _escritorStop.clear()
    _escritorThread = threading.Thread(
        target=_bucleEscritor, args=(rutaBD,), name="escritor-bd", daemon=True
    )
    _escritorThread.start()


def encolarResultado(url: str, titulo, codigo):
    if _colaResultados is not None:
        _colaResultados.put((url, titulo, codigo))


def cerrarEscritor():
    _escritorStop.set()
    if _escritorThread is not None:
        _escritorThread.join(timeout=15)


def _bucleEscritor(rutaBD: str):
    conexion = sqlite3.connect(rutaBD, timeout=30)
    conexion.execute("PRAGMA busy_timeout = 30000")
    conexion.execute("PRAGMA synchronous = NORMAL")
    lote = []
    try:
        while not _escritorStop.is_set() or (
            _colaResultados is not None and not _colaResultados.empty()
        ):
            try:
                item = _colaResultados.get(timeout=0.5)
            except queue.Empty:
                continue
            lote.append(item)
            if len(lote) >= 1000:
                _escribirLote(conexion, lote)
                lote.clear()
        if lote:
            _escribirLote(conexion, lote)
    except Exception as e:
        logger.error(f"Error en el hilo escritor de la BD: {e}")
    finally:
        conexion.close()


def _escribirLote(conexion, lote):
    fechaVisita = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    registros = [
        (titulo, codigo, fechaVisita, normalizarURL(url))
        for (url, titulo, codigo) in lote
    ]
    registros = [r for r in registros if r[3]]
    if not registros:
        return
    conexion.executemany(
        """UPDATE paginas
           SET titulo = ?, codigo_estado = ?, scrapeada = 1, reservada = 0,
               fecha_visita = ?
           WHERE url = ?""",
        registros,
    )
    conexion.commit()


def puntoControlBD(rutaBD: str = "crawler.db"):
    try:
        conexion = sqlite3.connect(rutaBD, timeout=5)
        conexion.execute("PRAGMA busy_timeout = 2000")
        conexion.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        conexion.close()
    except sqlite3.Error as e:
        logger.error(f"Checkpoint del WAL fallido: {e}")


def iniciarMantenimientoBD(rutaBD: str = "crawler.db"):
    threading.Thread(
        target=_bucleMantenimiento, args=(rutaBD,),
        name="mantenimiento-wal", daemon=True,
    ).start()


def _bucleMantenimiento(rutaBD: str):
    while not _escritorStop.is_set():
        time.sleep(5)
        if not os.path.exists("crawler.db-wal"):
            continue
        tamano = os.path.getsize("crawler.db-wal")
        if tamano == 0:
            continue
        try:
            conexion = sqlite3.connect(rutaBD, timeout=15)
            conexion.execute("PRAGMA busy_timeout = 10000")
            if tamano > 8 * 1024 * 1024:
                conexion.execute("PRAGMA wal_checkpoint(TRUNCATE)")
                logger.info(f"Mantenimiento: WAL {tamano // (1024 * 1024)} MB truncado")
            else:
                conexion.execute("PRAGMA wal_checkpoint(PASSIVE)")
            conexion.close()
        except sqlite3.Error as e:
            logger.error(f"Error en mantenimiento del WAL: {e}")


def eliminarBloqueadosBD(rutaBD: str = "crawler.db") -> int:
    conexion = sqlite3.connect(rutaBD, timeout=30)
    try:
        conexion.execute("PRAGMA busy_timeout = 30000")
        try:
            filas = conexion.execute("SELECT id, url FROM paginas").fetchall()
        except sqlite3.OperationalError:
            return 0
        ids = [fila[0] for fila in filas
               if not _hostPermitido(urlparse(fila[1]).netloc)]
        if ids:
            for i in range(0, len(ids), 900):
                marca = ",".join("?" * len(ids[i:i + 900]))
                conexion.execute(
                    f"DELETE FROM paginas WHERE id IN ({marca})", ids[i:i + 900]
                )
            conexion.commit()
            logger.info(f"Eliminadas {len(ids)} URLs de dominios bloqueados de la BD")
        return len(ids)
    finally:
        conexion.close()


def guardarResultadoBD(
    url: str,
    titulo: str | None,
    codigoEstado: int | None,
    rutaBD: str = "crawler.db",
) -> bool:
    normalizada = normalizarURL(url)
    if not normalizada:
        return False
    fechaVisita = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    conexion = sqlite3.connect(rutaBD, timeout=30)
    try:
        conexion.execute("PRAGMA busy_timeout = 30000")
        cursor = conexion.execute(
            """UPDATE paginas
               SET titulo = ?, codigo_estado = ?, scrapeada = 1, fecha_visita = ?
               WHERE url = ?""",
            (titulo, codigoEstado, fechaVisita, normalizada),
        )
        conexion.commit()
        return cursor.rowcount > 0
    finally:
        conexion.close()


RE_TITULO = re.compile(r"(?is)<title[^>]*>(.*?)</title>")


def extraerTitulo(html: str) -> str | None:
    # Antes se construia un arbol BeautifulSoup completo (192 ms) solo para leer
    # <title>; main.py vuelve a parsear el mismo HTML en parsearPagina.
    encontrado = RE_TITULO.search(html)
    if encontrado is None:
        return None
    titulo = " ".join(RE_ETIQUETAS.sub(" ", encontrado.group(1)).split())
    return html_lib.unescape(titulo) or None