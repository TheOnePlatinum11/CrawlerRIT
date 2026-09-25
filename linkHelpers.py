#Elaborado por: Elias e Ignacio

import logging
import os
import re
import threading
import time
from urllib.parse import urlparse, urlsplit, urlunsplit
from urllib.robotparser import RobotFileParser

import requests
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options

listaURLs = set()
NUM_ITERS = 3  # unas 40 ???
DELAY = 1.0
RENDER_WAIT = 2.5

MIN_RELEVANCIA = 4
MAX_LINKS_POR_ITERACION = 1000
MAX_POR_DOMINIO = 100

DOMINIOS_BLOQUEADOS = {
    "facebook.com", "fb.com", "instagram.com", "x.com", "twitter.com",
    "youtube.com", "youtu.be", "tiktok.com", "reddit.com", "linkedin.com",
    "whatsapp.com", "wa.me", "pinterest.com", "telegram.me", "t.me",
    "snapchat.com", "discord.com", "vk.com", "vk.cc", "weibo.com", "twitch.tv",
    "doubleclick.net", "googletagservices.com", "googleadservices.com",
    "googletagmanager.com", "google-analytics.com", "hotjar.com", "mxpnl.com",
    "amazon.com", "ebay.com", "shopify.com", "play.google.com", "aliexpress.com",
    "mercadolibre.com", "netflix.com", "spotify.com", "soundcloud.com",
    "google.com", "googleusercontent.com", "bing.com", "yahoo.com",
    "duckduckgo.com", "baidu.com", "yandex.com", "ask.com",
}

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

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s %(levelname)s [%(threadName)s] %(message)s")
logger = logging.getLogger("crawler")

ultimoAcceso = {}
crawlLock = threading.Lock()

robotsCache = {}
robotsLock = threading.Lock()

driverLocal = threading.local()


def _driver():
    driver = getattr(driverLocal, "driver", None)
    if driver is None:
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


def _hostPermitido(host: str) -> bool:
    host = host.lower().lstrip("www.")
    for b in DOMINIOS_BLOQUEADOS:
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
    porDominio = {}
    seleccion = []
    for u, ancla in sorted(normalizados, key=lambda x: (not _hintURL(x[0], x[1]), x)):
        dom = urlparse(u).netloc.lower().lstrip("www.")
        if porDominio.get(dom, 0) >= MAX_POR_DOMINIO:
            continue
        porDominio[dom] = porDominio.get(dom, 0) + 1
        seleccion.append(u)
        if len(seleccion) >= MAX_LINKS_POR_ITERACION:
            break
    return seleccion


def puntajeRelevancia(texto: str) -> int:
    if not texto:
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


def esRobotsPermitido(url: str) -> bool:
    host = urlparse(url).netloc
    if not host:
        return False
    parser = robotsCache.get(host)
    if parser is None:
        parser = RobotFileParser()
        lineas = _leerRobotsTXT(host)
        if lineas is None:
            logger.error(f"[ROBOTS] {host}: robots.txt ilegible, se permite (fail-open)")
        else:
            parser.parse(lineas)
        with robotsLock:
            robotsCache[host] = parser
    return parser.can_fetch("BreteRIT/1.0", url)


def descargarHTML(url: str, numIter: int = 0):
    logger.info(f"Descargando: {url}")
    try:
        driver = _driver()
        driver.get(url)
        time.sleep(RENDER_WAIT)
        return driver.page_source
    except Exception as e:
        logger.error(f"Error al descargar {url} con Selenium: {e}")
        try:
            html = requests.get(url, headers={"User-Agent": "BreteRIT/1.0"})
            return html.text
        except requests.RequestException as e2:
            logger.error(f"Error al descargar {url} con requests: {e2}")
            return ""


def nombreArchivo(nomArchivo: str) -> str:
    nombre = re.sub(r'[<>:"/\\|?*]', '_', nomArchivo)
    return f"HTMLs/{nombre}.txt"


def yaDescargado(nomArchivo: str) -> bool:
    return bool(nomArchivo) and os.path.exists(nombreArchivo(nomArchivo))


def guardarTexto(texto: str, nomArchivo: str):
    if not nomArchivo:
        return
    os.makedirs("HTMLs", exist_ok=True)
    with open(nombreArchivo(nomArchivo), "w", encoding="utf-8") as archivo:
        archivo.write(texto)


def esperarCrawlDelay(url: str):
    host = urlparse(url).netloc
    with crawlLock:
        disponible = ultimoAcceso.get(host, 0.0)
        ahora = time.time()
        espera = max(disponible - ahora, 0.0)
        ultimoAcceso[host] = max(disponible, ahora) + DELAY
    if espera > 0:
        time.sleep(espera)


def parsearPagina(html: str):
    patron = r'https?://[a-zA-Z0-9.-]+\.[a-zA-Z]{2,6}(?:/[^\s"<>]*)?'
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup.find_all(["script", "style"]):
        tag.decompose()
    texto = soup.get_text()
    links = set()
    for link in soup.find_all("a"):
        href = link.get("href")
        if href and re.match(patron, href):
            n = normalizarURL(href)
            if n and esURLUtil(n):
                ancla = link.get_text(strip=True)[:60]
                links.add((n, ancla))
    return texto, links