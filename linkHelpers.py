#Elaborado por: Elias e Ignacio

from datetime import datetime
import os 
import sys
import re
import requests
from bs4 import BeautifulSoup

listaURLs = set()
NUM_ITERS = 3 # unas 40 ???

def guardarLinks(links: set[str], nomArchivo: str):
    with open(f"assets/URLs{nomArchivo}.txt", "a") as archivo:
        for link in links:
            archivo.write(f"{link}\n")

def depurarLinks():
    # aca debemos agarrar todos los links en los n archivos
    # y meterlos en uno solo, para tener una lista final de
    # links a descargar
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

def leerURLs(file_path: str):
    with open(file_path) as archivo:
        URLs = set(archivo.readlines())
    return URLs

def descargarHTML(url: str, numIter: int):
    print(f"Descargando: {url}")
    try:
        headers = {
            'User-Agent': 'BreteRIT/1.0'
            }
        
        html = requests.get(url, headers=headers)
        return html.text
    except requests.RequestException as e:
        print(f"Error al descargar {url}: {e}")
        return ""

def detectarLinks(html: str, numIter: int):
    patron = r'https?://[a-zA-Z0-9.-]+\.[a-zA-Z]{2,6}(?:/[^\s"<>]*)?'
    soup = BeautifulSoup(html, "html.parser")
    links = set()
    for link in soup.find_all("a"):
        href = link.get("href")
        if href and re.match(patron, href):
            links.add(href)
    return links
