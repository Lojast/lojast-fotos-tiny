# Fotos automáticas para o Tiny (LojaST)

Pega os produtos do Tiny **sem foto** (cabos, capas e fones), procura fotos pelo código do modelo
(primeiro na Maldaner Acessórios, depois na internet), tira a logo da Maldaner, coloca a logo da LojaST,
sobe as fotos num repositório do GitHub e grava os links no produto do Tiny.

## Como ele roda (e por quanto tempo)

- Roda **no seu computador**, numa janela do Windows. Não roda "na nuvem".
- **O PC precisa ficar ligado, com a janela aberta e sem entrar em suspensão** até terminar
  (Configurações > Sistema > Energia > "Nunca" suspender quando na tomada).
- Se você fechar a janela, desligar ou der Ctrl+C, **nada se perde**: o andamento fica salvo em
  `saida/estado.sqlite`. Rode de novo e ele continua de onde parou, pulando o que já foi feito.
- Velocidade: cerca de 20 a 40 segundos por produto (o Tiny limita as chamadas da API). Algumas
  centenas de produtos levam algumas horas. Pode deixar rodando de um dia para o outro.

## Instalação (uma vez só)

1. Instale o [Python 3.10+](https://www.python.org/downloads/) (marque "Add to PATH") e o [Git](https://git-scm.com).
2. Dê dois cliques em `instalar.bat`.
3. Abra o `.env` que foi criado e preencha:
   - `TINY_TOKEN`: token da API v2 do Tiny (em Configurações, na parte de integrações/API do Tiny).
   - `FOTOS_REPO_GIT` e `FOTOS_BASE_URL`: o repositório **público** das fotos (veja abaixo).
4. Coloque a logo da loja em `assets\logo_lojast.png`.
5. O Git do seu PC precisa estar logado no GitHub (ao subir a primeira foto ele pede o login).

### Repositório das fotos

O Tiny baixa cada foto pelo link, então o repositório de fotos precisa ser **público**.
Use um repositório só para as fotos (o código pode ficar em outro, privado).
O arquivo `.env` (com o token) nunca é enviado ao GitHub: ele está no `.gitignore`.

## Uso

```
rodar.bat                       simulação de todos os produtos (não envia nada)
rodar.bat --sku ST30            simula só um produto
rodar.bat --sku ST30 --gravar   grava de verdade só esse produto
rodar.bat --limite 10 --gravar  grava os 10 primeiros
rodar.bat --gravar              grava todos
```

Na **primeira vez** abre uma janela do Chrome: faça o login na Maldaner e aperte ENTER na janela preta.
O login fica salvo na pasta `perfil-navegador`; depois pode usar `--headless` (sem janela).

Outras opções: `--so-maldaner` (não procura na internet), `--refazer` (refaz o que já foi feito),
`--sem-logo`, `--termo cabo` (só uma categoria), `--max 4` (máximo de fotos).

**Ordem recomendada:** simulação em 2 produtos → `--sku ... --gravar` em 2 produtos e conferir no Tiny
→ `--limite 10 --gravar` → tudo.

## O que ele faz com cada produto

1. Só mexe em produto **sem nenhuma foto**. Nunca apaga nada.
2. Tira o código do modelo do nome (ex.: `GB51267`, `HS-107`). Sem código no nome, pula.
3. Procura na Maldaner pelo código; confere o código e a metragem (um cabo de 2M não pega foto de 3m).
4. Se tiver menos de 3 fotos, completa com a internet (só imagens cujo título cita o mesmo código).
5. Cada foto: cobre a logo da Maldaner com branco, exige fundo branco, deixa quadrada 1000x1000, coloca a
   logo da loja, descarta repetidas. Foto que não passa em alguma regra é descartada.
6. Com 3 ou mais fotos: status `ok`. Com 1 ou 2: sobe mesmo assim como `incompleto`. Nenhuma: `pulado`.
7. Sobe no GitHub, grava no Tiny e **relê o produto para conferir que nenhum outro campo mudou**.
   Se algo mudou, o script para tudo.

Produtos com variações, kits e fabricados são pulados.

## Relatório

`saida/relatorio.csv` (abre no Excel) lista cada produto, status, quantidade de fotos, fontes e motivo.
As fotos tratadas ficam também em `saida/<SKU>/` para você olhar.

## Atenção: direitos das imagens

Fotos da internet pertencem a quem as fez. As da Maldaner você tem como fornecedor, mas confirme com eles que
pode usá-las com a sua logo. Para as da internet, prefira revisar o relatório e as pastas de `saida`.

## Testes

```
.venv\Scripts\activate
pytest
```
