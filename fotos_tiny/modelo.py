"""Código do modelo (HS-107, GB51267...) e comparação de títulos.

O código do modelo é a melhor chave para achar o mesmo produto em outro site,
porque os nomes mudam de loja para loja, mas o código do fabricante não.
"""
from __future__ import annotations

import re

# "2.4A", "27W", "1M", "4K", "1,5M": medidas, não são código de modelo.
_UNIDADE = re.compile(r"^\d+([.,]\d+)?[A-Za-z]{1,2}$")
_SEPARADOR = r"[\s\-_/]?"


def _eh_codigo(tok: str) -> bool:
    if len(tok) < 3:
        return False
    tem_letra = any(c.isalpha() for c in tok)
    tem_digito = any(c.isdigit() for c in tok)
    if tem_letra and tem_digito:
        return not _UNIDADE.match(tok)
    if tok.isdigit():  # só números: aceita se for longo (ex.: 26458)
        return len(tok) >= 4
    return False


def _ultimo_segmento(nome: str) -> str:
    """Trecho depois do último ' - ' ou '|' (marca + modelo costumam ficar no fim)."""
    i_traco = nome.rfind(" - ")
    i_barra = nome.rfind("|")
    if i_traco < 0 and i_barra < 0:
        return nome
    if i_traco > i_barra:
        return nome[i_traco + 3:]
    return nome[i_barra + 1:]


def extrair_codigos(nome: str) -> list[str]:
    """Códigos de modelo candidatos do nome de um produto, em maiúsculas."""
    codigos: list[str] = []
    for tok in re.split(r"[\s|,;()]+", _ultimo_segmento(nome)):
        tok = tok.strip(".,;:").upper()
        if tok and _eh_codigo(tok) and tok not in codigos:
            codigos.append(tok)
    return codigos


def padrao_codigo(codigo: str) -> re.Pattern:
    """Regex que aceita o código com ou sem hífen/espaço: HS-107, HS107, HS 107."""
    partes = re.findall(r"[A-Za-z]+|\d+", codigo)
    corpo = _SEPARADOR.join(re.escape(p) for p in partes)
    return re.compile(r"(?<![A-Za-z0-9])" + corpo + r"(?![A-Za-z0-9])(?!-\d)", re.IGNORECASE)


def bate(codigo: str, texto: str) -> bool:
    """O código do modelo aparece no texto (título do anúncio)?"""
    return bool(padrao_codigo(codigo).search(texto))


_COMPRIMENTO = re.compile(r"(?<![\w.,])(\d+(?:[.,]\d+)?)\s?M(?![A-Za-z])", re.IGNORECASE)


def comprimentos(texto: str) -> set[str]:
    """Comprimentos em metros citados no texto ('1M', '2 m', '1,5m'), normalizados."""
    achados = set()
    for m in _COMPRIMENTO.finditer(texto):
        achados.add(m.group(1).replace(",", ".").rstrip("0").rstrip("."))
    return achados


def compativel(nome_tiny: str, titulo: str) -> bool:
    """False quando os dois citam comprimentos e nenhum coincide (ex.: 2M x 3M)."""
    a, b = comprimentos(nome_tiny), comprimentos(titulo)
    return not (a and b and a.isdisjoint(b))


def _palavras(texto: str) -> set[str]:
    return {p.strip(".,").upper() for p in re.findall(r"[A-Za-z0-9.,]+", texto) if len(p.strip(".,")) >= 2}


def desambiguar(nome_tiny: str, titulos: list[str]) -> int | None:
    """Índice do título que mais se parece com o nome do produto; None se empatar."""
    if not titulos:
        return None
    if len(titulos) == 1:
        return 0
    base = _palavras(nome_tiny)
    pontos = [len(base & _palavras(t)) for t in titulos]
    melhor = max(pontos)
    if pontos.count(melhor) > 1:
        return None
    return pontos.index(melhor)
