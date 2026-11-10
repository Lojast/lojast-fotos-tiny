"""Cliente da API v2 do Tiny ERP: listar produtos, ler e gravar fotos."""
from __future__ import annotations

import json
import time

import requests

URL = "https://api.tiny.com.br/api2/{}.php"

# Campos que o produto.obter devolve e que o produto.alterar aceita com o mesmo nome.
CAMPOS_DIRETOS = [
    "codigo", "nome", "unidade", "preco", "preco_promocional", "ncm", "origem", "gtin",
    "gtin_embalagem", "localizacao", "peso_liquido", "peso_bruto", "estoque_minimo",
    "estoque_maximo", "id_fornecedor", "codigo_fornecedor", "codigo_pelo_fornecedor",
    "unidade_por_caixa", "preco_custo", "situacao", "tipo", "classe_ipi", "valor_ipi_fixo",
    "cod_lista_servicos", "descricao_complementar", "garantia", "cest", "obs",
    "dias_preparacao", "marca", "categoria", "classe_produto",
]
# No obter vêm em camelCase; no alterar são snake_case.
CAMPOS_RENOMEADOS = {
    "tipoEmbalagem": "tipo_embalagem",
    "alturaEmbalagem": "altura_embalagem",
    "larguraEmbalagem": "largura_embalagem",
    "comprimentoEmbalagem": "comprimento_embalagem",
    "diametroEmbalagem": "diametro_embalagem",
}
CAMPOS_SEO = ["seo_title", "seo_keywords", "link_video", "seo_description", "slug"]

# Campos comparados antes x depois da gravação para provar que o cadastro foi preservado.
CAMPOS_CONFERIDOS = (
    CAMPOS_DIRETOS
    + list(CAMPOS_RENOMEADOS)
    + CAMPOS_SEO
)


class TinyErro(Exception):
    def __init__(self, mensagem: str, codigo: str = ""):
        super().__init__(mensagem)
        self.codigo = codigo


class ProdutoNaoSuportado(Exception):
    """Produto com variações, kit etc.: o script não mexe para não bagunçar o cadastro."""


def _mensagem_erro(ret: dict) -> str:
    erros = ret.get("erros") or []
    partes = []
    for e in erros:
        partes.append(e.get("erro", str(e)) if isinstance(e, dict) else str(e))
    return "; ".join(partes) or f"status {ret.get('status')}"


class Tiny:
    def __init__(self, token: str, pausa: float = 2.2, sessao: requests.Session | None = None):
        self.token = token
        self.pausa = pausa
        self.s = sessao or requests.Session()
        self._ultimo = 0.0

    def _esperar(self) -> None:
        falta = self.pausa - (time.monotonic() - self._ultimo)
        if falta > 0:
            time.sleep(falta)
        self._ultimo = time.monotonic()

    def _chamar(self, endpoint: str, **params) -> dict:
        for tentativa in range(5):
            self._esperar()
            resp = self.s.post(
                URL.format(endpoint),
                data={"token": self.token, "formato": "json", **params},
                timeout=60,
            )
            resp.raise_for_status()
            ret = resp.json()["retorno"]
            if str(ret.get("status")) == "OK":
                return ret
            msg = _mensagem_erro(ret)
            codigo = str(ret.get("codigo_erro", ""))
            if codigo == "6" or "bloquead" in msg.lower() or "limite" in msg.lower():
                time.sleep(30 * (tentativa + 1))  # limite de chamadas por minuto: espera e tenta de novo
                continue
            raise TinyErro(msg, codigo)
        raise TinyErro("API do Tiny bloqueada por excesso de chamadas")

    def listar_produtos(self, pesquisa: str, situacao: str = "A") -> list[dict]:
        """Produtos cujo nome ou código contém 'pesquisa' (todas as páginas)."""
        produtos: list[dict] = []
        pagina = 1
        while True:
            try:
                ret = self._chamar("produtos.pesquisa", pesquisa=pesquisa, situacao=situacao, pagina=pagina)
            except TinyErro as e:
                if e.codigo == "20":  # "A consulta não retornou registros"
                    break
                raise
            produtos += [item["produto"] for item in ret.get("produtos", [])]
            if pagina >= int(ret.get("numero_paginas", 1)):
                break
            pagina += 1
        return produtos

    def obter(self, produto_id) -> dict:
        return self._chamar("produto.obter", id=produto_id)["produto"]

    def alterar(self, produto: dict) -> None:
        corpo = json.dumps({"produtos": [{"produto": produto}]}, ensure_ascii=False)
        ret = self._chamar("produto.alterar", produto=corpo)
        registros = ret.get("registros") or {}
        if isinstance(registros, dict):
            registros = registros.get("registro", registros)
        if isinstance(registros, dict):
            registros = [registros]
        for r in registros:
            r = r.get("registro", r) if isinstance(r, dict) else r
            if isinstance(r, dict) and str(r.get("status")) != "OK":
                erros = r.get("erros") or r.get("erro") or r
                raise TinyErro(f"Tiny recusou a alteração: {erros}")


def urls_das_fotos(produto: dict) -> list[str]:
    """URLs das imagens já cadastradas (anexos + imagens externas)."""
    urls = []
    for a in produto.get("anexos") or []:
        urls.append(a["anexo"] if isinstance(a, dict) else a)
    for i in produto.get("imagens_externas") or []:
        item = i.get("imagem_externa", i) if isinstance(i, dict) else {"url": i}
        urls.append(item.get("url", ""))
    return [u for u in urls if u]


def sem_foto(produto: dict) -> bool:
    return not urls_das_fotos(produto)


def montar_payload_alterar(produto: dict, novas_urls: list[str]) -> dict:
    """Monta o JSON do produto.alterar a partir do produto.obter, só acrescentando as fotos.

    Reenvia todos os campos já cadastrados para o Tiny não apagar nada que não mandamos.
    """
    if produto.get("tipoVariacao", "N") != "N" or produto.get("classe_produto", "S") != "S":
        raise ProdutoNaoSuportado("produto com variações, kit ou fabricado")
    p: dict = {"sequencia": 1, "id": produto["id"]}
    for campo in CAMPOS_DIRETOS:
        if campo in produto and produto[campo] is not None:
            p[campo] = produto[campo]
    for de, para in CAMPOS_RENOMEADOS.items():
        if de in produto and produto[de] is not None:
            p[para] = produto[de]
    seo = {c: produto[c] for c in CAMPOS_SEO if produto.get(c) is not None}
    if seo:
        p["seo"] = seo
    todas = urls_das_fotos(produto) + [u for u in novas_urls if u not in urls_das_fotos(produto)]
    p["anexos"] = [{"anexo": u} for u in todas]
    return p


def _norm(valor) -> str:
    texto = "" if valor is None else str(valor).strip()
    try:
        return repr(float(texto))
    except ValueError:
        return texto


def conferir_preservado(antes: dict, depois: dict) -> list[str]:
    """Campos que mudaram entre o produto lido antes e depois da gravação (exceto fotos)."""
    diferencas = []
    for campo in CAMPOS_CONFERIDOS:
        if campo in antes and _norm(antes.get(campo)) != _norm(depois.get(campo)):
            diferencas.append(f"{campo}: {antes.get(campo)!r} -> {depois.get(campo)!r}")
    return diferencas
