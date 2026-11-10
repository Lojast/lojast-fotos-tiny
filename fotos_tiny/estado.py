"""Guarda o andamento (sqlite) para o script continuar de onde parou e gerar o relatório."""
from __future__ import annotations

import csv
import json
import sqlite3
from datetime import datetime
from pathlib import Path

COLUNAS = ["produto_id", "sku", "nome", "status", "n_fotos", "fontes", "motivo", "atualizado"]


class Estado:
    def __init__(self, caminho: Path):
        Path(caminho).parent.mkdir(parents=True, exist_ok=True)
        self.con = sqlite3.connect(str(caminho))
        self.con.execute(
            "CREATE TABLE IF NOT EXISTS produtos ("
            "produto_id TEXT PRIMARY KEY, sku TEXT, nome TEXT, status TEXT, "
            "n_fotos INTEGER, fontes TEXT, motivo TEXT, atualizado TEXT)"
        )
        self.con.commit()

    def status(self, produto_id) -> str | None:
        linha = self.con.execute(
            "SELECT status FROM produtos WHERE produto_id = ?", (str(produto_id),)
        ).fetchone()
        return linha[0] if linha else None

    def registrar(self, produto_id, sku, nome, status, n_fotos=0, fontes=None, motivo="") -> None:
        self.con.execute(
            "INSERT OR REPLACE INTO produtos VALUES (?,?,?,?,?,?,?,?)",
            (
                str(produto_id), sku, nome, status, n_fotos,
                json.dumps(fontes or [], ensure_ascii=False), motivo,
                datetime.now().isoformat(timespec="seconds"),
            ),
        )
        self.con.commit()

    def resumo(self) -> dict:
        return dict(self.con.execute("SELECT status, COUNT(*) FROM produtos GROUP BY status").fetchall())

    def exportar_csv(self, caminho: Path) -> None:
        Path(caminho).parent.mkdir(parents=True, exist_ok=True)
        linhas = self.con.execute(f"SELECT {', '.join(COLUNAS)} FROM produtos ORDER BY sku").fetchall()
        with open(caminho, "w", newline="", encoding="utf-8-sig") as f:  # utf-8-sig: abre certo no Excel
            w = csv.writer(f, delimiter=";")
            w.writerow(COLUNAS)
            w.writerows(linhas)

    def fechar(self) -> None:
        self.con.close()
