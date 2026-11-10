import json

import pytest

from fotos_tiny import tiny
from fotos_tiny.tiny import (
    ProdutoNaoSuportado, Tiny, TinyErro, conferir_preservado,
    montar_payload_alterar, sem_foto, urls_das_fotos,
)

PRODUTO = {
    "id": "948106396", "codigo": "ST30", "nome": "Cabo Tipo-C x Tipo-C | 1M 2.4A - MBTECH GB51267",
    "unidade": "UN", "preco": "19.90", "preco_promocional": "0.00", "ncm": "8544.42.00",
    "origem": "0", "gtin": "", "peso_liquido": "0.05", "peso_bruto": "0.06",
    "situacao": "A", "tipo": "P", "classe_produto": "S", "tipoVariacao": "N",
    "alturaEmbalagem": "2", "larguraEmbalagem": "10", "comprimentoEmbalagem": "16",
    "tipoEmbalagem": "2", "marca": "MBTECH", "seo_title": "Cabo", "slug": "cabo-tipo-c",
    "anexos": [],
}


class RespostaFalsa:
    def __init__(self, corpo):
        self.corpo = corpo

    def raise_for_status(self):
        pass

    def json(self):
        return self.corpo


class SessaoFalsa:
    def __init__(self, respostas):
        self.respostas = list(respostas)
        self.chamadas = []

    def post(self, url, data=None, timeout=None):
        self.chamadas.append((url, data))
        return RespostaFalsa(self.respostas.pop(0))


def cliente(respostas):
    s = SessaoFalsa(respostas)
    return Tiny("tok", pausa=0, sessao=s), s


def test_sem_foto_e_urls():
    assert sem_foto(PRODUTO)
    com = {**PRODUTO, "anexos": [{"anexo": "https://x/1.jpg"}]}
    assert not sem_foto(com)
    assert urls_das_fotos(com) == ["https://x/1.jpg"]


def test_payload_preserva_campos_e_acrescenta_fotos():
    p = montar_payload_alterar(PRODUTO, ["https://x/1.jpg", "https://x/2.jpg"])
    assert p["id"] == "948106396" and p["sequencia"] == 1
    assert p["nome"] == PRODUTO["nome"] and p["preco"] == "19.90" and p["ncm"] == "8544.42.00"
    assert p["altura_embalagem"] == "2" and p["tipo_embalagem"] == "2"
    assert p["seo"]["slug"] == "cabo-tipo-c"
    assert p["anexos"] == [{"anexo": "https://x/1.jpg"}, {"anexo": "https://x/2.jpg"}]
    json.dumps(p)  # tem que ser serializável


def test_payload_nao_duplica_foto_existente():
    com = {**PRODUTO, "anexos": [{"anexo": "https://x/1.jpg"}]}
    p = montar_payload_alterar(com, ["https://x/1.jpg", "https://x/2.jpg"])
    assert [a["anexo"] for a in p["anexos"]] == ["https://x/1.jpg", "https://x/2.jpg"]


@pytest.mark.parametrize("extra", [{"tipoVariacao": "V"}, {"classe_produto": "K"}])
def test_payload_recusa_variacao_e_kit(extra):
    with pytest.raises(ProdutoNaoSuportado):
        montar_payload_alterar({**PRODUTO, **extra}, ["https://x/1.jpg"])


def test_conferir_preservado():
    assert conferir_preservado(PRODUTO, dict(PRODUTO)) == []
    assert conferir_preservado(PRODUTO, {**PRODUTO, "preco": "19.9000"}) == []  # número igual
    dif = conferir_preservado(PRODUTO, {**PRODUTO, "preco": "0.00", "marca": ""})
    assert len(dif) == 2 and any("preco" in d for d in dif)


def test_obter_e_listar_paginado():
    c, s = cliente([
        {"retorno": {"status": "OK", "produto": PRODUTO}},
        {"retorno": {"status": "OK", "numero_paginas": 2, "produtos": [{"produto": {"id": "1"}}]}},
        {"retorno": {"status": "OK", "numero_paginas": 2, "produtos": [{"produto": {"id": "2"}}]}},
    ])
    assert c.obter("948106396")["codigo"] == "ST30"
    assert [p["id"] for p in c.listar_produtos("cabo")] == ["1", "2"]
    assert s.chamadas[0][1]["token"] == "tok" and s.chamadas[0][1]["formato"] == "json"


def test_listar_sem_resultado():
    c, _ = cliente([{"retorno": {"status": "Erro", "codigo_erro": "20", "erros": [{"erro": "sem registros"}]}}])
    assert c.listar_produtos("zzz") == []


def test_erro_da_api():
    c, _ = cliente([{"retorno": {"status": "Erro", "codigo_erro": "99", "erros": [{"erro": "token inválido"}]}}])
    with pytest.raises(TinyErro, match="token inválido"):
        c.obter("1")


def test_limite_de_chamadas_tenta_de_novo(monkeypatch):
    monkeypatch.setattr(tiny.time, "sleep", lambda s: None)
    c, s = cliente([
        {"retorno": {"status": "Erro", "codigo_erro": "6", "erros": [{"erro": "API Bloqueada"}]}},
        {"retorno": {"status": "OK", "produto": PRODUTO}},
    ])
    assert c.obter("1")["id"] == "948106396"
    assert len(s.chamadas) == 2


def test_alterar_envia_json_e_detecta_recusa():
    c, s = cliente([
        {"retorno": {"status": "OK", "registros": {"registro": {"status": "OK"}}}},
        {"retorno": {"status": "OK", "registros": {"registro": {"status": "Erro", "erros": [{"erro": "ruim"}]}}}},
    ])
    c.alterar({"sequencia": 1, "id": "1", "anexos": [{"anexo": "https://x/1.jpg"}]})
    corpo = json.loads(s.chamadas[0][1]["produto"])
    assert corpo["produtos"][0]["produto"]["anexos"][0]["anexo"] == "https://x/1.jpg"
    with pytest.raises(TinyErro):
        c.alterar({"sequencia": 1, "id": "1"})
