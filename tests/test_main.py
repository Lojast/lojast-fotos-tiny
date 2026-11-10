import io
from types import SimpleNamespace

import pytest
from PIL import Image, ImageDraw

from fotos_tiny import main as m
from fotos_tiny import web
from fotos_tiny.config import Config
from fotos_tiny.estado import Estado

NOME = "Cabo Tipo-C x Tipo-C | 1M 2.4A - MBTECH GB51267"


def png(cor, tamanho=(800, 800), logo_maldaner=False):
    im = Image.new("RGB", tamanho, "white")
    d = ImageDraw.Draw(im)
    d.rectangle([300, 350, 500, 450], fill=cor)  # "produto" no meio
    if logo_maldaner:
        d.rectangle([20, 20, 200, 60], fill=(200, 0, 0))
    buf = io.BytesIO()
    im.save(buf, "PNG")
    return buf.getvalue()


def logo_loja(tmp_path):
    caminho = tmp_path / "logo.png"
    Image.new("RGBA", (200, 80), (0, 0, 255, 255)).save(caminho)
    return caminho


class MaldanerFalso:
    def __init__(self, fotos):
        self._fotos = fotos

    def fotos(self, codigo, nome):
        yield from self._fotos


class TinyFalso:
    def __init__(self, produto):
        self.produto = produto
        self.alterados = []

    def obter(self, pid):
        if self.alterados:  # depois da gravação o Tiny devolve as fotos
            return {**self.produto, "anexos": self.alterados[-1]["anexos"]}
        return self.produto

    def alterar(self, payload):
        self.alterados.append(payload)


class HospFalsa:
    def publicar(self, sku, imagens):
        return [f"https://raw.example/{sku}/{i}.jpg" for i, _ in enumerate(imagens, 1)]


def contexto(tmp_path, produto, mald, hosp=None, gravar=False):
    cfg = Config.carregar(tmp_path)
    cfg.pasta_saida = tmp_path / "saida"
    estado = Estado(tmp_path / "e.sqlite")
    logo = m.carregar_logo(logo_loja(tmp_path))
    args = SimpleNamespace(gravar=gravar, so_maldaner=True, max=5)
    resumo = {"id": produto["id"], "codigo": produto["codigo"], "nome": produto["nome"]}
    return cfg, TinyFalso(produto), estado, mald, hosp, logo, args, resumo


PRODUTO = {
    "id": "1", "codigo": "ST30", "nome": NOME, "unidade": "UN", "preco": "19.90", "origem": "0",
    "situacao": "A", "tipo": "P", "classe_produto": "S", "tipoVariacao": "N", "anexos": [],
}


def rodar(tmp_path, produto, mald, hosp=None, gravar=False):
    cfg, tiny, estado, mald, hosp, logo, args, resumo = contexto(tmp_path, produto, mald, hosp, gravar)
    res = m.processar(resumo, cfg, tiny, estado, mald, hosp, logo, args)
    return res, tiny, estado, cfg


def test_simulacao_gera_fotos_mas_nao_grava(tmp_path):
    fotos = [("u1", png((0, 0, 0), logo_maldaner=True)), ("u2", _forma_diferente())]
    res, tiny, estado, cfg = rodar(tmp_path, PRODUTO, MaldanerFalso(fotos))
    assert res == "incompleto"  # só 2 fotos, mínimo 3
    assert tiny.alterados == []
    assert len(list((cfg.pasta_saida / "ST30").glob("*.jpg"))) == 2
    assert estado.status("1") == "incompleto"


def test_tres_fotos_diferentes_ficam_ok(tmp_path):
    # formas diferentes para não cair como foto repetida
    fotos = [("u0", png((0, 0, 0), logo_maldaner=True)), ("u1", _forma_diferente()), ("u2", _forma_diferente(True))]
    res, *_ = rodar(tmp_path, PRODUTO, MaldanerFalso(fotos))
    assert res == "ok"


def _forma_diferente(grande=False):
    im = Image.new("RGB", (800, 800), "white")
    d = ImageDraw.Draw(im)
    d.ellipse([150, 150, 650, 650] if grande else [350, 200, 450, 700], fill=(10, 10, 10))
    buf = io.BytesIO()
    im.save(buf, "PNG")
    return buf.getvalue()


def test_gravando_publica_altera_e_confere(tmp_path):
    fotos = [("u1", png((0, 0, 0), logo_maldaner=True))]
    res, tiny, estado, _ = rodar(tmp_path, PRODUTO, MaldanerFalso(fotos), HospFalsa(), gravar=True)
    assert res == "incompleto"
    assert len(tiny.alterados) == 1
    assert tiny.alterados[0]["anexos"] == [{"anexo": "https://raw.example/ST30/1.jpg"}]
    assert tiny.alterados[0]["nome"] == NOME


def test_para_o_lote_se_o_tiny_mudar_outro_campo(tmp_path):
    class TinyQueApagaPreco(TinyFalso):
        def obter(self, pid):
            if self.alterados:
                return {**self.produto, "preco": "0.00", "anexos": self.alterados[-1]["anexos"]}
            return self.produto

    cfg, _, estado, mald, hosp, logo, args, resumo = contexto(
        tmp_path, PRODUTO, MaldanerFalso([("u1", png((0, 0, 0), logo_maldaner=True))]), HospFalsa(), True
    )
    with pytest.raises(m.AbortarLote):
        m.processar(resumo, cfg, TinyQueApagaPreco(PRODUTO), estado, mald, hosp, logo, args)
    assert estado.status("1") == "erro"


def test_produto_que_ja_tem_foto_e_ignorado(tmp_path):
    com_foto = {**PRODUTO, "anexos": [{"anexo": "https://x/1.jpg"}]}
    res, tiny, *_ = rodar(tmp_path, com_foto, MaldanerFalso([]), HospFalsa(), True)
    assert res == "ja_tem_foto" and tiny.alterados == []


def test_sem_codigo_no_nome_e_pulado(tmp_path):
    res, *_ = rodar(tmp_path, {**PRODUTO, "nome": "Cabo comum branco"}, MaldanerFalso([]))
    assert res == "pulado"


def test_variacao_e_pulada(tmp_path):
    res, *_ = rodar(tmp_path, {**PRODUTO, "tipoVariacao": "V"}, MaldanerFalso([]))
    assert res == "pulado"


def test_cai_na_web_quando_maldaner_nao_tem(tmp_path, monkeypatch):
    monkeypatch.setattr(web, "fotos", lambda nome, codigos: iter([("w1", _forma_diferente()), ("w2", _forma_diferente(True))]))
    cfg, tiny, estado, mald, hosp, logo, args, resumo = contexto(tmp_path, PRODUTO, MaldanerFalso([]))
    args.so_maldaner = False
    assert m.processar(resumo, cfg, tiny, estado, mald, hosp, logo, args) == "incompleto"
    assert "web" in estado.con.execute("SELECT fontes FROM produtos").fetchone()[0]


def test_filtro_de_nome():
    termos = ["cabo", "capa", "fone"]
    assert m.nome_bate_termo("Cabo USB 1M", termos)
    assert m.nome_bate_termo("Fones de ouvido HS-107", termos)
    assert m.nome_bate_termo("Capa iPhone 13", termos)
    assert not m.nome_bate_termo("Telefone fixo", termos)
    assert not m.nome_bate_termo("Capacete moto", termos)
    assert not m.nome_bate_termo("Película capa iPhone", termos)
