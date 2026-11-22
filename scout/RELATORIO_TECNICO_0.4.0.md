# Caça à Arte Scout 0.4.0, relatório técnico

Data: 22-11-2026. Base: `0.3.3_REV9_PAGINACAO_CORRIGIDA`.

## 1. Inventário dos 29 ZIP do projecto

Todos os ZIP foram extraídos e comparados (os originais ficam intactos).

| ZIP | SHA-256 (início) do ficheiro principal | Linhas | Funcionalidades detectadas | Ficheiros de teste |
|---|---|---|---|---|
| Caca_Arte_App_v0_1 | — | — | PWA HTML/JS (sem motores) | — |
| 0.3.2 | bb0ee3d194 | 890 | P55 colecção, São Mamede, alfarrabistas, multimotor, SQLite, 3 áreas | 2 |
| 0.3.3 | c9057bdd7f | 939 | P55 colecção, São Mamede, alfarrabistas, multimotor, SQLite, 3 áreas, paginação UI | 2 |
| 0.3.3_REV1 | c9057bdd7f | 939 | P55 colecção, São Mamede, alfarrabistas, multimotor, SQLite, 3 áreas, paginação UI | 2 |
| 0.3.3_REV2 | 374e235deb | 1013 | P55 colecção, São Mamede, alfarrabistas, multimotor, SQLite, 3 áreas, paginação UI | 3 |
| 0.3.3_REV3 | 42a7f5ed37 | 960 | P55 colecção, São Mamede, alfarrabistas, multimotor, SQLite, 3 áreas, paginação UI | 3 |
| 0.3.3_REV4_CORRECOES_ESTRUTURAIS | aa66a11d52 | 985 | P55 colecção, São Mamede, alfarrabistas, multimotor, SQLite, 3 áreas, paginação UI | 3 |
| 0.3.3_REV5_PRESERVA_PESQUISA | 3189fb725a | 1054 | P55 colecção, São Mamede, alfarrabistas, multimotor, SQLite, 3 áreas, paginação UI | 3 |
| 0.3.3_REV6_P55_CATALOGO_COMPLETO | c67cd36a78 | 1060 | P55 colecção, São Mamede, alfarrabistas, multimotor, SQLite, 3 áreas, paginação UI | 3 |
| 0.3.3_REV7_P55_HTML_FALLBACK | b73171e5ee | 1126 | P55 colecção, São Mamede, alfarrabistas, multimotor, SQLite, 3 áreas, paginação UI | 3 |
| 0.3.3_REV8_CORRECOES_PESQUISA | b9e7172f54 | 1169 | P55 colecção, São Mamede, alfarrabistas, multimotor, SQLite, 3 áreas, paginação UI | 3 |
| 0.3.3_REV9_PAGINACAO_CORRIGIDA | bb8703a7f0 | 1165 | P55 colecção, São Mamede, alfarrabistas, multimotor, SQLite, 3 áreas, paginação UI | 3 |
| ATUALIZADA_KIKI_LIMA_JOAO_CUTILEIRO | 8e20314962 | 679 | P55 colecção, São Mamede, alfarrabistas, só Bing, filtro OLX | 1 |
| Afinada_0.3.1 | e842b34f1c | 852 | P55 suggest, São Mamede, alfarrabistas, multimotor, SQLite, 3 áreas | 1 |
| COM_ALFARRABISTAS | 6510c5ee22 | 447 | P55 suggest, São Mamede, só Bing | 0 |
| CORRIGIDA_FILTRO_LIVROS | 7bc5c038ac | 790 | P55 suggest, São Mamede, alfarrabistas, multimotor, ficha individual | 1 |
| CORRIGIDA_PORTA_8766 | f5781a4c8f | 623 | P55 suggest, São Mamede, alfarrabistas, só Bing, filtro OLX | 1 |
| CORRIGIDO_OLX | 647da872f3 | 488 | P55 suggest, São Mamede, só Bing, filtro OLX | 0 |
| Consolidada_Dev_0.1 | 3248704cc9 | 842 | P55 suggest, São Mamede, alfarrabistas, multimotor, SQLite, 3 áreas | 1 |
| DASHBOARD_TESTE_SEPARADO | 1a9449c1cb | 814 | P55 suggest, São Mamede, alfarrabistas, multimotor, 3 áreas | 1 |
| INTERFACE_FONTES | cedad53fee | 316 | P55 suggest, só Bing | 0 |
| PACOTE_CORRIGIDO | 5ceae215f2 | 339 | P55 suggest, só Bing | 0 |
| RECTIFICADA_v1_1 | 3b092eab3e | 623 | P55 suggest, São Mamede, alfarrabistas, só Bing, filtro OLX | 1 |
| RECUPERADA_MULTIMOTOR | 81d68d6fc0 | 684 | P55 suggest, São Mamede, alfarrabistas, multimotor | 1 |
| Revisao_Tecnica_0.2 | 64fde4ee5f | 856 | P55 suggest, São Mamede, alfarrabistas, multimotor, SQLite, 3 áreas | 1 |
| SAO_MAMEDE_DIRECTO | 529ac700f8 | 411 | P55 suggest, São Mamede, só Bing | 0 |
| VERSAO_CONSOLIDADA | 3b092eab3e | 623 | P55 suggest, São Mamede, alfarrabistas, só Bing, filtro OLX | 1 |
| VERSAO_PARA_TESTE | abffb207e3 | 495 | P55 suggest, São Mamede, só Bing, filtro OLX | 0 |
| VERSAO_PARA_TESTE_1 | abffb207e3 | 495 | P55 suggest, São Mamede, só Bing, filtro OLX | 0 |

