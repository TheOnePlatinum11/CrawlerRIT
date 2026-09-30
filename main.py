import argparse
import threading
from queue import Queue

from linkHelpers import (
    MAX_POR_LOTE, MIN_RELEVANCIA, NUM_ITERS, cargarDominiosBloqueados,
    cargarDominiosJS, cerrarDrivers, configurarDelay, descargarPagina,
    eliminarBloqueadosBD, esRobotsPermitido, esperarCrawlDelay, esURLUtil,
    extraerTitulo, guardarResultadoBD, guardarTexto, inicializarBD, logger,
    obtenerURLsPendientesBD, parsearPagina, puntajeRelevancia, registrarURLsBD,
    seleccionarFrontera,
)

STOP = object() 
RUTA_BD = "crawler.db"

cola = Queue()
lock = threading.Lock()
linksAcumulados = set()
pendientes = 0
loteTerminado = threading.Event()


def procesarURL(url: str):
    html, codigoEstado = descargarPagina(url, incluirEstado=True)
    if not html:
        return None, codigoEstado
    titulo = extraerTitulo(html)
    texto, links = parsearPagina(html, url)
    with lock:
        linksAcumulados.update(links)
    p = puntajeRelevancia(texto)
    if p < MIN_RELEVANCIA:
        logger.info(f"[PUNT] {url}: relevancia {p} < {MIN_RELEVANCIA}, sin texto")
        return titulo, codigoEstado
    logger.info(f"[PUNT] {url}: relevancia {p}")
    guardarTexto(texto, url)
    return titulo, codigoEstado


def trabajador():
    global pendientes
    while True:
        url = cola.get()
        if url is STOP:
            cerrarDrivers()
            break
        titulo = None
        codigoEstado = None
        try:
            if not esURLUtil(url):
                logger.info(f"[BLOQUEO] {url}: descartado (dominio o ruta bloqueada)")
            else:
                esperarCrawlDelay(url)
                if esRobotsPermitido(url):
                    titulo, codigoEstado = procesarURL(url)
                else:
                    logger.info(f"[ROBOTS] {url}: descartado por robots.txt")
        except Exception as e:
            logger.exception(f"Error al procesar {url}: {e}")
        finally:
            try:
                guardarResultadoBD(url, titulo, codigoEstado, RUTA_BD)
            except Exception as e:
                logger.exception(f"Error al actualizar la BD para {url}: {e}")
            with lock:
                pendientes -= 1
                if pendientes == 0:
                    loteTerminado.set()


def main(maxWorkers: int, delay: float, lote: int = MAX_POR_LOTE):
    global pendientes
    cargarDominiosJS()
    cargarDominiosBloqueados()
    configurarDelay(delay)
    inicializarBD(RUTA_BD)
    eliminarBloqueadosBD(RUTA_BD)
    hilos = [threading.Thread(target=trabajador, name=f"araña-{n}")
             for n in range(maxWorkers)]
    for t in hilos:
        t.start()

    i = 0
    while i < NUM_ITERS:
        urls = obtenerURLsPendientesBD(RUTA_BD, lote, aleatorio=True)
        if not urls:
            logger.info("No hay URLs pendientes en la base de datos")
            break

        linksAcumulados.clear()
        with lock:
            pendientes = len(urls)
        loteTerminado.clear()

        for url in urls:
            cola.put(url)
        logger.info(f"Lote {i}: {len(urls)} URLs en cola")

        loteTerminado.wait()
        frontera = seleccionarFrontera(linksAcumulados)
        nuevas = registrarURLsBD(frontera, RUTA_BD)
        logger.info(f"Lote {i} terminado: {len(urls)} URLs procesadas, "
                f"frontera [{len(frontera)}], {nuevas} URLs nuevas")
        i += 1

    for _ in hilos:
        cola.put(STOP)
    for t in hilos:
        t.join()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="BreteRIT: araña enfocada")
    parser.add_argument("--workers", type=int, default=32,
                        help="número de hilos araña (default: 32)")
    parser.add_argument("--delay", type=float, default=1.0,
                        help="crawl-delay en segundos por host (default: 1.0)")
    parser.add_argument("--lote", type=int, default=MAX_POR_LOTE,
                        help="URLs por iteración (default: 1000)")
    args = parser.parse_args()
    main(maxWorkers=args.workers, delay=args.delay, lote=args.lote)