"""Busca fotos no site do fornecedor Maldaner Acessórios (catálogo Mercos) com o seu login."""
from __future__ import annotations

from typing import Iterator
from urllib.parse import quote

from .modelo import bate, compativel, desambiguar

CARTAO = "div.catalog-item-b2b"
FOTOS_PRODUTO = '[class*="Carrousel__carrousel"] img[src*="imagem_produto"]'
BUSCA = "/?busca={}"
MAX_CARTOES = 24


class MaldanerErro(Exception):
    pass


def url_original(src: str) -> str:
    """A foto do carrossel vem como miniatura; o arquivo original é a parte que começa em https://arquivos."""
    i = src.find("https://arquivos")
    return src[i:] if i >= 0 else src


def sem_repetidas(urls: list[str]) -> list[str]:
    vistos, saida = set(), []
    for u in urls:
        if u not in vistos:
            vistos.add(u)
            saida.append(u)
    return saida


def escolher_cartao(codigo: str, nome_tiny: str, titulos: list[str]) -> int | None:
    """Índice do cartão da busca que é o produto certo (código no título, metragem compatível)."""
    aceitos = [i for i, t in enumerate(titulos) if bate(codigo, t) and compativel(nome_tiny, t)]
    if not aceitos:
        return None
    pos = desambiguar(nome_tiny, [titulos[i] for i in aceitos])
    return None if pos is None else aceitos[pos]


class Maldaner:
    def __init__(self, url: str, pasta_perfil, headless: bool = False):
        self.url = url.rstrip("/")
        self.pasta_perfil = str(pasta_perfil)
        self.headless = headless
        self._pw = None
        self.ctx = None
        self.page = None

    def __enter__(self):
        try:
            from playwright.sync_api import sync_playwright
        except ImportError as e:
            raise MaldanerErro("Playwright não instalado: rode instalar.bat") from e
        self._pw = sync_playwright().start()
        self.ctx = self._pw.chromium.launch_persistent_context(
            self.pasta_perfil, headless=self.headless, viewport={"width": 1280, "height": 900}
        )
        self.page = self.ctx.pages[0] if self.ctx.pages else self.ctx.new_page()
        return self

    def __exit__(self, *exc):
        try:
            if self.ctx:
                self.ctx.close()
        finally:
            if self._pw:
                self._pw.stop()

    def logado(self) -> bool:
        return self.page.locator("a:has-text('Sair')").count() > 0

    def garantir_login(self) -> None:
        """Abre o site; se não estiver logado, pede para você entrar na janela (só na 1ª vez)."""
        self.page.goto(self.url, wait_until="domcontentloaded")
        try:
            self.page.wait_for_load_state("networkidle", timeout=20000)
        except Exception:
            pass
        for _ in range(3):
            if self.logado():
                return
            if self.headless:
                raise MaldanerErro("Sem login na Maldaner: rode uma vez sem --headless e faça o login.")
            input("\nFaça o login no site da Maldaner na janela que abriu e aperte ENTER aqui... ")
            self.page.goto(self.url, wait_until="domcontentloaded")
        raise MaldanerErro("Login na Maldaner não foi detectado.")

    def _titulos(self, codigo: str) -> list[str]:
        self.page.goto(self.url + BUSCA.format(quote(codigo)), wait_until="domcontentloaded")
        try:
            self.page.wait_for_selector(CARTAO, timeout=8000)
        except Exception:
            return []
        self.page.wait_for_timeout(800)
        cartoes = self.page.locator(CARTAO)
        return [cartoes.nth(i).inner_text() for i in range(min(cartoes.count(), MAX_CARTOES))]

    def fotos(self, codigo: str, nome_tiny: str) -> Iterator[tuple[str, bytes]]:
        """Fotos (url, bytes) do produto da Maldaner que corresponde ao código; vazio se não achar."""
        titulos = self._titulos(codigo)
        indice = escolher_cartao(codigo, nome_tiny, titulos)
        if indice is None:
            return
        self.page.locator(CARTAO).nth(indice).click()
        try:
            self.page.wait_for_url("**/produtos/**", timeout=10000)
            self.page.wait_for_selector(FOTOS_PRODUTO, timeout=10000)
        except Exception:
            return
        srcs = self.page.eval_on_selector_all(FOTOS_PRODUTO, "els => els.map(e => e.src)")
        for src in sem_repetidas([url_original(s) for s in srcs]):
            dados = self._baixar(src)
            if dados:
                yield src, dados

    def _baixar(self, url: str) -> bytes | None:
        try:
            resp = self.ctx.request.get(url, timeout=30000)
            return resp.body() if resp.ok else None
        except Exception:
            return None
