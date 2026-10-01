package ritec;

import java.util.ArrayList;
import java.util.Collections;
import java.util.HashSet;
import java.util.List;
import java.util.Set;
import java.util.concurrent.BlockingQueue;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.LinkedBlockingQueue;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicBoolean;
import java.util.concurrent.atomic.AtomicInteger;
import java.util.concurrent.atomic.AtomicLong;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

public final class Crawler {

    private static final Logger logger = LoggerFactory.getLogger(Crawler.class);

    private static final int MAX_POR_LOTE = 1000;
    private static final int NUM_ITERS = 40;
    private static final int TAMANO_PISCINA = 5000;

    public static void main(String[] args) {
        int workers = 128;
        int lote = MAX_POR_LOTE;
        int iters = NUM_ITERS;
        boolean noRobots = false;
        int minVelocidad = 50;
        int minVentanas = 6;
        int fallosFrio = 3;
        long pausaHost = 250;

        for (int i = 0; i < args.length; i++) {
            switch (args[i]) {
                case "--workers" -> workers = Integer.parseInt(args[++i]);
                case "--lote" -> lote = Integer.parseInt(args[++i]);
                case "--iters" -> iters = Integer.parseInt(args[++i]);
                case "--no-robots" -> noRobots = true;
                case "--min-velocidad" -> minVelocidad = Integer.parseInt(args[++i]);
                case "--min-ventanas" -> minVentanas = Integer.parseInt(args[++i]);
                case "--fallos-frio" -> fallosFrio = Integer.parseInt(args[++i]);
                case "--pausa-host" -> pausaHost = Long.parseLong(args[++i]);
                default -> {
                    System.err.println("Argumento desconocido: " + args[i]);
                    System.exit(1);
                }
            }
        }

        final int workersArg = workers;
        final int loteArg = lote;
        final int itersArg = iters;
        final boolean noRobotsArg = noRobots;
        final int minVelocidadArg = minVelocidad;
        final int minVentanasArg = minVentanas;
        final int fallosFrioArg = fallosFrio;
        final long pausaHostArg = pausaHost;

        AtomicBoolean detener = new AtomicBoolean(false);
        Runtime.getRuntime().addShutdownHook(new Thread(() -> {
            logger.info("Apagado solicitado: cerrando BD y checkpoint del WAL...");
            detener.set(true);
            Db.cerrar();
            Db.puntoControl();
            logger.info("Apagado limpio");
        }, "apagado"));

        Parser.cargarDominiosBloqueados("assets/Bloqueados0.txt");
        Db.inicializar();
        Db.iniciarEscritor();
        Db.iniciarMantenimiento();

        Fetcher fetcher = new Fetcher();
        Robots robots = new Robots(fetcher, !noRobotsArg);
        Politencia politencia = new Politencia(pausaHostArg);

        Set<Parser.Link> frontera = ConcurrentHashMap.newKeySet();
        BlockingQueue<String> cola = new LinkedBlockingQueue<>(Math.max(4096, loteArg * 2));
        AtomicLong reclamadas = new AtomicLong();
        AtomicLong bytesEscritos = new AtomicLong();
        AtomicLong contadorProcesadas = new AtomicLong();
        ConcurrentHashMap<String, AtomicInteger> fallosHost = new ConcurrentHashMap<>();
        AtomicBoolean productorListo = new AtomicBoolean(false);
        AtomicInteger enProceso = new AtomicInteger();
        long presupuesto = itersArg == 0 ? Long.MAX_VALUE : (long) itersArg * loteArg;

        Thread productor = new Thread(() -> {
            List<String> piscina = new ArrayList<>();
            int vaciosConsecutivos = 0;
            try {
                while (reclamadas.get() < presupuesto && !detener.get()) {
                    if (piscina.isEmpty()) {
                        int falta = (int) Math.min(TAMANO_PISCINA, presupuesto - reclamadas.get());
                        piscina.addAll(Db.reclamarLote(falta));
                        if (piscina.isEmpty()) {
                            vaciosConsecutivos++;
                            if (vaciosConsecutivos >= 15) break;
                            Thread.sleep(2000);
                            continue;
                        }
                        vaciosConsecutivos = 0;
                        Collections.shuffle(piscina);
                    }
                    int aEncolar = Math.min(loteArg, piscina.size());
                    List<String> loteEncolado = new ArrayList<>(piscina.subList(0, aEncolar));
                    piscina.subList(0, aEncolar).clear();
                    reclamadas.addAndGet(loteEncolado.size());
                    for (String u : loteEncolado) cola.put(u);
                    logger.info("Lote: {} URLs en cola", loteEncolado.size());
                }
            } catch (InterruptedException e) {
                Thread.currentThread().interrupt();
            } finally {
                productorListo.set(true);
            }
        }, "productor");

        Runnable trabajador = () -> {
            try {
                while (true) {
                    String url = cola.poll(250, TimeUnit.MILLISECONDS);
                    if (url == null) {
                        if (productorListo.get() && enProceso.get() == 0) break;
                        continue;
                    }
                    enProceso.incrementAndGet();
                    try {
                        procesarURL(url, fetcher, robots, politencia, frontera,
                                bytesEscritos, contadorProcesadas, fallosHost,
                                fallosFrioArg);
                    } finally {
                        enProceso.decrementAndGet();
                    }
                }
            } catch (InterruptedException e) {
                Thread.currentThread().interrupt();
            }
        };

        Thread registrador = new Thread(() -> {
            while (!detener.get()) {
                try {
                    Thread.sleep(2000);
                } catch (InterruptedException e) {
                    break;
                }
                if (!frontera.isEmpty()) vaciarFrontera(frontera);
            }
            vaciarFrontera(frontera);
        }, "registrador");

        Thread estadisticas = new Thread(() -> {
            long[] ventana = {System.nanoTime(), 0, 0};
            int ventanasTotales = 0;
            int ventanasBajas = 0;
            while (!detener.get()) {
                try {
                    Thread.sleep(10_000);
                } catch (InterruptedException e) {
                    break;
                }
                long ahora = System.nanoTime();
                long bytes = bytesEscritos.get();
                long procesadas = contadorProcesadas.get();
                double seg = (ahora - ventana[0]) / 1e9;
                double mbs = (bytes - ventana[1]) / (1024.0 * 1024.0) / Math.max(seg, 0.001);
                double urlsMin = (procesadas - ventana[2]) / Math.max(seg, 0.001) * 60.0;
                logger.info("[EST] {} MB/s, {} URLs/min, {} MB total, {} URLs",
                        String.format("%.2f", mbs),
                        String.format("%.0f", urlsMin),
                        String.format("%.2f", bytes / (1024.0 * 1024.0)),
                        procesadas);
                ventanasTotales++;
                if (ventanasTotales >= minVentanasArg) {
                    if (urlsMin < minVelocidadArg) {
                        ventanasBajas++;
                        if (ventanasBajas >= minVentanasArg) {
                            logger.info("Rendimiento bajo ({} URLs/min, {} MB/s) durante {} ventanas, deteniéndose...",
                                    String.format("%.0f", urlsMin),
                                    String.format("%.2f", mbs),
                                    ventanasBajas);
                            detener.set(true);
                        }
                    } else {
                        ventanasBajas = 0;
                    }
                }
                ventana[0] = ahora;
                ventana[1] = bytes;
                ventana[2] = procesadas;
            }
        }, "estadisticas");
        estadisticas.setDaemon(true);

        registrador.start();
        estadisticas.start();
        ExecutorService ejecutor = Executors.newVirtualThreadPerTaskExecutor();
        for (int n = 0; n < workersArg; n++) ejecutor.submit(trabajador);
        productor.start();

        try {
            productor.join();
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
        }
        ejecutor.close();
        detener.set(true);
        try {
            registrador.join();
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
        }
        Db.cerrar();
        logger.info("Arañado terminado ({} URLs reclamadas)", reclamadas.get());
    }

