import io

from PIL import Image, ImageDraw

from fotos_tiny import imagem as im_mod


def _png(im) -> bytes:
    buf = io.BytesIO()
    im.save(buf, "PNG")
    return buf.getvalue()


def foto_com_logo(lado=800, logo_box=(30, 25, 250, 70), produto_box=(250, 300, 650, 700)):
    """Foto branca com 'logo' escura no canto superior esquerdo e um 'produto' ao centro."""
    im = Image.new("RGB", (lado, lado), (255, 255, 255))
    d = ImageDraw.Draw(im)
    if logo_box:
        d.rectangle(logo_box, fill=(20, 20, 20))
    d.ellipse(produto_box, fill=(200, 80, 30))
    return im


def logo_da_loja():
    logo = Image.new("RGBA", (400, 120), (0, 0, 0, 0))
    ImageDraw.Draw(logo).rectangle((0, 0, 399, 119), fill=(0, 90, 200, 255))
    return logo


def test_cobrir_logo_pinta_de_branco():
    im = foto_com_logo()
    out = im_mod.cobrir_logo_fornecedor(im)
    assert out is not None
    assert im_mod.fracao_branca(out, (0, 0, 288, 104)) == 1.0
    # o produto continua intacto
    assert out.getpixel((450, 500)) == (200, 80, 30)


def test_cobrir_logo_descarta_quando_logo_encosta_no_produto():
    # produto invade a faixa logo abaixo da área da logo
    im = foto_com_logo(produto_box=(100, 100, 500, 500))
    assert im_mod.cobrir_logo_fornecedor(im) is None


def test_cobrir_logo_descarta_quando_logo_e_maior_que_a_area():
    im = foto_com_logo(logo_box=(30, 25, 400, 70))  # passa da área (36% = 288px)
    assert im_mod.cobrir_logo_fornecedor(im) is None


def test_fundo_branco():
    assert im_mod.fundo_branco(foto_com_logo())
    colorida = Image.new("RGB", (400, 400), (30, 90, 160))
    assert not im_mod.fundo_branco(colorida)


def test_quadrado_gera_lado_exato_e_centraliza():
    im = Image.new("RGB", (400, 200), (10, 10, 10))
    out = im_mod.quadrado(im, 1000)
    assert out.size == (1000, 1000)
    assert out.getpixel((500, 500)) == (10, 10, 10)  # centro é a foto
    assert out.getpixel((500, 50)) == (255, 255, 255)  # barra branca em cima


def test_aplicar_logo_loja_no_canto_preferido():
    base = Image.new("RGB", (1000, 1000), (255, 255, 255))
    out = im_mod.aplicar_logo_loja(base, logo_da_loja(), "sup_esq")
    assert out.getpixel((60, 40)) == (0, 90, 200)  # dentro da logo
    assert out.getpixel((900, 900)) == (255, 255, 255)


def test_aplicar_logo_loja_troca_de_canto_se_ocupado():
    base = Image.new("RGB", (1000, 1000), (255, 255, 255))
    ImageDraw.Draw(base).rectangle((0, 0, 330, 200), fill=(0, 0, 0))  # sup_esq ocupado
    out = im_mod.aplicar_logo_loja(base, logo_da_loja(), "sup_esq")
    assert out is not None
    assert out.getpixel((900, 40)) == (0, 90, 200)  # foi para sup_dir


def test_aplicar_logo_loja_sem_canto_livre_retorna_none():
    base = Image.new("RGB", (1000, 1000), (0, 0, 0))
    assert im_mod.aplicar_logo_loja(base, logo_da_loja()) is None


def test_preparar_fluxo_completo_maldaner():
    dados = _png(foto_com_logo())
    out, motivo = im_mod.preparar(dados, cobrir_fornecedor=True, logo=logo_da_loja(), lado=1000)
    assert motivo == "ok"
    assert out.size == (1000, 1000)
    # logo da Maldaner (escura) foi trocada pela da loja (azul) no mesmo canto
    assert out.getpixel((60, 40)) == (0, 90, 200)


def test_preparar_rejeita_imagem_pequena_e_lixo():
    pequena = _png(Image.new("RGB", (200, 200), (255, 255, 255)))
    assert im_mod.preparar(pequena, cobrir_fornecedor=False, logo=None)[0] is None
    out, motivo = im_mod.preparar(b"isto nao e imagem", cobrir_fornecedor=False, logo=None)
    assert out is None and "não é uma imagem" in motivo


def test_preparar_rejeita_fundo_colorido():
    colorida = _png(Image.new("RGB", (800, 800), (30, 90, 160)))
    out, motivo = im_mod.preparar(colorida, cobrir_fornecedor=False, logo=None)
    assert out is None and "fundo" in motivo


def test_png_transparente_vira_fundo_branco():
    t = Image.new("RGBA", (800, 800), (0, 0, 0, 0))
    ImageDraw.Draw(t).ellipse((250, 250, 550, 550), fill=(200, 80, 30, 255))
    out = im_mod.carregar(_png(t))
    assert out.getpixel((5, 5)) == (255, 255, 255)


def test_repetidas():
    a = foto_com_logo()
    b = foto_com_logo()
    c = Image.new("RGB", (800, 800), (255, 255, 255))
    ImageDraw.Draw(c).rectangle((0, 400, 800, 800), fill=(0, 0, 0))
    vistos = [im_mod.hash_media(a)]
    assert im_mod.repetida(b, vistos)
    assert not im_mod.repetida(c, vistos)
