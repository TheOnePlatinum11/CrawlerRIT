#Elaborado por: Elias y Ignacio

from datetime import datetime
import os 
import sys
import re
import requests
from bs4 import BeautifulSoup



def leerURLs():
    with open("URLs.txt") as archivo:
        URLs = set(archivo.readlines())
    return URLs

def descargarHTML(url: str):
    html = requests.get(url)
    return html.text

def detectarLinks(html: str):
    patron = r'https?://[a-zA-Z0-9.-]+\.[a-zA-Z]{2,6}(?:/[^\s"<>]*)?'
    soup = BeautifulSoup(html, "html.parser")
    links = set()
    for link in soup.find_all("a"):
        href = link.get("href")
        if href and re.match(patron, href):
            links.add(href)
    return links

def guardarLinks(links: set[str]):

    with open("URLs.txt") as archivo:
        existentes = set(archivo.readlines())

    nuevos = links - existentes 

    with open("URLs.txt", "a") as archivo:
        for link in nuevos:
            archivo.write(f"{link}\n")
            print(link)

