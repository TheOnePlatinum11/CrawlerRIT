# El-Desclasificador — arañador con Apache Nutch

Tercera implementación del arañador, usando **Apache Nutch 1.23**.
Nutch aporta la gestión de la frontera (CrawlDb), la cortesía por 
host (`fetcher.server.delay`), el respeto a robots.txt y el parseo de 
HTML/Texto; nosotros configuramos el enfoque temático y post-procesamos el texto.

## Requisitos

- **JDK 17**. En este equipo:
  `/usr/lib/jvm/java-17-openjdk-amd64`
- Apache Nutch 1.23 (`apache-nutch-1.23-bin.tar.gz`) descomprimido en
  `nutch/apache-nutch-1.23/` (gitignored).
- Python 3 (venv del repo) para `extract.py`.

## Reproducción

```bash
# 1. Descargar y descomprimir (una sola vez)
cd nutch
curl -LO https://dlcdn.apache.org/nutch/1.23/apache-nutch-1.23-bin.tar.gz
tar xzf apache-nutch-1.23-bin.tar.gz

# 2. Instalar la configuración en el runtime
./setup.sh

# 3. Arañar (3 rondas × 100 URLs; edita ROUNDS/TOPN en crawl.sh para cambiar)
./crawl.sh
#    todo se anota en logs/bitacora_nutch.log

# 4. Convertir los segmentos a texto plano en HTMLs/
../.venv/bin/python extract.py
```

La **bitácora del recorrido** queda en `nutch/logs/bitacora_nutch.log`
(inyección, generación, fetch y parse de cada ronda).

## Configuración aplicada (y su justificación)

| Política | Configuración | Justificación |
| :--- | :--- | :--- |
| **Identificación** | `http.agent.name = El-Desclasificador` | Transparencia ante los sitios. |
| **Cortesía por host** | `fetcher.server.delay = 1.0` | 1 petición por host por segundo; no satura prensa/archivos. |
| **robots.txt** | `http.robots.agents = El-Desclasificador,*` | Nutch respeta robots.txt por defecto. |
| **Solo texto** | `http.content.limit = 5MB` + filtro de URLs | Descarta binarios/multimedia (`.pdf`, `.jpg`, `.mp4`, …). |
| **Enfoque temático** | `regex-urlfilter.txt` (exclusiones) | Ignora login/registro/búsquedas y binarios; sigue el resto. |
| **Concurrencia** | `fetcher.threads.fetch = 50` | Descarga concurrente (I/O-bound). |
| **Frontera acotada** | `db.max.outlink.per.page = 200` | Controla el crecimiento de la frontera. |

## Salida

- `HTMLs/<url>.txt` — texto procesado con el mismo `cortarTexto` y filtro de
  relevancia que el arañador Python (repo consistente).
- `nutch/crawldb/` — metadatos del arañado (estado, score, fechas por URL).
- `nutch/logs/bitacora_nutch.log` — bitácora del recorrido.

La comparación con las otras implementaciones está en `COMPARACION.md`.