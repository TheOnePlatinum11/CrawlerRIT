#Elaborado por: Elias e Ignacio

from datetime import datetime
import os 
import sys
import re
import requests
from bs4 import BeautifulSoup

listaURLs = []

def leerURLs(file_path: str):
    with open(file_path) as archivo:
        URLs = set(archivo.readlines())
    return URLs

def descargarHTML(url: str):
    print(f"Descargando: {url}")
    try:
        explorados = set()
        headers = {
            'User-Agent': 'BreteRIT/1.0'
            }
        
        if url in explorados:
            return ""
        html = requests.get(url, headers=headers)
        with open("assets/URLsExplorados.txt", "a") as archivo:
            archivo.write(f"{url}")
        return html.text
    except requests.RequestException as e:
        print(f"Error al descargar {url}: {e}")
        return ""

def detectarLinks(html: str):
    patron = r'https?://[a-zA-Z0-9.-]+\.[a-zA-Z]{2,6}(?:/[^\s"<>]*)?'
    soup = BeautifulSoup(html, "html.parser")
    links = set()
    existentes = leerURLs("assets/URLs.txt")
    for link in soup.find_all("a"):
        href = link.get("href")
        if href and re.match(patron, href):
            links.add(href)
    links = links - existentes
    return links

def guardarLinks(links: set[str]):

    with open("assets/URLs.txt", "a") as archivo:
        for link in links:
            archivo.write(f"{link}\n")
            print(link)

