"""Programa principal: percorre os produtos do Tiny sem foto, acha, trata e sobe as fotos."""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

from . import maldaner as md
from . import web
from .config import Config
from .estado import Estado
from .hospedagem import Hospedagem, HospedagemErro
from .imagem import carregar_logo, preparar, repetida, hash_media, salvar_jpg
from .modelo import extrair_codigos
from .tiny import (
    ProdutoNaoSuportado, Tiny, TinyErro, conferir_preservado,
    montar_payload_alterar, sem_foto, urls_das_fotos,
)

FINAIS = {"ok", "incompleto", "ja_tem_foto", "pulado"}  # não refaz sem --refazer
EXCLUIR = re.compile(r"pel[ií]cula", re.IGNORECASE)  # películas já estão prontas


class AbortarLote(Exception):
    """Algo inesperado aconteceu ao gravar no Tiny: para tudo para ninguém sair prejudicado."""


def nome_bate_termo(nome: str, termos: list[str]) -> bool:
    if EXCLUIR.search(nome):
        return False
    return any(re.search(rf"\b{re.escape(t)}s?\b", nome, re.IGNORECASE) for t in termos)


def listar_alvos(tiny: Tiny, termos: list[str], sku: str | None) -> list[dict]:
    achados: dict[str, dict] = {}
    for termo in termos:
        for p in tiny.listar_produtos(termo):
            if nome_bate_termo(p.get("nome", ""), termos):
                achados[str(p["id"])] = p
    alvos = sorted(achados.values(), key=lambda p: p.get("codigo", ""))
    if sku:
        alvos = [p for p in alvos if p.get("codigo", "").upper() == sku.upper()]
    return alvos


def tratar(fonte, ja: list, vistas: list[int], cfg: Config, logo, cobrir: bool, max_fotos: int, motivos: list[str]) -> None:
    """Consome (url, bytes) de uma fonte e acrescenta em 'ja' as fotos tratadas e sem repetição."""
    for url, dados in fonte:
        if len(ja) >= max_fotos:
            return
        im, motivo = preparar(dados, cobrir_fornecedor=cobrir, logo=logo, lado=cfg.lado)
        if im is None:
            motivos.append(f"{url[-40:]}: {motivo}")
            continue
        if repetida(im, vistas):
            continue
        vistas.append(hash_media(im))
        ja.append((url, im))


def processar(resumo: dict, cfg: Config, tiny: Tiny, estado: Estado, mald, hosp, logo, args) -> str:
    pid, sku, nome = str(resumo["id"]), resumo.get("codigo", ""), resumo.get("nome", "")
    produto = tiny.obter(pid)
    if not sem_foto(produto):
        estado.registrar(pid, sku, nome, "ja_tem_foto", len(urls_das_fotos(produto)))
        return "ja_tem_foto"
    try:
        montar_payload_alterar(produto, [])  # confere cedo se o produto é do tipo que sabemos alterar
    except ProdutoNaoSuportado as e:
        estado.registrar(pid, sku, nome, "pulado", 0, [], str(e))
        return "pulado"
    codigos = extrair_codigos(nome)
    if not codigos:
        estado.registrar(pid, sku, nome, "pulado", 0, [], "sem código de modelo no nome")
        return "pulado"

    fotos: list = []
    vistas: list[int] = []
    motivos: list[str] = []
    fontes: list[str] = []
    if mald is not None:
        for codigo in codigos:
            tratar(mald.fotos(codigo, nome), fotos, vistas, cfg, logo, True, args.max, motivos)
            if fotos:
                fontes.append("maldaner")
                break
    if len(fotos) < cfg.min_fotos and not args.so_maldaner:
        antes = len(fotos)
        tratar(web.fotos(nome, codigos), fotos, vistas, cfg, logo, False, cfg.max_fotos, motivos)
        if len(fotos) > antes:
            fontes.append("web")
    if not fotos:
        estado.registrar(pid, sku, nome, "pulado", 0, [], "nenhuma foto aproveitável: " + " | ".join(motivos[:3]))
        return "pulado"

    pasta = cfg.pasta_saida / re.sub(r"[^A-Za-z0-9_-]", "_", sku or pid)
    caminhos = []
    for n, (_, im) in enumerate(fotos, 1):
        salvar_jpg(im, pasta / f"{n}.jpg")
        caminhos.append(pasta / f"{n}.jpg")

    status = "ok" if len(fotos) >= cfg.min_fotos else "incompleto"
    motivo = "" if status == "ok" else f"só {len(fotos)} foto(s) de {cfg.min_fotos}"
    if args.gravar:
        urls = hosp.publicar(sku or pid, caminhos)
        tiny.alterar(montar_payload_alterar(produto, urls))
        depois = tiny.obter(pid)
        diferencas = conferir_preservado(produto, depois)
        if diferencas:
            estado.registrar(pid, sku, nome, "erro", len(fotos), fontes, "campos mudaram: " + "; ".join(diferencas))
            raise AbortarLote(f"{sku}: o Tiny alterou outros campos ({'; '.join(diferencas)})")
        if sem_foto(depois):
            estado.registrar(pid, sku, nome, "erro", len(fotos), fontes, "Tiny não registrou as fotos")
            raise AbortarLote(f"{sku}: o Tiny não registrou as fotos enviadas")
    estado.registrar(pid, sku, nome, status, len(fotos), fontes, motivo)
    return status


