package ritec;

import java.io.IOException;
import java.util.concurrent.TimeUnit;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import okhttp3.ConnectionPool;
import okhttp3.Dispatcher;
import okhttp3.OkHttpClient;
import okhttp3.Request;
import okhttp3.Response;
import okhttp3.ResponseBody;

public final class Fetcher {

    private static final Logger logger = LoggerFactory.getLogger(Fetcher.class);

    public static final String USER_AGENT = "BreteRIT/1.0";

    private static final long MAX_BYTES = 5L * 1024 * 1024;

    public record Result(String html, Integer statusCode) {}

    private final OkHttpClient client;

    public Fetcher() {
        Dispatcher dispatcher = new Dispatcher();
        dispatcher.setMaxRequests(512);
        dispatcher.setMaxRequestsPerHost(2);
        this.client = new OkHttpClient.Builder()
                .dispatcher(dispatcher)
                .connectTimeout(6, TimeUnit.SECONDS)
                .readTimeout(12, TimeUnit.SECONDS)
                .callTimeout(15, TimeUnit.SECONDS)
                .followRedirects(true)
                .followSslRedirects(true)
                .connectionPool(new ConnectionPool(32, 5, TimeUnit.MINUTES))
                .build();
    }

    public Result fetch(String url) {
        Request peticion = new Request.Builder()
                .url(url)
                .header("User-Agent", USER_AGENT)
                .build();
        for (int intento = 0; intento < 2; intento++) {
            try (Response respuesta = client.newCall(peticion).execute()) {
                int codigo = respuesta.code();
                if (codigo >= 500 && codigo < 600 && intento == 0) {
                    try {
                        Thread.sleep(250);
                    } catch (InterruptedException e) {
                        Thread.currentThread().interrupt();
                    }
                    continue;
                }
                if (!esHTML(respuesta) || excedeTope(respuesta)) {
                    return new Result("", codigo);
                }
                ResponseBody cuerpo = respuesta.body();
                String html = cuerpo == null ? "" : cuerpo.string();
                return new Result(html, codigo);
            } catch (IOException e) {
                logger.error("Error al descargar {} con OkHttp: {}", url, e.toString());
                return new Result("", null);
            }
        }
        return new Result("", null);
    }

    private static boolean esHTML(Response respuesta) {
        String ct = respuesta.header("Content-Type", "");
        if (ct.isBlank()) return true;
        String c = ct.toLowerCase();
        return c.contains("text/html") || c.contains("text/plain")
                || c.contains("xhtml") || c.contains("xml");
    }

    private static boolean excedeTope(Response respuesta) {
        String cl = respuesta.header("Content-Length", "");
        if (cl.isBlank()) return false;
        try {
            return Long.parseLong(cl) > MAX_BYTES;
        } catch (NumberFormatException e) {
            return false;
        }
    }
}