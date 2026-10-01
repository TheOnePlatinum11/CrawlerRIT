package ritec;

import java.nio.charset.StandardCharsets;
import java.util.List;
import java.util.concurrent.ConcurrentHashMap;

import crawlercommons.robots.BaseRobotRules;
import crawlercommons.robots.SimpleRobotRules;
import crawlercommons.robots.SimpleRobotRulesParser;

public final class Robots {

    private final Fetcher fetcher;
    private final boolean habilitado;
    private final ConcurrentHashMap<String, BaseRobotRules> cache = new ConcurrentHashMap<>();
    private final SimpleRobotRulesParser parser = new SimpleRobotRulesParser();

    public Robots(Fetcher fetcher, boolean habilitado) {
        this.fetcher = fetcher;
        this.habilitado = habilitado;
    }

    public boolean esPermitido(String url) {
        if (!habilitado) return true;
        String host = Parser.hostRaiz(url);
        BaseRobotRules reglas = cache.computeIfAbsent(host, this::cargar);
        return reglas == null || reglas.isAllowed(url);
    }

    private BaseRobotRules cargar(String host) {
        for (String esquema : List.of("https", "http")) {
            Fetcher.Result r = fetcher.fetch(esquema + "://" + host + "/robots.txt");
            if (r.statusCode() == null) continue;
            if (r.statusCode() == 404) return new SimpleRobotRules();
            if (r.statusCode() == 200) {
                byte[] contenido = r.html().getBytes(StandardCharsets.UTF_8);
                return parser.parseContent(host, contenido, "text/plain", Fetcher.USER_AGENT);
            }
        }
        return new SimpleRobotRules();
    }
}