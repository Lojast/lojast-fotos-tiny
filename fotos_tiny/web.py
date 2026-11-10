"""Plano B: procura fotos do mesmo modelo na internet (busca de imagens do DuckDuckGo)."""
from __future__ import annotations

from typing import Callable, Iterator
from urllib.parse import urlparse

import requests

from .modelo import bate, compativel

# Bancos de imagem com marca d'água e o próprio fornecedor (essas já tratamos em maldaner.py).
BLOQUEADOS = (
    "shutterstock", "alamy", "istockphoto", "gettyimages", "dreamstime", "123rf",
    "depositphotos", "maldaneracessorios", "mercos", "meuspedidos", "pinterest",
)
MAX_BYTES = 8_000_000


def _pesquisar_ddgs(consulta: str, max_resultados: int = 25) -> list[dict]:
    try:
        from ddgs import DDGS
    except ImportError:
        from duckduckgo_search import DDGS
    with DDGS() as d:
        return list(d.images(consulta, max_results=max_resultados))


def baixar(url: str, sessao: requests.Session | None = None) -> bytes | None:
    s = sessao or requests
    try:
        r = s.get(
            url, timeout=20, stream=True,
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"},
        )
        if r.status_code != 200 or not r.headers.get("content-type", "").lower().startswith("image/"):
            return None
        dados = r.raw.read(MAX_BYTES + 1, decode_content=True)
        return dados if 0 < len(dados) <= MAX_BYTES else None
    except requests.RequestException:
        return None


def dominio_bloqueado(url: str) -> bool:
    host = urlparse(url).netloc.lower()
    return any(b in host for b in BLOQUEADOS)


def consultas(nome: str, codigos: list[str]) -> list[str]:
    categoria = nome.split()[0] if nome.split() else ""
    qs = [nome]
    for c in codigos:
        qs.append(f"{categoria} {c}".strip())
    vistas, saida = set(), []
    for q in qs:
        if q not in vistas:
            vistas.add(q)
            saida.append(q)
    return saida


def candidatas(nome: str, codigos: list[str], pesquisar: Callable[[str], list[dict]] = _pesquisar_ddgs) -> list[str]:
    """URLs de imagens cujo título cita o código do modelo, sem repetir e sem sites bloqueados."""
    urls: list[str] = []
    for q in consultas(nome, codigos):
        try:
            resultados = pesquisar(q)
        except Exception:
            continue
        for r in resultados:
            url = r.get("image") or ""
            titulo = f"{r.get('title', '')} {r.get('url', '')}"
            if not url or url in urls or dominio_bloqueado(url) or dominio_bloqueado(r.get("url", "")):
                continue
            if not any(bate(c, titulo) for c in codigos) or not compativel(nome, r.get("title", "")):
                continue
            urls.append(url)
    return urls


def fotos(
    nome: str,
    codigos: list[str],
    pesquisar: Callable[[str], list[dict]] = _pesquisar_ddgs,
    baixador: Callable[[str], bytes | None] = baixar,
) -> Iterator[tuple[str, bytes]]:
    """Gera (url, bytes) aos poucos: quem consome para quando já tiver fotos suficientes."""
    for url in candidatas(nome, codigos, pesquisar):
        dados = baixador(url)
        if dados:
            yield url, dados