Conclusões da comparação:

- **Duplicados exactos:** `VERSAO_PARA_TESTE` = `VERSAO_PARA_TESTE (1)`; `VERSAO_CONSOLIDADA` = `RECTIFICADA_v1_1` (mesmo ficheiro principal); `0.3.3` = `0.3.3_REV1` (mesmo ficheiro principal, a REV1 acrescenta testes).
- **Linha principal:** Consolidada_Dev_0.1 → Revisão Técnica 0.2 → Afinada 0.3.1 → 0.3.2 → 0.3.3 → REV1…REV9. A REV9 contém tudo o que as anteriores tinham (P55 por colecção, São Mamede, alfarrabistas, multimotor, SQLite, três áreas, paginação) e é a melhor base.
- **Funcionalidades que se tinham perdido e foram recuperadas na 0.4.0:**
  - filtro de anúncios do OLX (exigir o artista no título, rejeitar mobiliário/roupa/“compro”), da versão `CORRIGIDO_OLX`;
  - enriquecimento pela ficha individual (og:image, JSON-LD Product, preço), da versão `CORRIGIDA_FILTRO_LIVROS`.
- A PWA `Caca_Arte_App_v0_1` não tem motores; não foi usada.

## 2. Verificação nos sites reais (22-11-2026)

Feita com acesso web de leitura (não a partir do código):

| Fonte | O que se observou | Consequência |
|---|---|---|
| Galeria São Mamede | Página `/listagem/artistas/cruzeiro-seixas` existe, secção “Obras de arte”, ligações `/listagem/obras-de-arte/<slug>`; o texto das ligações **não** contém o nome do artista; sem preços. | **Defeito encontrado:** a REV9 exigia o nome do artista no texto da ligação, por isso nunca encontrava obras. Corrigido. |
| Liliana Queiroz (livrariaalfarrabista.com) | Com `?tipo=pesq&pesq=…` e `?tipo=pesq&query=…` o site responde **“Falta a pesquisa”**. | **Defeito encontrado:** parâmetro errado; a REV9 tratava isto como “zero resultados”. Agora descobre o formulário real e trata “Falta a pesquisa” como erro. |
| Sá da Costa | Site activo; catálogo em `/livros` (paginação `?p=N`), fichas em `/livro/<ref>/<slug>`. Os cartões da listagem não mostram o autor. | Pesquisa por formulário descoberto + confirmação do autor na ficha. |
| OLX | `https://www.olx.pt/ads/q-cruzeiro-seixas/` devolve 285 anúncios relevantes (litografias, serigrafias, livros). A API `/api/v1/offers` está proibida no robots.txt. | Motor **directo** novo pela página pública de pesquisa (não pela API). |
| CustoJusto | `/portugal/q/cruzeiro seixas` devolve 87 anúncios, mas mistura apartamentos e carros. | Motor directo novo com filtro estrito do artista. |
| P55.art | Recusou o acesso de leitura usado nesta verificação (erro do lado do site). | Não foi possível confirmar; fica para o teste real. |
| AbeBooks | Pesquisa proibida no robots.txt. | Mantém-se só por motor de pesquisa. |

