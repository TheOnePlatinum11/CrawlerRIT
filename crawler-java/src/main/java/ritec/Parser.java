package ritec;

import java.io.File;
import java.io.FileWriter;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.text.Normalizer;
import java.util.ArrayList;
import java.util.HashSet;
import java.util.List;
import java.util.Locale;
import java.util.Set;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

import org.jsoup.Jsoup;
import org.jsoup.nodes.Document;
import org.jsoup.nodes.Element;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

public final class Parser {

    public static final int MIN_RELEVANCIA = 4;

    private static final Logger logger = LoggerFactory.getLogger(Parser.class);

    public record Link(String url, String ancla) {}

    public record ParseResult(String titulo, String texto, Set<Link> links) {}

    private static final Pattern EXCLUSIONES_URL = Pattern.compile(
            "(/login|/signup|/logout|/register|/cart|/checkout|/account|/privacy|"
            + "/terms|/password|/search|/archive\\.php|\\.(jpg|jpeg|png|gif|svg|webp|ico|"
            + "mp4|avi|mov|webm|mp3|wav|zip|tar|gz|exe|pdf|css|js|woff2?|ttf)\\b)",
            Pattern.CASE_INSENSITIVE);

    private static final Pattern TERMINOS_RELEVANTES = Pattern.compile(
            "\\b(intervenci\\w+|intervencionismo|intervent\\w+|intervenç\\w+|"
            + "golpe de estado|golpe militar|invas\\w+|invad\\w+|ocupaci\\w+|"
            + "occupi\\w+|occupied|embargo|bloqueo|blockade|sanctions?|sanciones|"
            + "dictadur\\w+|dictatorship|dictador|guerra fr\\w*|cold war|"
            + "doctrina monroe|monroe doctrine|doutrina monroe|operaci.n c.nd|"
            + "operation condor|c.ndor|condor|misil\\w+|missiles?|crisis de los misiles|"
            + "missile crisis|bah.a de cochinos|bay of pigs|latinoam\\w+|latin america|"
            + "latin american|america latina|centroam\\w+|central america|south america|"
            + "estados unidos|united states|estadounid\\w+|norteamerican\\w+|imperial\\w+|"
            + "imperialism|hegemon\\w+|hegemony|revoluci\\w+|revoluç\\w+|revolut\\w+|"
            + "guerrilla|sandinista|contrainsurgencia|contras?|somoza|pinochet|"
            + "allende|castro|arbenz|torrijos|noriega|batista|trujillo|represi\\w+|"
            + "repression|desclasific\\w+|injerencia|interference|yanqui|diplomaci\\w+|"
            + "diplomatic|canal de panama|espionaje|espionage|subvers\\w+|subversion|"
            + "guerra sucia|regime change|cambio de regimen|covert|destabiliz\\w+|"
            + "proxy war|guerra por poderes|drug war|guantanam\\w+|chile|argentina|cuba|"
            + "nicaragua|guatemala|panama|honduras|el salvador|mexic\\w+|colombia|"
            + "venezuela|peru|bolivia|uruguay|paraguay|brasil\\w+|brazil|puerto rico|"
            + "haiti|granada|grenada|republica dominicana|república dominicana|"
            + "dominican republic|the caribbean|caribe)\\b",
            Pattern.CASE_INSENSITIVE | Pattern.UNICODE_CHARACTER_CLASS);

    private static final Pattern PARAMETROS_BASURA = Pattern.compile(
            "^(utm_|fbclid|gclid|mc_|ref_|via_|hs_|spm_).*", Pattern.CASE_INSENSITIVE);

    private static final int MIN_HTML_PARSE = 2000;

