import subprocess

import pytest
from PIL import Image

from fotos_tiny.hospedagem import Hospedagem, HospedagemErro


def git(*args, cwd):
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True)


@pytest.fixture
def remoto(tmp_path):
    """Repositório 'GitHub' local (bare) já com um commit inicial."""
    bare = tmp_path / "remoto.git"
    subprocess.run(["git", "init", "--bare", "-b", "main", str(bare)], check=True, capture_output=True)
    semente = tmp_path / "semente"
    semente.mkdir()
    git("init", "-b", "main", cwd=semente)
    git("config", "user.email", "t@t", cwd=semente)
    git("config", "user.name", "t", cwd=semente)
    (semente / "README.md").write_text("fotos")
    git("add", "-A", cwd=semente)
    git("commit", "-m", "inicio", cwd=semente)
    git("remote", "add", "origin", str(bare), cwd=semente)
    git("push", "origin", "main", cwd=semente)
    return bare


def foto(caminho, cor):
    Image.new("RGB", (20, 20), cor).save(caminho, "JPEG")
    return caminho


def hosp(tmp_path, remoto):
    h = Hospedagem(tmp_path / "repo", "https://raw.example/main", str(remoto), verificar_url=False)
    h.preparar_repo()
    git("config", "user.email", "t@t", cwd=h.repo_dir)
    git("config", "user.name", "t", cwd=h.repo_dir)
    return h


def test_publicar_gera_urls_e_envia(tmp_path, remoto):
    h = hosp(tmp_path, remoto)
    imgs = [foto(tmp_path / "a.jpg", "red"), foto(tmp_path / "b.jpg", "blue")]
    urls = h.publicar("ST 30/x", imgs)
    assert len(urls) == 2
    assert all(u.startswith("https://raw.example/main/fotos/ST_30_x/") for u in urls)
    # chegou no remoto
    clone = tmp_path / "conferencia"
    subprocess.run(["git", "clone", str(remoto), str(clone)], check=True, capture_output=True)
    assert len(list((clone / "fotos" / "ST_30_x").glob("*.jpg"))) == 2


def test_republicar_substitui_e_sem_mudanca_nao_quebra(tmp_path, remoto):
    h = hosp(tmp_path, remoto)
    a = foto(tmp_path / "a.jpg", "red")
    h.publicar("ST30", [a])
    h.publicar("ST30", [a])  # nada mudou: não deve falhar no commit
    h.publicar("ST30", [foto(tmp_path / "c.jpg", "green")])
    assert len(list((h.repo_dir / "fotos" / "ST30").glob("*.jpg"))) == 1


def test_repo_inexistente(tmp_path):
    h = Hospedagem(tmp_path / "x", "https://r", "")
    with pytest.raises(HospedagemErro):
        h.preparar_repo()
