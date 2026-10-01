package ritec;

import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.locks.LockSupport;

public final class Politencia {

    private final long gapNanos;
    private final ConcurrentHashMap<String, Long> ultimoAcceso = new ConcurrentHashMap<>();
    private final Object lock = new Object();

    public Politencia(long gapMillis) {
        this.gapNanos = gapMillis * 1_000_000L;
    }

    public void esperar(String host) {
        if (gapNanos <= 0) return;
        long ahora = System.nanoTime();
        long espera;
        synchronized (lock) {
            Long prev = ultimoAcceso.get(host);
            if (prev == null) {
                ultimoAcceso.put(host, ahora + gapNanos);
                espera = 0;
            } else {
                long disponible = Math.max(prev, ahora) + gapNanos;
                ultimoAcceso.put(host, disponible);
                espera = disponible - ahora;
            }
        }
        if (espera > 0) LockSupport.parkNanos(espera);
    }
}