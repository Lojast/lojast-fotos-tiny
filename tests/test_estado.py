from fotos_tiny.estado import Estado


def test_registrar_resumo_e_csv(tmp_path):
    e = Estado(tmp_path / "sub" / "estado.sqlite")
    assert e.status("1") is None
    e.registrar(1, "ST30", "Cabo", "ok", 3, ["maldaner", "web"])
    e.registrar(2, "ST31", "Capa", "incompleto", 1, ["web"], "só 1 foto")
    e.registrar(1, "ST30", "Cabo", "ok", 4, ["maldaner"])  # reescreve, não duplica
    assert e.status(1) == "ok"
    assert e.resumo() == {"ok": 1, "incompleto": 1}
    destino = tmp_path / "relatorio.csv"
    e.exportar_csv(destino)
    linhas = destino.read_text(encoding="utf-8-sig").splitlines()
    assert linhas[0].startswith("produto_id;sku;nome;status")
    assert len(linhas) == 3
    e.fechar()


def test_persiste_entre_execucoes(tmp_path):
    caminho = tmp_path / "e.sqlite"
    e = Estado(caminho)
    e.registrar(7, "X", "n", "erro", 0, [], "falhou")
    e.fechar()
    assert Estado(caminho).status(7) == "erro"
