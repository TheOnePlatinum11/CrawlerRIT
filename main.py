import argparse
import random
import signal
import threading
import time
from queue import Queue, Empty

from linkHelpers import (
    MAX_POR_LOTE, MIN_RELEVANCIA, NUM_ITERS, cargarDominiosBloqueados,
    cargarDominiosJS, cerrarEscritor, configurarPausa, descargarPagina,
    encolarResultado, esFalloHost, esRobotsPermitido, esperarCrawlDelay,
    esURLUtil, extraerTitulo, guardarTexto, hostRaizURL, iniciarEscritor,
    iniciarMantenimientoBD, inicializarBD, logger, parsearPagina,
    puntoControlBD, puntajeRelevancia, reclamarLoteBD, registrarURLsBD,
    setUsarJS,
)

RUTA_BD = "crawler.db"
TAMANO_PISCINA = 5000


def main(workers: int, lote: int, iters: int, noRobots: bool,
         pausaHost: int, fallosFrio: int, minVelocidad: int,
         minVentanas: int, usarJS: bool):
    cargarDominiosJS()
    cargarDominiosBloqueados()
    setUsarJS(usarJS)
    configurarPausa(pausaHost)
    inicializarBD(RUTA_BD)
    iniciarEscritor(RUTA_BD)
    iniciarMantenimientoBD(RUTA_BD)

    detener = threading.Event()
    productorListo = threading.Event()
    lock = threading.Lock()

    frontera = set()
    bytesEscritos = 0
    procesadas = 0
    reclamadas = 0
    enProceso = 0
    fallosHost = {}
    cola = Queue(maxsize=max(4096, lote * 2))
    presupuesto = float("inf") if iters == 0 else iters * lote

    def procesarURL(url: str):
        nonlocal bytesEscritos, procesadas
        titulo = None
        codigo = None
        host = hostRaizURL(url)
        try:
            with lock:
                fallos = fallosHost.get(host, 0)
            if fallos >= fallosFrio:
                logger.info(
                    f"[HOST-FRIO] {host}: host con {fallos} errores seguidos, "
                    f"descartado"
                )
                return
            if not esURLUtil(url):
                logger.info(f"[BLOQUEO] {url}: descartado (dominio o ruta bloqueada)")
                return
            if not noRobots and not esRobotsPermitido(url):
                logger.info(f"[ROBOTS] {url}: descartado por robots.txt")
                return
            esperarCrawlDelay(url)
            logger.info(f"Descargando: {url}")
            html, codigo = descargarPagina(url, incluirEstado=True)
            if esFalloHost(codigo):
                with lock:
                    n = fallosHost.get(host, 0) + 1
                    fallosHost[host] = n
                if n >= fallosFrio:
                    logger.info(
                        f"[HOST-FRIO] {host}: alcanzado {n} errores, se descartará"
                    )
            else:
                with lock:
                    fallosHost.pop(host, None)
            if not html:
                return
            titulo = extraerTitulo(html)
            texto, links = parsearPagina(html, url)
            with lock:
                frontera.update(links)
            p = puntajeRelevancia(texto)
            if p < MIN_RELEVANCIA:
                logger.info(
                    f"[PUNT] {url}: relevancia {p} < {MIN_RELEVANCIA}, sin texto"
                )
                return
            logger.info(f"[PUNT] {url}: relevancia {p}")
            nbytes = guardarTexto(texto, url)
            with lock:
                bytesEscritos += nbytes
        except Exception as e:
            logger.exception(f"Error al procesar {url}: {e}")
        finally:
            procesadas += 1
            encolarResultado(url, titulo, codigo)

    def trabajador():
        nonlocal enProceso
        while not (productorListo.is_set() and enProceso == 0 and cola.empty()):
            try:
                url = cola.get(timeout=0.25)
            except Empty:
                continue
            enProceso += 1
            try:
                procesarURL(url)
            finally:
                enProceso -= 1

    def productor():
        nonlocal reclamadas
        piscina = []
        vacios = 0
        try:
            while reclamadas < presupuesto and not detener.is_set():
                if not piscina:
                    falta = (TAMANO_PISCINA if presupuesto == float("inf")
                             else min(TAMANO_PISCINA, int(presupuesto - reclamadas)))
                    piscina = reclamarLoteBD(RUTA_BD, falta)
                    if not piscina:
                        vacios += 1
                        if vacios >= 15:
                            break
                        time.sleep(2)
                        continue
                    vacios = 0
                    random.shuffle(piscina)
                aEncolar = min(lote, len(piscina))
                loteEncolado = piscina[:aEncolar]
                piscina = piscina[aEncolar:]
                reclamadas += len(loteEncolado)
                for u in loteEncolado:
                    cola.put(u)
                logger.info(f"Lote: {len(loteEncolado)} URLs en cola")
        finally:
            productorListo.set()

    def vaciarFrontera():
        with lock:
            if not frontera:
                return
            instantanea = list(frontera)
            frontera.clear()
        urls = [l[0] for l in instantanea]
        nuevas = registrarURLsBD(urls, RUTA_BD)
        logger.info(f"Frontera: {len(urls)} enlaces, {nuevas} URLs nuevas")

    def registrador():
        while not detener.is_set():
            time.sleep(2)
            vaciarFrontera()
        vaciarFrontera()

    def estadisticas():
        ventana = [time.time(), 0, 0]
        ventanasTotales = 0
        ventanasBajas = 0
        while not detener.is_set():
            time.sleep(10)
            ahora = time.time()
            with lock:
                b = bytesEscritos
                p = procesadas
            seg = max(ahora - ventana[0], 0.001)
            mbs = (b - ventana[1]) / (1024 * 1024) / seg
            urlsMin = (p - ventana[2]) / seg * 60
            logger.info(
                f"[EST] {mbs:.2f} MB/s, {urlsMin:.0f} URLs/min, "
                f"{b / (1024 * 1024):.2f} MB total, {p} URLs"
            )
            ventanasTotales += 1
            if ventanasTotales >= minVentanas:
                if urlsMin < minVelocidad:
                    ventanasBajas += 1
                    if ventanasBajas >= minVentanas:
                        logger.info(
                            f"Rendimiento bajo ({urlsMin:.0f} URLs/min, "
                            f"{mbs:.2f} MB/s) durante {ventanasBajas} ventanas, "
                            f"deteniéndose..."
                        )
                        detener.set()
                else:
                    ventanasBajas = 0
            ventana[0], ventana[1], ventana[2] = ahora, b, p

    def on_sigint(sig, frame):
        logger.info("Apagado solicitado: cerrando BD y checkpoint del WAL...")
        detener.set()

    signal.signal(signal.SIGINT, on_sigint)

    registrador_t = threading.Thread(target=registrador, name="registrador",
                                     daemon=True)
    estadisticas_t = threading.Thread(target=estadisticas, name="estadisticas",
                                      daemon=True)
    registrador_t.start()
    estadisticas_t.start()
    hilos = [threading.Thread(target=trabajador, name=f"araña-{n}")
             for n in range(workers)]
    for t in hilos:
        t.start()
    productor_t = threading.Thread(target=productor, name="productor")
    productor_t.start()

    productor_t.join()
    for t in hilos:
        t.join()
    detener.set()
    registrador_t.join(timeout=5)
    cerrarEscritor()
    puntoControlBD(RUTA_BD)
    logger.info(f"Arañado terminado ({reclamadas} URLs reclamadas)")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="El Desclasificador: crawler enfocado en la Intervención Estadounidense en América Latina")
    parser.add_argument("--workers", type=int, default=128,
                        help="número de hilos araña (default: 128)")
    parser.add_argument("--lote", type=int, default=MAX_POR_LOTE,
                        help="URLs por lote (default: 1000)")
    parser.add_argument("--iters", type=int, default=NUM_ITERS,
                        help="lotes totales, 0 = ilimitado (default: 40)")
    parser.add_argument("--no-robots", action="store_true",
                        help="ignorar robots.txt")
    parser.add_argument("--pausa-host", type=int, default=250,
                        help="separación mínima en ms entre peticiones al mismo "
                             "host (default: 250)")
    parser.add_argument("--fallos-frio", type=int, default=3,
                        help="errores seguidos para descartar un host "
                             "(default: 3)")
    parser.add_argument("--min-velocidad", type=int, default=50,
                        help="URLs/min bajo las cuales detenerse (default: 50)")
    parser.add_argument("--min-ventanas", type=int, default=6,
                        help="ventanas de 10s de rendimiento bajo antes de "
                             "detenerse (default: 6)")
    parser.add_argument("--js", action="store_true",
                        help="renderizar con Selenium (lento; default: estático)")
    args = parser.parse_args()
    main(workers=args.workers, lote=args.lote, iters=args.iters,
         noRobots=args.no_robots, pausaHost=args.pausa_host,
         fallosFrio=args.fallos_frio, minVelocidad=args.min_velocidad,
         minVentanas=args.min_ventanas, usarJS=args.js)