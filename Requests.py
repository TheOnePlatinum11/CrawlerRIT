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
    soup = BeautifulSoup(html, "html.parser")
    links = set()
    for link in soup.find_all("a"):
        href = link.get("href")
        if href and href.startswith("http"):
            links.add(href)
    return links

def guardarLinks(links: set[str]):
    with open("URLs.txt", "w") as archivo:
        for link in links:
            archivo.write(f"{link}\n")
            print(link)

