import threading
from queue import Queue

from linkHelpers import (
    MAX_WORKERS, NUM_ITERS, depurarLinks, descargarHTML, esperarCrawlDelay,
    guardarLinks, guardarTexto, leerURLs, logger, parsearPagina, yaDescargado,
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
    guardarTexto(texto, url)
    with lock:
        linksAcumulados.update(links)


def trabajador():
    global pendientes
    while True:
        url = cola.get()
        if url is STOP:
            break
        esperarCrawlDelay(url)
        procesarURL(url)
        with lock:
            pendientes -= 1
            if pendientes == 0:
                loteTerminado.set()


def main():
    global pendientes
    hilos = [threading.Thread(target=trabajador, name=f"araña-{n}")
             for n in range(MAX_WORKERS)]
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
        guardarLinks(linksAcumulados, str(i + 1))
        logger.info(f"Lote {i} terminado: {len(urls)} URLs procesadas")
        i += 1

    for _ in hilos:
        cola.put(STOP)
    for t in hilos:
        t.join()


if __name__ == "__main__":
    main()
    depurarLinks()