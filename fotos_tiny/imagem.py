"""Tratamento das fotos: cobrir a logo do fornecedor, fundo branco quadrado, logo da loja."""
from __future__ import annotations

import io
from pathlib import Path

from PIL import Image, ImageDraw

BRANCO = (255, 255, 255)
LIMIAR_BRANCO = 240  # pixel com cinza >= 240 conta como "branco"

# Onde fica a logo da Maldaner nas fotos deles (canto superior esquerdo), em fração da imagem.
AREA_LOGO_FORNECEDOR = (0.0, 0.0, 0.36, 0.13)

CANTOS = ("sup_esq", "sup_dir", "inf_esq", "inf_dir")


def carregar(dados: bytes) -> Image.Image:
    """Abre os bytes de uma imagem e devolve RGB (transparência vira branco)."""
    im = Image.open(io.BytesIO(dados))
    im.load()
    if im.mode in ("RGBA", "LA") or (im.mode == "P" and "transparency" in im.info):
        im = im.convert("RGBA")
        fundo = Image.new("RGBA", im.size, BRANCO + (255,))
        fundo.alpha_composite(im)
        im = fundo
    return im.convert("RGB")


def carregar_logo(caminho: Path) -> Image.Image:
    if not Path(caminho).exists():
        raise FileNotFoundError(
            f"Logo da loja não encontrada em {caminho}. Coloque o arquivo logo_lojast.png na pasta "
            "assets (ou use --sem-logo para rodar sem a logo)."
        )
    return Image.open(caminho).convert("RGBA")


def fracao_branca(im: Image.Image, caixa) -> float:
    """Fração (0 a 1) de pixels quase brancos dentro da caixa (x0, y0, x1, y1)."""
    x0, y0, x1, y1 = (int(v) for v in caixa)
    x0, y0 = max(0, x0), max(0, y0)
    x1, y1 = min(im.width, x1), min(im.height, y1)
    if x1 <= x0 or y1 <= y0:
        return 1.0
    hist = im.crop((x0, y0, x1, y1)).convert("L").histogram()
    return sum(hist[LIMIAR_BRANCO:]) / sum(hist)


def cobrir_logo_fornecedor(im: Image.Image, area=AREA_LOGO_FORNECEDOR, folga: float = 0.015):
    """Pinta de branco a área da logo do fornecedor.

    Só faz isso se as faixas logo ao lado e logo abaixo da área forem brancas, ou seja, se a logo
    cabe na área e não encosta no produto. Caso contrário devolve None (foto descartada), para não
    deixar mancha nem apagar parte do produto.
    """
    w, h = im.size
    x1, y1 = int(w * area[2]), int(h * area[3])
    f = max(3, int(min(w, h) * folga))
    if fracao_branca(im, (x1, 0, x1 + f, y1)) < 0.985:
        return None
    if fracao_branca(im, (0, y1, x1, y1 + f)) < 0.985:
        return None
    novo = im.copy()
    ImageDraw.Draw(novo).rectangle((0, 0, x1, y1), fill=BRANCO)
    return novo


def fundo_branco(im: Image.Image, borda: float = 0.02, minimo: float = 0.9) -> bool:
    """As quatro bordas da foto são (quase) brancas?"""
    w, h = im.size
    e = max(2, int(min(w, h) * borda))
    faixas = [(0, 0, w, e), (0, h - e, w, h), (0, 0, e, h), (w - e, 0, w, h)]
    return all(fracao_branca(im, f) >= minimo for f in faixas)


def quadrado(im: Image.Image, lado: int = 1000) -> Image.Image:
    """Centraliza a foto num quadrado branco lado x lado."""
    w, h = im.size
    s = max(w, h)
    tela = Image.new("RGB", (s, s), BRANCO)
    tela.paste(im, ((s - w) // 2, (s - h) // 2))
    return tela.resize((lado, lado), Image.LANCZOS)


def _posicao(canto: str, im_size, logo_size, margem: int):
    w, h = im_size
    lw, lh = logo_size
    x = margem if "esq" in canto else w - lw - margem
    y = margem if "sup" in canto else h - lh - margem
    return x, y


def aplicar_logo_loja(
    im: Image.Image,
    logo: Image.Image,
    preferido: str = "sup_esq",
    largura_rel: float = 0.24,
    margem_rel: float = 0.03,
):
    """Cola a logo da loja no canto preferido; se o canto tiver produto, tenta os outros.

    Devolve None se nenhum canto estiver livre (não cobrimos o produto com a logo).
    """
    w, h = im.size
    lw = max(1, int(w * largura_rel))
    lh = max(1, int(logo.height * lw / logo.width))
    pequena = logo.convert("RGBA").resize((lw, lh), Image.LANCZOS)
    margem = int(w * margem_rel)
    ordem = [preferido] + [c for c in CANTOS if c != preferido]
    for canto in ordem:
        x, y = _posicao(canto, im.size, (lw, lh), margem)
        if fracao_branca(im, (x, y, x + lw, y + lh)) >= 0.97:
            base = im.convert("RGBA")
            base.alpha_composite(pequena, (x, y))
            return base.convert("RGB")
    return None


def preparar(
    dados: bytes,
    *,
    cobrir_fornecedor: bool,
    logo: Image.Image | None,
    lado: int = 1000,
    min_lado: int = 400,
):
    """Pipeline completo de uma foto. Devolve (imagem, "ok") ou (None, motivo)."""
    try:
        im = carregar(dados)
    except Exception as erro:  # arquivo corrompido ou não é imagem
        return None, f"arquivo não é uma imagem válida ({erro.__class__.__name__})"
    if min(im.size) < min_lado:
        return None, f"imagem pequena ({im.width}x{im.height})"
    if cobrir_fornecedor:
        coberta = cobrir_logo_fornecedor(im)
        if coberta is None:
            return None, "logo do fornecedor encosta no produto"
        im = coberta
    if not fundo_branco(im):
        return None, "fundo da foto não é branco"
    im = quadrado(im, lado)
    if logo is not None:
        com_logo = aplicar_logo_loja(im, logo)
        if com_logo is None:
            return None, "sem canto livre para a logo da loja"
        im = com_logo
    return im, "ok"


def hash_media(im: Image.Image) -> int:
    """Impressão digital 8x8 da foto, para achar fotos repetidas."""
    pequena = im.convert("L").resize((8, 8), Image.LANCZOS)
    pixels = list(pequena.tobytes())
    media = sum(pixels) / len(pixels)
    bits = 0
    for p in pixels:
        bits = (bits << 1) | (1 if p >= media else 0)
    return bits


def distancia(h1: int, h2: int) -> int:
    return bin(h1 ^ h2).count("1")


def repetida(im: Image.Image, vistos: list[int], tolerancia: int = 4) -> bool:
    h = hash_media(im)
    return any(distancia(h, v) <= tolerancia for v in vistos)


def salvar_jpg(im: Image.Image, caminho: Path) -> None:
    Path(caminho).parent.mkdir(parents=True, exist_ok=True)
    im.save(caminho, "JPEG", quality=90, optimize=True)
