package ritec;

import java.io.File;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.sql.Connection;
import java.sql.DriverManager;
import java.sql.PreparedStatement;
import java.sql.ResultSet;
import java.sql.SQLException;
import java.sql.Statement;
import java.time.ZoneOffset;
import java.time.ZonedDateTime;
import java.time.format.DateTimeFormatter;
import java.util.ArrayList;
import java.util.Collection;
import java.util.Collections;
import java.util.HashSet;
import java.util.List;
import java.util.Set;
import java.util.concurrent.LinkedBlockingQueue;
import java.util.concurrent.TimeUnit;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

public final class Db {

    private static final Logger logger = LoggerFactory.getLogger(Db.class);

    private static final String RUTA = "crawler.db";
    private static final String SEMILLAS = "assets/URLs0.txt";
    private static final int LOTE_ESCRITURA = 2000;
    private static final long MAX_WAL_BYTES = 8L * 1024 * 1024;
    private static final DateTimeFormatter FECHA = DateTimeFormatter
            .ofPattern("yyyy-MM-dd'T'HH:mm:ss'Z'").withZone(ZoneOffset.UTC);

    private static final Object lockReclamo = new Object();
    private static final LinkedBlockingQueue<Object[]> colaResultados = new LinkedBlockingQueue<>();
    private static volatile boolean cerrado = false;
    private static Thread escritor;

    private Db() {}

    public static void inicializar() {
        long walInicial = tamanoWAL();
        try (Connection c = abrir()) {
            try (Statement st = c.createStatement()) {
                if (walInicial > 0) {
                    logger.info("Punto de control del WAL ({} MB)...",
                            walInicial / (1024 * 1024));
                }
                st.execute("PRAGMA busy_timeout = 2000");
                st.execute("PRAGMA wal_checkpoint(TRUNCATE)");
                long walFinal = tamanoWAL();
                if (walFinal != walInicial) {
                    logger.info("Punto de control completo (WAL ahora {} MB)",
                            walFinal / (1024 * 1024));
                }
                st.execute("CREATE TABLE IF NOT EXISTS paginas ("
                        + "id INTEGER PRIMARY KEY AUTOINCREMENT,"
                        + "url TEXT NOT NULL UNIQUE,"
                        + "titulo TEXT,"
                        + "codigo_estado INTEGER,"
                        + "scrapeada INTEGER NOT NULL DEFAULT 0 CHECK (scrapeada IN (0, 1)),"
                        + "fecha_visita TEXT)");
                st.execute("CREATE INDEX IF NOT EXISTS idx_paginas_pendientes ON paginas (scrapeada, id)");
                if (!tieneColumna(c, "reservada")) {
                    st.execute("ALTER TABLE paginas ADD COLUMN reservada INTEGER NOT NULL DEFAULT 0");
                    logger.info("Columna 'reservada' agregada a paginas");
                }
                try (ResultSet rs = st.executeQuery(
                        "SELECT 1 FROM paginas WHERE scrapeada = 0 AND reservada = 1 LIMIT 1")) {
                    if (rs.next()) {
                        int reclamadas = 0;
                        while (true) {
                            int n = st.executeUpdate(
                                    "UPDATE paginas SET reservada = 0 WHERE id IN ("
                                    + "SELECT id FROM paginas WHERE scrapeada = 0 AND reservada = 1 "
                                    + "LIMIT 10000)");
                            reclamadas += n;
                            if (n == 0) break;
                        }
                        logger.info("Reclamadas {} filas reservadas de una ejecución anterior",
                                reclamadas);
                    }
                }
            }
            sembrar(c);
        } catch (SQLException e) {
            throw new RuntimeException("No se pudo inicializar la BD", e);
        }
    }

    public static List<String> reclamarLote(int limite) {
        if (limite <= 0) return List.of();
        synchronized (lockReclamo) {
            try (Connection c = abrir();
                 PreparedStatement ps = c.prepareStatement(
                         "UPDATE paginas SET reservada = 1 WHERE id IN ("
                         + "SELECT id FROM paginas WHERE scrapeada = 0 AND reservada = 0 "
                         + "ORDER BY RANDOM() LIMIT ?) RETURNING url")) {
                ps.setInt(1, limite);
                List<String> urls = new ArrayList<>();
                if (ps.execute()) {
                    try (ResultSet rs = ps.getResultSet()) {
                        while (rs.next()) urls.add(rs.getString(1));
                    }
                }
                return urls;
            } catch (SQLException e) {
                throw new RuntimeException(e);
            }
        }
    }

    public static int registrarUrls(Collection<String> urls) {
        Set<String> vistos = new HashSet<>();
        List<String> normalizadas = new ArrayList<>();
        for (String u : urls) {
            if (!u.isEmpty() && vistos.add(u)) normalizadas.add(u);
        }
        if (normalizadas.isEmpty()) return 0;
        int nuevos = 0;
        try (Connection c = abrir()) {
            for (int i = 0; i < normalizadas.size(); i += 500) {
                List<String> chunk = normalizadas.subList(i, Math.min(i + 500, normalizadas.size()));
                String marca = String.join(",", Collections.nCopies(chunk.size(), "(?)"));
                try (PreparedStatement ps = c.prepareStatement(
                        "INSERT OR IGNORE INTO paginas (url) VALUES " + marca)) {
                    for (int j = 0; j < chunk.size(); j++) ps.setString(j + 1, chunk.get(j));
                    nuevos += ps.executeUpdate();
                }
            }
            return nuevos;
        } catch (SQLException e) {
            logger.error("Error al registrar URLs en la BD", e);
            return 0;
        }
    }