def ler_args(argv=None):
    p = argparse.ArgumentParser(prog="fotos_tiny", description="Coloca fotos nos produtos do Tiny que estão sem foto.")
    p.add_argument("--gravar", action="store_true", help="de verdade: sobe as fotos no GitHub e grava no Tiny (sem isso é só simulação)")
    p.add_argument("--sku", help="processa só este SKU (ex.: ST30)")
    p.add_argument("--limite", type=int, help="processa no máximo N produtos")
    p.add_argument("--termo", action="append", help="palavra do nome do produto (pode repetir); padrão: TERMOS do .env")
    p.add_argument("--so-maldaner", action="store_true", help="não procura na internet")
    p.add_argument("--refazer", action="store_true", help="refaz também produtos já concluídos")
    p.add_argument("--sem-logo", action="store_true", help="não coloca a logo da loja")
    p.add_argument("--headless", action="store_true", help="navegador invisível (só depois de já ter feito login)")
    p.add_argument("--max", type=int, help="máximo de fotos por produto")
    return p.parse_args(argv)


def main(argv=None) -> int:
    for fluxo in (sys.stdout, sys.stderr):
        if hasattr(fluxo, "reconfigure"):
            fluxo.reconfigure(encoding="utf-8")
    args = ler_args(argv)
    cfg = Config.carregar()
    args.max = args.max or cfg.max_fotos
    if not cfg.tiny_token:
        print("Falta o TINY_TOKEN no arquivo .env (veja o README).")
        return 2
    logo = None
    if not args.sem_logo:
        if not cfg.logo_loja.exists():
            print(f"Falta a logo da loja em {cfg.logo_loja} (ou use --sem-logo).")
            return 2
        logo = carregar_logo(cfg.logo_loja)

    modo = "GRAVANDO no Tiny" if args.gravar else "SIMULAÇÃO (nada é enviado ao Tiny nem ao GitHub)"
    print(f"== {modo} ==")
    tiny = Tiny(cfg.tiny_token, pausa=cfg.pausa_tiny)
    nome_estado = "estado.sqlite" if args.gravar else "estado-simulacao.sqlite"
    estado = Estado(cfg.pasta_saida / nome_estado)
    hosp = None
    if args.gravar:
        hosp = Hospedagem(cfg.fotos_repo_dir, cfg.fotos_base_url, cfg.fotos_repo_git)
        try:
            hosp.preparar_repo()
        except HospedagemErro as e:
            print(f"Problema com o repositório das fotos: {e}")
            return 2

    termos = args.termo or cfg.termos
    print("Listando produtos no Tiny...")
    alvos = listar_alvos(tiny, termos, args.sku)
    print(f"{len(alvos)} produto(s) com {', '.join(termos)} no nome.")

    mald = None
    codigo_saida = 0
    try:
        mald_ctx = md.Maldaner(cfg.maldaner_url, cfg.pasta_perfil, headless=args.headless)
        mald = mald_ctx.__enter__()
        mald.garantir_login()
        feitos = 0
        for i, resumo in enumerate(alvos, 1):
            pid = str(resumo["id"])
            if not args.refazer and estado.status(pid) in FINAIS:
                continue
            if args.limite and feitos >= args.limite:
                break
            feitos += 1
            try:
                res = processar(resumo, cfg, tiny, estado, mald, hosp, logo, args)
            except AbortarLote as e:
                print(f"\nPARADO POR SEGURANÇA: {e}")
                codigo_saida = 3
                break
            except (TinyErro, HospedagemErro, md.MaldanerErro) as e:
                estado.registrar(pid, resumo.get("codigo", ""), resumo.get("nome", ""), "erro", 0, [], str(e))
                res = f"erro ({e})"
            print(f"[{i}/{len(alvos)}] {resumo.get('codigo', '')} -> {res}")
    except KeyboardInterrupt:
        print("\nInterrompido. Rode de novo para continuar de onde parou.")
        codigo_saida = 130
    except md.MaldanerErro as e:
        print(f"Maldaner: {e}")
        codigo_saida = 2
    finally:
        if mald is not None:
            mald_ctx.__exit__(None, None, None)
        relatorio = cfg.pasta_saida / ("relatorio.csv" if args.gravar else "relatorio-simulacao.csv")
        estado.exportar_csv(relatorio)
        print(f"\nResumo: {estado.resumo()}\nRelatório: {relatorio}")
        estado.fechar()
    return codigo_saida


if __name__ == "__main__":
    raise SystemExit(main())