    private static void procesarURL(String url, Fetcher fetcher, Robots robots,
                                    Politencia politencia, Set<Parser.Link> frontera,
                                    AtomicLong bytesEscritos, AtomicLong contadorProcesadas,
                                    ConcurrentHashMap<String, AtomicInteger> fallosHost,
                                    int umbralFrio) {
        String titulo = null;
        Integer codigoEstado = null;
        try {
            String host = Parser.hostRaiz(url);
            AtomicInteger fallos = fallosHost.get(host);
            if (fallos != null && fallos.get() >= umbralFrio) {
                logger.info("[HOST-FRIO] {}: host con {} errores seguidos, descartado",
                        host, fallos.get());
                return;
            }
            if (!Parser.esURLUtil(url)) {
                logger.info("[BLOQUEO] {}: descartado (dominio o ruta bloqueada)", url);
                return;
            }
            if (!robots.esPermitido(url)) {
                logger.info("[ROBOTS] {}: descartado por robots.txt", url);
                return;
            }
            politencia.esperar(host);
            logger.info("Descargando: {}", url);
            Fetcher.Result r = fetcher.fetch(url);
            codigoEstado = r.statusCode();
            if (esFalloHost(codigoEstado)) {
                int n = fallosHost.computeIfAbsent(host, h -> new AtomicInteger())
                        .incrementAndGet();
                if (n >= umbralFrio) {
                    logger.info("[HOST-FRIO] {}: alcanzado {} errores, se descartará",
                            host, n);
                }
            } else {
                fallosHost.remove(host);
            }
            if (r.html().isEmpty()) return;
            Parser.ParseResult pr = Parser.parsearPagina(r.html(), url);
            titulo = pr.titulo();
            int p = Parser.puntajeRelevancia(pr.texto());
            if (p < Parser.MIN_RELEVANCIA) {
                logger.info("[PUNT] {}: relevancia {} < {}, sin texto",
                        url, p, Parser.MIN_RELEVANCIA);
                return;
            }
            logger.info("[PUNT] {}: relevancia {}", url, p);
            bytesEscritos.addAndGet(Parser.guardarTexto(pr.texto(), url));
            frontera.addAll(pr.links());
        } catch (Exception e) {
            logger.error("Error al procesar {}: {}", url, e.toString());
        } finally {
            contadorProcesadas.incrementAndGet();
            Db.guardarResultado(url, titulo, codigoEstado);
        }
    }

    private static boolean esFalloHost(Integer codigo) {
        if (codigo == null) return true;
        return codigo == 403 || codigo == 429 || codigo >= 500;
    }

    private static void vaciarFrontera(Set<Parser.Link> frontera) {
        Set<Parser.Link> instantanea = new HashSet<>(frontera);
        frontera.removeAll(instantanea);
        if (instantanea.isEmpty()) return;
        List<String> urls = new ArrayList<>(instantanea.size());
        for (Parser.Link l : instantanea) urls.add(l.url());
        int nuevos = Db.registrarUrls(urls);
        logger.info("Frontera: {} enlaces, {} URLs nuevas", urls.size(), nuevos);
    }
}