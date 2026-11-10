"""Hospeda as fotos tratadas num repositório público do GitHub e devolve os links."""
from __future__ import annotations

import hashlib
import re
import shutil
import subprocess
import time
from pathlib import Path

import requests


class HospedagemErro(Exception):
    pass


def _sku_seguro(sku: str) -> str:
    return re.sub(r"[^A-Za-z0-9_-]", "_", sku)


class Hospedagem:
    def __init__(self, repo_dir: Path, base_url: str, repo_git: str = "", verificar_url: bool = True):
        self.repo_dir = Path(repo_dir)
        self.base_url = base_url.rstrip("/")
        self.repo_git = repo_git
        self.verificar_url = verificar_url

    def _git(self, *args: str) -> str:
        try:
            r = subprocess.run(
                ["git", *args], cwd=self.repo_dir, check=True, capture_output=True, text=True
            )
        except FileNotFoundError as e:
            raise HospedagemErro("Git não está instalado (baixe em https://git-scm.com)") from e
        except subprocess.CalledProcessError as e:
            raise HospedagemErro(f"git {' '.join(args)} falhou: {e.stderr.strip() or e.stdout.strip()}") from e
        return r.stdout

    def preparar_repo(self) -> None:
        """Clona o repositório das fotos se ainda não existir e atualiza."""
        if not (self.repo_dir / ".git").exists():
            if not self.repo_git:
                raise HospedagemErro(f"Pasta {self.repo_dir} não é um repositório git")
            self.repo_dir.parent.mkdir(parents=True, exist_ok=True)
            try:
                subprocess.run(
                    ["git", "clone", self.repo_git, str(self.repo_dir)],
                    check=True, capture_output=True, text=True,
                )
            except subprocess.CalledProcessError as e:
                raise HospedagemErro(f"Não consegui clonar {self.repo_git}: {e.stderr.strip()}") from e
        self._git("pull", "--rebase", "--autostash")

    def publicar(self, sku: str, imagens: list[Path]) -> list[str]:
        """Copia as fotos para fotos/<SKU>/, faz commit e push; devolve as URLs públicas."""
        seguro = _sku_seguro(sku)
        destino = self.repo_dir / "fotos" / seguro
        if destino.exists():
            shutil.rmtree(destino)  # refazer um produto substitui as fotos antigas
        destino.mkdir(parents=True)
        urls = []
        for n, origem in enumerate(imagens, 1):
            selo = hashlib.sha1(Path(origem).read_bytes()).hexdigest()[:8]
            nome = f"{n}-{selo}.jpg"  # o selo muda o link quando a foto muda (evita cache velho)
            shutil.copy2(origem, destino / nome)
            urls.append(f"{self.base_url}/fotos/{seguro}/{nome}")
        self._git("add", "-A", f"fotos/{seguro}")
        if self._git("status", "--porcelain", f"fotos/{seguro}").strip():
            self._git("commit", "-m", f"fotos: {sku}")
        self._git("push")
        if self.verificar_url:
            for u in urls:
                self._esperar_url(u)
        return urls

    @staticmethod
    def _esperar_url(url: str, tentativas: int = 8, pausa: float = 3.0) -> None:
        """O Tiny só consegue baixar a foto quando o link já responde: espera ficar no ar."""
        for _ in range(tentativas):
            try:
                if requests.get(url, timeout=20, stream=True).status_code == 200:
                    return
            except requests.RequestException:
                pass
            time.sleep(pausa)
        raise HospedagemErro(f"A foto não ficou acessível em {url} (o repositório é público?)")