    private static final String[] PISTAS_RAPIDAS = {
            "guerra", "cuba", "chile", "intervenci", "estados unidos", "revoluci",
            "dictadur", "golpe de estado", "regimen", "embargo", "pinochet", "condor",
            "mexic", "nicaragua", "guatemala", "argentina", "colombia", "venezuela",
            "latinoam", "america latina", "united states", "imperial", "sandinista",
            "castro", "allende", "panama", "honduras", "peru", "bolivia", "brasil",
            "haiti", "caribe", "guerrilla", "dictatorship", "intervent", "invas",
            "invad", "ocupaci", "occupi", "blockade", "sanction", "sanciones",
            "dictador", "guerra fr", "cold war", "doctrina monroe", "monroe doctrine",
            "operaci", "operation condor", "misil", "missile", "crisis de los misiles",
            "missile crisis", "bah", "bay of pigs", "latin america", "latin american",
            "centroam", "central america", "south america", "estadounid", "norteamerican",
            "imperialism", "hegemon", "hegemony", "revoluç", "revolut", "contrainsurgencia",
            "contra", "somoza", "arbenz", "torrijos", "noriega", "batista", "trujillo",
            "represi", "repression", "desclasific", "injerencia", "interference",
            "yanqui", "diplomaci", "diplomatic", "canal de panama", "espionaje",
            "espionage", "subvers", "subversion", "guerra sucia", "regime change",
            "cambio de regimen", "covert", "destabiliz", "proxy war", "guerra por poderes",
            "drug war", "guantanam", "el salvador", "puerto rico", "granada", "grenada",
            "republica dominicana", "república dominicana", "dominican republic",
            "the caribbean", "intervencionismo", "intervenç", "occupied", "bloqueo",
            "doutrina monroe", "uruguay", "paraguay", "brazil",
    };

    private static volatile Set<String> dominiosBloqueados = Set.of();

    private Parser() {}

    public static void cargarDominiosBloqueados(String ruta) {
        Set<String> dominios = new HashSet<>();
        File archivo = new File(ruta);
        if (archivo.exists()) {
            try {
                for (String linea : Files.readAllLines(archivo.toPath(), StandardCharsets.UTF_8)) {
                    String d = linea.split("#", 2)[0].trim().toLowerCase();
                    if (!d.isEmpty()) dominios.add(d);
                }
            } catch (IOException e) {
                throw new RuntimeException("No se pudo leer " + ruta, e);
            }
        }
        dominiosBloqueados = dominios;
        if (!dominios.isEmpty()) {
            logger.info("Dominios bloqueados ({}): {}",
                    dominios.size(), dominios.stream().sorted().toList());
        } else {
            logger.warn("Sin lista de dominios bloqueados: {} no existe", ruta);
        }
    }

    public static boolean hostPermitido(String host) {
        for (String b : dominiosBloqueados) {
            if (host.equals(b) || host.endsWith("." + b)) return false;
        }
        return true;
    }

    public static String netloc(String url) {
        int i = url.indexOf("://");
        if (i < 0) return "";
        String resto = url.substring(i + 3);
        int slash = resto.indexOf('/');
        String autoridad = slash < 0 ? resto : resto.substring(0, slash);
        int arroba = autoridad.lastIndexOf('@');
        if (arroba >= 0) autoridad = autoridad.substring(arroba + 1);
        return autoridad;
    }

    public static String hostRaiz(String url) {
        String h = netloc(url).toLowerCase();
        int dosPuntos = h.indexOf(':');
        if (dosPuntos >= 0) h = h.substring(0, dosPuntos);
        return h.startsWith("www.") ? h.substring(4) : h;
    }

    public static boolean esURLUtil(String url) {
        String host = netloc(url);
        if (host.isEmpty()) return false;
        if (!hostPermitido(hostRaiz(url))) return false;
        return !EXCLUSIONES_URL.matcher(url).find();
    }

