#Elaborado por: Elias e Ignacio

import logging
import os
import re
import threading
import time
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

listaURLs = set()
NUM_ITERS = 3  # unas 40 ???
MAX_WORKERS = 10
DELAY = 1.0

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s %(levelname)s [%(threadName)s] %(message)s")
logger = logging.getLogger("crawler")

ultimoAcceso = {}
crawlLock = threading.Lock()


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


def descargarHTML(url: str, numIter: int = 0):
    logger.info(f"Descargando: {url}")
    try:
        headers = {
            'User-Agent': 'BreteRIT/1.0'
        }
        html = requests.get(url, headers=headers)
        return html.text
    except requests.RequestException as e:
        logger.error(f"Error al descargar {url}: {e}")
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
    texto = soup.get_text()
    links = set()
    for link in soup.find_all("a"):
        href = link.get("href")
        if href and re.match(patron, href):
            links.add(href)
    return texto, links