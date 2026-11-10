from fotos_tiny import web
from fotos_tiny.maldaner import escolher_cartao, sem_repetidas, url_original


def test_url_original_da_miniatura():
    mini = ("https://thumbnails.meuspedidos.com.br/rs:fit:300/plain/"
            "https://arquivos.mercos.com/media/imagem_produto/288305/abc.png")
    assert url_original(mini) == "https://arquivos.mercos.com/media/imagem_produto/288305/abc.png"
    assert url_original("https://outro/x.png") == "https://outro/x.png"


def test_sem_repetidas_mantem_ordem():
    assert sem_repetidas(["a", "b", "a", "c", "b"]) == ["a", "b", "c"]


def test_escolher_cartao():
    titulos = ["Cabo USB 3m GB51269", "Cabo Tipo-C 1M GB51267", "Fone HS-107"]
    assert escolher_cartao("GB51267", "Cabo Tipo-C | 1M - MBTECH GB51267", titulos) == 1
    assert escolher_cartao("HS-107", "Fone de ouvido - HS-107", titulos) == 2
    assert escolher_cartao("ZZ999", "Cabo ZZ999", titulos) is None
    # mesmo código mas metragem diferente (Tiny 2M x site 3m) não serve
    assert escolher_cartao("GB51269", "Cabo USB 2M GB51269", titulos) is None


def resultados(*itens):
    return lambda consulta: list(itens)


def test_web_candidatas_filtra():
    r = [
        {"image": "https://loja.com/a.jpg", "title": "Cabo GB51267 1M", "url": "https://loja.com/p1"},
        {"image": "https://loja.com/a.jpg", "title": "Cabo GB51267 1M", "url": "https://loja.com/p1"},  # repetida
        {"image": "https://shutterstock.com/b.jpg", "title": "GB51267", "url": "https://shutterstock.com/x"},
        {"image": "https://maldaneracessorios.com.br/c.jpg", "title": "GB51267", "url": "https://m.com"},
        {"image": "https://loja.com/d.jpg", "title": "Cabo qualquer", "url": "https://loja.com/p4"},  # sem código
        {"image": "https://loja.com/e.jpg", "title": "Cabo GB51267 3M", "url": "https://loja.com/p5"},  # metragem
        {"image": "https://outra.com/f.jpg", "title": "GB51267 original", "url": "https://outra.com/p6"},
    ]
    urls = web.candidatas("Cabo Tipo-C | 1M - GB51267", ["GB51267"], resultados(*r))
    assert urls == ["https://loja.com/a.jpg", "https://outra.com/f.jpg"]


def test_web_busca_que_falha_nao_derruba():
    def quebra(_):
        raise RuntimeError("sem rede")
    assert web.candidatas("Cabo GB1", ["GB1"], quebra) == []


def test_web_fotos_gera_so_o_que_baixou():
    r = [
        {"image": "https://a.com/1.jpg", "title": "GB51267", "url": "https://a.com/p"},
        {"image": "https://b.com/2.jpg", "title": "GB51267", "url": "https://b.com/p"},
    ]
    baixados = {"https://b.com/2.jpg": b"bytes"}
    saida = list(web.fotos("Cabo GB51267", ["GB51267"], resultados(*r), baixados.get))
    assert saida == [("https://b.com/2.jpg", b"bytes")]


def test_consultas_sem_repetir():
    assert web.consultas("Cabo X GB1", ["GB1"]) == ["Cabo X GB1", "Cabo GB1"]
