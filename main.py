import argparse
import threading
from queue import Queue

from linkHelpers import (
    MIN_RELEVANCIA, NUM_ITERS, cerrarDrivers, depurarLinks,
    descargarHTML, esRobotsPermitido, esperarCrawlDelay, guardarLinks,
    guardarTexto, leerURLs, logger, parsearPagina, puntajeRelevancia,
    seleccionarFrontera, yaDescargado,
)

STOP = object()

cola = Queue()
lock = threading.Lock()
linksAcumulados = set()
pendientes = 0
loteTerminado = threading.Event()


def procesarURL(url: str):
    if yaDescargado(url):
        return
    html = descargarHTML(url)
    if not html:
        return
    texto, links = parsearPagina(html)
    p = puntajeRelevancia(texto)
    if p < MIN_RELEVANCIA:
        logger.info(f"[PUNT] {url}: relevancia {p} < {MIN_RELEVANCIA}, descartada")
        return
    logger.info(f"[PUNT] {url}: relevancia {p}")
    guardarTexto(texto, url)
    with lock:
        linksAcumulados.update(links)


def trabajador():
    global pendientes
    while True:
        url = cola.get()
        if url is STOP:
            cerrarDrivers()
            break
        try:
            esperarCrawlDelay(url)
            if esRobotsPermitido(url):
                procesarURL(url)
            else:
                logger.info(f"[ROBOTS] {url}: descartado por robots.txt")
        finally:
            with lock:
                pendientes -= 1
                if pendientes == 0:
                    loteTerminado.set()


def main(maxWorkers: int):
    global pendientes
    hilos = [threading.Thread(target=trabajador, name=f"araña-{n}")
             for n in range(maxWorkers)]
    for t in hilos:
        t.start()

    i = 0
    while i < NUM_ITERS:
        urls = leerURLs(f"assets/URLs{i}.txt")
        if not urls:
            i += 1
            continue

        linksAcumulados.clear()
        with lock:
            pendientes = len(urls)
        loteTerminado.clear()

        for url in urls:
            cola.put(url)
        logger.info(f"Lote {i}: {len(urls)} URLs en cola")

        loteTerminado.wait()
        frontera = seleccionarFrontera(linksAcumulados)
        guardarLinks(frontera, str(i + 1))
        logger.info(f"Lote {i} terminado: {len(urls)} URLs procesadas, "
                    f"frontera [{len(frontera)}]")
        i += 1

    for _ in hilos:
        cola.put(STOP)
    for t in hilos:
        t.join()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="BreteRIT: araña enfocada")
    parser.add_argument("--workers", type=int, default=4,
                        help=f"número de hilos araña (default: 4)")
    args = parser.parse_args()
    main(maxWorkers=args.workers)
    depurarLinks()