#!/usr/bin/env python3
# Rápido y sucio: segmentos de Nutch -> HTMLs/<url>.txt (texto procesado).
import os, re, subprocess, sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from linkHelpers import cortarTexto, puntajeRelevancia, MIN_RELEVANCIA

N, SEG, OUT = "apache-nutch-1.23", "segments", "../HTMLs"
os.makedirs(OUT, exist_ok=True)
env = {**os.environ, "JAVA_HOME": "/usr/lib/jvm/java-17-openjdk-amd64"}
vistos = set()

for seg in os.listdir(SEG):
    dump = f"/tmp/dump_{seg}"
    subprocess.run([f"{N}/bin/nutch", "readseg", "-dump", f"{SEG}/{seg}", dump], env=env)
    txt = open(f"{dump}/dump", encoding="utf-8", errors="replace").read()
    for b in re.split(r"(?m)^Recno:: ", txt)[1:]:
        u = re.search(r"URL:: (\S+)", b)
        p = re.search(r"(?ms)^ParseText::\s*(.*)", b)
        if not u or not p or u.group(1) in vistos:
            continue
        vistos.add(u.group(1))
        t = p.group(1).strip()
        if puntajeRelevancia(t) >= MIN_RELEVANCIA:
            name = re.sub(r'[<>:"/\\|?*]', "_", u.group(1))[:180] + ".txt"
            open(os.path.join(OUT, name), "w", encoding="utf-8").write(cortarTexto(t))

print("listo")