## 3. Alterações da 0.4.0

1. `scout_engine/adapters.py` (novo): motores directos OLX, CustoJusto, São Mamede e livrarias com descoberta automática do formulário; leitura robusta de preços (`1 800,00 €`, `€1.250,50`…); enriquecimento pela ficha.
2. OLX e CustoJusto: se o motor directo falhar, recorre ao motor de pesquisa e mostra um **aviso** (não um falso sucesso).
3. Regra das áreas reforçada no servidor: “Todas as fontes” deixou de existir; só área ou fonte individual.
4. Cada resultado tem agora: área, categoria, método de recolha, data de recolha, moeda, identificador do anúncio (OLX/CustoJusto), data de publicação (OLX), estado de validação e `dedup_key`.
5. Deduplicação por URL canónico (sem `www`, sem parâmetros de rastreio), completando campos em falta entre duplicados.
6. Histórico: botão “Histórico guardado”, exportação CSV (Excel) e JSON.
7. Registo `data/scout.log` com cada pedido, estado HTTP e falhas (sem credenciais).
8. “Nova pesquisa” interrompe também a pesquisa no servidor.
9. Corrigido: o cabeçalho `Referer: p55.art` era enviado a todos os sites; a cache HTTP nunca era limpa entre pesquisas.
10. `TESTAR_FONTES.bat` + `diagnostico_fontes.py`: teste real fonte a fonte, relatório e ZIP para enviar.
11. `INSTALAR.bat`: instala tudo e cria atalho. Requisitos reduzidos a `rapidfuzz` (Scrapy/Playwright/Trafilatura não eram usados na pesquisa; ficam em `requirements-opcional.txt`).

## 4. Testes

`python -m unittest test_engine test_p55_connector test_search_parser test_adapters_040`

**34 testes aprovados** (17 antigos + 17 novos). Os novos cobrem: São Mamede com a estrutura real, OLX (estado JSON e HTML alternativo, paginação sem ciclo infinito, filtro de “compro” e mobiliário), CustoJusto (filtro do artista), descoberta de formulário Liliana Queiroz, “Falta a pesquisa” como falha, confirmação do autor na ficha, formatos de preço, regra das áreas, isolamento de falhas, deduplicação e recurso ao motor de pesquisa.

Também testado: arranque do servidor, sintaxe do JavaScript da página, endpoints `/api/start`, `/api/status`, `/api/history`, `/api/export`, `/api/sources` e isolamento de falha com a rede bloqueada.

**Não executado:** pesquisas reais a partir do código (o ambiente de desenvolvimento não tem saída para a Internet). Os testes usam páginas simuladas.

## 5. Estado das fontes

| Estado | Fontes |
|---|---|
| Motor directo, corrigido, **por validar em rede** | P55.art, Galeria São Mamede, OLX, CustoJusto, Manuel Ferreira, Liliana Queiroz, Sá da Costa |
| Motor de pesquisa por domínio (candidatos, sem imagem) | Restantes fontes |
| Identificação a confirmar | CPS (`cps.pt` = Centro Português de Serigrafia?), Galeria 111 (`111.pt`?) |

## 6. Próximo passo para concluir

1. Instalar (`INSTALAR.bat`) e correr `TESTAR_FONTES.bat` no Windows.
2. Enviar o `ENVIAR_diagnostico_….zip`.
3. Com as amostras HTML reais: corrigir as fontes que falharem, criar motores directos para as que só têm candidatos e marcar como “validada” cada fonte que devolver anúncios verificáveis.

Critério de conclusão do projecto: só fica concluído quando as pesquisas reais estiverem testadas e os resultados forem verificáveis.
