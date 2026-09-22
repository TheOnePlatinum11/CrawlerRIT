import linkHelpers

def main():
    urls = linkHelpers.leerURLs("assets/URLs.txt")
    for url in urls:
        html = linkHelpers.descargarHTML(url)
        links = linkHelpers.detectarLinks(html)
        linkHelpers.guardarLinks(links)

if __name__ == "__main__":
    explorados = linkHelpers.leerURLs("assets/URLsExplorados.txt")
    main()