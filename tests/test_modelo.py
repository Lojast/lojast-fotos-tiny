import pytest

from fotos_tiny.modelo import (
    bate,
    comprimentos,
    compativel,
    desambiguar,
    extrair_codigos,
)

# Nomes reais do Tiny da LojaST -> código(s) esperado(s)
NOMES = [
    ("Cabo Tipo-C x Tipo-C | 1M QC 3.0 - HREBOS HS-107", ["HS-107"]),
    ("Cabo Tipo-C x Tipo-C | 1M 2.4A - MBTECH GB51267", ["GB51267"]),
    ("Cabo Lightning x Tipo-C | Turbo Paracorde 27W - AGOLD CB121", ["CB121"]),
    ("Cabo USB-C x Lightning 2 M Ultrametalic 30W - CB3701 HREBOS", ["CB3701"]),
    ("Cabo Tipo-C x USB | 1M 3.1A - Luo Lu1106", ["LU1106"]),
    ("Cabo Tipo-c x USB | 1M 3A - Kapbom KAP-1M-TY", ["KAP-1M-TY"]),
    ("Cabo Lightning x USB | 2M 5A Turbo - AGOLD CB109-2", ["CB109-2"]),
    ("Cabo Tipo-C x USB | 1M Colorido Turbo 5.1A - LEHMOX LE-2217", ["LE-2217"]),
    ("Cabo Lightning x USB | 1M - KAPBOM KAP-305-5G", ["KAP-305-5G"]),
    ("Cabo Tipo-C x USB | 2M Data Cable - PMCELL CB-11", ["CB-11"]),
    ("Cabo HDMI 4K | 3M - ItBlue LE-6621-3M", ["LE-6621-3M"]),
    ("Cabo Auxiliar P2 x P2 | 1,5M Estereo - MBTECH MB51004", ["MB51004"]),
    ("Kit de Carregamento Tipo-C Fonte USB + Cabo - AGOLD CA38-3", ["CA38-3"]),
    ("Cabo Lightning | USB x Lightning 1M | 4.8A | HMASTON HB11-2", ["HB11-2"]),
    ("Cabo Micro-USB | USB x Micro-USB 1M | CB72-1", ["CB72-1"]),
    ("Cabo conversor - KNUP KP-AD154", ["KP-AD154"]),
    ("Cabo Tipo-C x Tipo-C | 1M Paracorde - Apple similar 26458", ["26458"]),
    # sem código de modelo no nome: não pode inventar
    ("Cabo Lightning x Tipo-C | 1M - Apple Original", []),
    ("Cabo HDMI", []),
    ("Cabo de Impressora - KNUP", []),
]


@pytest.mark.parametrize("nome,esperado", NOMES)
def test_extrair_codigos(nome, esperado):
    assert extrair_codigos(nome) == esperado


def test_medidas_nao_sao_codigo():
    assert extrair_codigos("Cabo X | 2.4A 27W 1M 4K - 3.1A") == []


@pytest.mark.parametrize(
    "codigo,titulo,esperado",
    [
        ("HS-107", "Cabo Dados Turbo Type C x Type C 3.0 1 Metro Hrebos HS107 Branco", True),
        ("HS-107", "Cabo Hrebos HS 107", True),
        ("GB51267", "E. CE - CABO TIPO C x TIPO C DE 1m 2.4A GB51267 MBTECH 324802", True),
        ("CB-11", "E. CE - CABO TIPO C PMCELL 1m CB-11 DATA CABLE", True),
        ("CB-11", "CABO CB-110 TURBO", False),  # não pode casar parte de outro código
        ("CB121", "E. CI - CABO IPHONE x TIPO C 27W DE 1m CB121 GOLD 768436", True),
        ("CB121", "CABO CB121-3 GOLD", False),  # variante diferente
        ("HS-107", "Cabo Hrebos HS-1070", False),
        ("KAP-1M-TY", "CABO TIPO C KAP-1M-TY KAPBOM", True),
    ],
)
def test_bate(codigo, titulo, esperado):
    assert bate(codigo, titulo) is esperado


def test_comprimentos():
    assert comprimentos("Cabo 1M 2.4A") == {"1"}
    assert comprimentos("CABO DE 1,5m") == {"1.5"}
    assert comprimentos("USB-C x Lightning 2 M Ultrametalic 30W") == {"2"}
    assert comprimentos("Carregador 27W 3.1A") == set()


def test_compativel_rejeita_comprimento_diferente():
    # caso real: Tiny diz 2M, Maldaner vende 3m do mesmo código
    assert not compativel("Cabo Tipo-C x Tipo-C | 2M 2.4A - MBTECH GB51269", "CABO TIPO C x TIPO C DE 3m 2.4A GB51269 MBTECH")
    assert compativel("Cabo Tipo-C x Tipo-C | 1M 2.4A - MBTECH GB51267", "CABO TIPO C x TIPO C DE 1m 2.4A GB51267 MBTECH")
    # um dos lados sem comprimento: não rejeita
    assert compativel("Cabo Tipo-C - X HS-1", "Cabo Tipo C HS-1")


def test_desambiguar():
    nome = "Cabo Tipo-C x USB | 3M 2.4A - MBTECH GB51270"
    titulos = ["CABO TIPO C x USB DE 3m 2.4A GB51270 MBTECH", "CABO LIGHTNING GB51270 MBTECH"]
    assert desambiguar(nome, titulos) == 0
    assert desambiguar(nome, ["IGUAL GB51270", "IGUAL GB51270"]) is None
    assert desambiguar(nome, ["UNICO"]) == 0
    assert desambiguar(nome, []) is None
