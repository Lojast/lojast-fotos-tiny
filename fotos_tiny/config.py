"""Configuração do script: lê o arquivo .env e variáveis de ambiente."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent


def carregar_env(caminho: Path) -> None:
    """Lê linhas CHAVE=valor de um .env sem sobrescrever o que já existe no ambiente."""
    if not caminho.exists():
        return
    for linha in caminho.read_text(encoding="utf-8").splitlines():
        linha = linha.strip()
        if not linha or linha.startswith("#") or "=" not in linha:
            continue
        chave, valor = linha.split("=", 1)
        os.environ.setdefault(chave.strip(), valor.strip().strip('"').strip("'"))


def _caminho(raiz: Path, valor: str | None, padrao: str) -> Path:
    p = Path(valor) if valor else Path(padrao)
    return p if p.is_absolute() else raiz / p


@dataclass
class Config:
    tiny_token: str
    fotos_repo_dir: Path
    fotos_repo_git: str
    fotos_base_url: str
    logo_loja: Path
    pasta_saida: Path
    pasta_perfil: Path
    maldaner_url: str
    termos: list
    min_fotos: int
    max_fotos: int
    lado: int
    pausa_tiny: float

    @classmethod
    def carregar(cls, raiz: Path = RAIZ) -> "Config":
        carregar_env(raiz / ".env")
        e = os.environ
        return cls(
            tiny_token=e.get("TINY_TOKEN", "").strip(),
            fotos_repo_dir=_caminho(raiz, e.get("FOTOS_REPO_DIR"), "fotos-repo"),
            fotos_repo_git=e.get("FOTOS_REPO_GIT", "https://github.com/Lojast/fotos-produtos.git"),
            fotos_base_url=e.get(
                "FOTOS_BASE_URL", "https://raw.githubusercontent.com/Lojast/fotos-produtos/main"
            ).rstrip("/"),
            logo_loja=_caminho(raiz, e.get("LOGO_LOJA"), "assets/logo_lojast.png"),
            pasta_saida=_caminho(raiz, e.get("PASTA_SAIDA"), "saida"),
            pasta_perfil=_caminho(raiz, e.get("PASTA_PERFIL"), "perfil-navegador"),
            maldaner_url=e.get("MALDANER_URL", "https://maldaneracessorios.com.br").rstrip("/"),
            termos=[t.strip() for t in e.get("TERMOS", "cabo,capa,fone").split(",") if t.strip()],
            min_fotos=int(e.get("MIN_FOTOS", "3")),
            max_fotos=int(e.get("MAX_FOTOS", "5")),
            lado=int(e.get("LADO", "1000")),
            pausa_tiny=float(e.get("PAUSA_TINY", "2.2")),
        )