    public static String normalizarURL(String url) {
        String s = url;
        int fragmento = s.indexOf('#');
        if (fragmento >= 0) s = s.substring(0, fragmento);
        int finEsquema = s.indexOf("://");
        if (finEsquema < 0) return "";
        String esquema = s.substring(0, finEsquema).toLowerCase();
        if (!esquema.equals("http") && !esquema.equals("https")) return "";
        String resto = s.substring(finEsquema + 3);
        int inicioRuta = resto.indexOf('/');
        String autoridad = inicioRuta < 0 ? resto : resto.substring(0, inicioRuta);
        String rutaConsulta = inicioRuta < 0 ? "" : resto.substring(inicioRuta);
        int q = rutaConsulta.indexOf('?');
        String ruta = q < 0 ? rutaConsulta : rutaConsulta.substring(0, q);
        String consulta = q < 0 ? "" : rutaConsulta.substring(q + 1);
        List<String> conservados = new ArrayList<>();
        if (!consulta.isEmpty()) {
            for (String p : consulta.split("&")) {
                if (p.isEmpty()) continue;
                String clave = p.split("=", 2)[0];
                if (!PARAMETROS_BASURA.matcher(clave).matches()) conservados.add(p);
            }
        }
        String nuevaConsulta = String.join("&", conservados);
        StringBuilder sb = new StringBuilder(esquema).append("://").append(autoridad).append(ruta);
        if (!nuevaConsulta.isEmpty()) sb.append('?').append(nuevaConsulta);
        String reconstruida = sb.toString();
        if (consulta.isEmpty() && ruta.endsWith("/") && !ruta.equals("/")) {
            int base = esquema.length() + 3 + autoridad.length();
            while (reconstruida.length() > base && reconstruida.endsWith("/")) {
                reconstruida = reconstruida.substring(0, reconstruida.length() - 1);
            }
        }
        return reconstruida;
    }

    public static int puntajeRelevancia(String texto) {
        if (texto == null || texto.isEmpty()) return 0;
        if (!tienePistas(texto)) return 0;
        Set<String> encontrados = new HashSet<>();
        Matcher m = TERMINOS_RELEVANTES.matcher(texto);
        while (m.find()) encontrados.add(m.group());
        return encontrados.size();
    }

    private static boolean tienePistas(String texto) {
        String bajo = texto.toLowerCase(Locale.ROOT);
        for (String p : PISTAS_RAPIDAS) {
            if (bajo.indexOf(p) >= 0) return true;
        }
        return false;
    }

    public static ParseResult parsearPagina(String html, String urlBase) {
        if (html == null || html.length() < MIN_HTML_PARSE) {
            return new ParseResult("", "", Set.of());
        }
        Document doc = Jsoup.parse(html, urlBase);
        doc.select("script, style").remove();
        String texto = doc.text();
        Set<Link> links = new HashSet<>();
        for (Element a : doc.select("a[href]")) {
            String href = a.attr("abs:href");
            if (href.isEmpty()) href = a.attr("href");
            String n = normalizarURL(href);
            if (!n.isEmpty() && esURLUtil(n)) {
                links.add(new Link(n, ""));
            }
        }
        return new ParseResult(doc.title(), texto, links);
    }

    public static String cortarTexto(String texto) {
        if (texto == null) return "";
        String norm = Normalizer.normalize(texto, Normalizer.Form.NFD);
        StringBuilder sb = new StringBuilder(norm.length());
        boolean enPalabra = false;
        for (int i = 0; i < norm.length(); i++) {
            char c = norm.charAt(i);
            if (Character.isLetterOrDigit(c)) {
                sb.append(Character.toLowerCase(c));
                enPalabra = true;
            } else if (c == '/' || c == '-' || c == '_' || Character.isWhitespace(c)) {
                if (enPalabra) {
                    sb.append(' ');
                    enPalabra = false;
                }
            }
        }
        return sb.toString();
    }

    private static boolean dirPreparado = false;

    public static int guardarTexto(String texto, String url) {
        if (url == null || url.isEmpty()) return 0;
        if (!dirPreparado) {
            new File("HTMLs").mkdirs();
            dirPreparado = true;
        }
        String nombre = url.replaceAll("[<>:\"/\\\\|?*]", "_");
        if (nombre.length() > 180) nombre = nombre.substring(0, 180);
        String contenido = cortarTexto(texto);
        try (FileWriter fw = new FileWriter(new File("HTMLs", nombre + ".txt"), StandardCharsets.UTF_8)) {
            fw.write(contenido);
            return contenido.getBytes(StandardCharsets.UTF_8).length;
        } catch (IOException e) {
            logger.error("Error al guardar texto de {}: {}", url, e.toString());
            return 0;
        }
    }
}