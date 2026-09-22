from linkHelpers import NUM_ITERS, leerURLs, descargarHTML, depurarLinks, detectarLinks, guardarLinks

def main():
    i = 0
    while i < NUM_ITERS:
      urls = leerURLs(f"assets/URLs{i}.txt")
      for url in urls:
          html = descargarHTML(url, i)
          links = detectarLinks(html, i)
          guardarLinks(links, str(i + 1))
      input(f"Iteración {i} terminada")
      i += 1

if __name__ == "__main__":
    main()
    depurarLinks()