    public static void guardarResultado(String url, String titulo, Integer codigoEstado) {
        String normalizada = Parser.normalizarURL(url);
        if (normalizada.isEmpty()) return;
        String fecha = FECHA.format(ZonedDateTime.now(ZoneOffset.UTC));
        colaResultados.offer(new Object[]{normalizada, titulo, codigoEstado, fecha});
    }

    public static void iniciarEscritor() {
        escritor = new Thread(Db::bucleEscritor, "escritor-bd");
        escritor.setDaemon(true);
        escritor.start();
    }

    public static void iniciarMantenimiento() {
        Thread t = new Thread(Db::bucleMantenimiento, "mantenimiento-wal");
        t.setDaemon(true);
        t.start();
    }

    public static void cerrar() {
        cerrado = true;
        Thread t = escritor;
        if (t != null) {
            try {
                t.join(5000);
            } catch (InterruptedException e) {
                Thread.currentThread().interrupt();
            }
        }
    }

    public static void puntoControl() {
        try (Connection c = abrir();
             Statement st = c.createStatement()) {
            st.execute("PRAGMA busy_timeout = 2000");
            st.execute("PRAGMA wal_checkpoint(TRUNCATE)");
        } catch (SQLException e) {
            logger.error("Checkpoint del WAL fallido", e);
        }
    }

    private static void bucleMantenimiento() {
        while (!cerrado) {
            try {
                Thread.sleep(5000);
            } catch (InterruptedException e) {
                Thread.currentThread().interrupt();
                break;
            }
            long wal = tamanoWAL();
            if (wal == 0) continue;
            boolean grande = wal > MAX_WAL_BYTES;
            try (Connection c = abrir();
                 Statement st = c.createStatement()) {
                st.execute("PRAGMA busy_timeout = 10000");
                try (ResultSet rs = st.executeQuery(grande
                        ? "PRAGMA wal_checkpoint(TRUNCATE)"
                        : "PRAGMA wal_checkpoint(PASSIVE)")) {
                    if (grande && rs.next() && rs.getInt(1) == 0) {
                        logger.info("Mantenimiento: WAL {} MB truncado",
                                wal / (1024 * 1024));
                    }
                }
            } catch (SQLException e) {
                logger.error("Error en mantenimiento del WAL", e);
            }
        }
    }

    private static void bucleEscritor() {
        try (Connection c = abrir()) {
            c.setAutoCommit(false);
            List<Object[]> lote = new ArrayList<>();
            while (!cerrado || !colaResultados.isEmpty()) {
                Object[] fila = colaResultados.poll(500, TimeUnit.MILLISECONDS);
                if (fila != null) lote.add(fila);
                if (lote.size() >= LOTE_ESCRITURA) {
                    escribirLote(c, lote);
                    lote.clear();
                }
            }
            if (!lote.isEmpty()) escribirLote(c, lote);
            c.commit();
        } catch (Exception e) {
            logger.error("Error en el hilo escritor de la BD", e);
        }
    }

    private static void escribirLote(Connection c, List<Object[]> lote) throws SQLException {
        try (PreparedStatement ps = c.prepareStatement(
                "UPDATE paginas SET titulo = ?, codigo_estado = ?, scrapeada = 1, reservada = 0, fecha_visita = ? WHERE url = ?")) {
            for (Object[] fila : lote) {
                ps.setString(1, (String) fila[1]);
                ps.setObject(2, fila[2]);
                ps.setString(3, (String) fila[3]);
                ps.setString(4, (String) fila[0]);
                ps.addBatch();
            }
            ps.executeBatch();
            c.commit();
        }
    }

    private static void sembrar(Connection c) throws SQLException {
        File archivo = new File(SEMILLAS);
        if (!archivo.exists()) return;
        try {
            List<String> semillas = new ArrayList<>();
            for (String linea : Files.readAllLines(archivo.toPath(), StandardCharsets.UTF_8)) {
                String u = Parser.normalizarURL(linea.strip());
                if (!u.isEmpty()) semillas.add(u);
            }
            if (semillas.isEmpty()) return;
            try (PreparedStatement ps = c.prepareStatement(
                    "INSERT OR IGNORE INTO paginas (url) VALUES (?)")) {
                for (String u : semillas) {
                    ps.setString(1, u);
                    ps.addBatch();
                }
                ps.executeBatch();
            }
            logger.info("Semillas cargadas desde {}", SEMILLAS);
        } catch (IOException e) {
            logger.warn("No se pudo leer {}", SEMILLAS, e);
        }
    }

    private static boolean tieneColumna(Connection c, String nombre) throws SQLException {
        try (Statement st = c.createStatement();
             ResultSet rs = st.executeQuery("PRAGMA table_info(paginas)")) {
            while (rs.next()) {
                if (nombre.equals(rs.getString("name"))) return true;
            }
        }
        return false;
    }

    private static long tamanoWAL() {
        File wal = new File("crawler.db-wal");
        return wal.exists() ? wal.length() : 0;
    }

    private static Connection abrir() throws SQLException {
        Connection c = DriverManager.getConnection("jdbc:sqlite:" + RUTA);
        try (Statement st = c.createStatement()) {
            st.execute("PRAGMA journal_mode = WAL");
            st.execute("PRAGMA busy_timeout = 30000");
            st.execute("PRAGMA synchronous = NORMAL");
            st.execute("PRAGMA wal_autocheckpoint = 1000");
        }
        return c;
    }
}