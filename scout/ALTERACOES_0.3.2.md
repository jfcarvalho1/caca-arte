# Caça à Arte Scout 0.3.3

## Alteração principal: P55.art

A versão 0.3.1 consultava apenas `search/suggest.json`, o endpoint de pesquisa preditiva Shopify. Esse endpoint devolve uma amostra limitada de produtos e não equivale ao catálogo completo.

A versão 0.3.3 passa a tentar primeiro o endpoint público de produtos da colecção Shopify do artista:

`/collections/{identificador-do-artista}/products.json?limit=250&page=N`

A recolha percorre páginas até encontrar uma página vazia ou incompleta, deduplica produtos por identificador, usa variantes para verificar disponibilidade e mantém preço, imagem e URL do produto. O endpoint `search/suggest.json` fica como fallback quando a colecção não devolve dados.

O filtro por categoria continua activo. Produtos sem variantes disponíveis são excluídos. O envio para Portugal continua identificado como informação a confirmar no checkout, não como dado verificado pela Scout.

## Testes executados

- Compilação do ficheiro principal: passou.
- Testes existentes do motor: 5 passaram.
- Testes novos do conector P55, com respostas Shopify simuladas: 2 passaram.
- Teste de paginação com 251 produtos distribuídos por duas páginas: passou.
- Teste de exclusão de produto sem variante disponível: passou.

**Limitação importante:** os testes do conector P55 foram feitos com respostas simuladas. Nesta execução não foi possível efectuar uma chamada HTTP real ao endpoint da P55 a partir do ambiente de desenvolvimento. Portanto, a alteração está implementada e os testes locais passaram, mas ainda falta validar o endpoint no computador Windows do utilizador, com acesso real à Internet.

## Evidência externa sobre a necessidade da alteração

A página pública da colecção de José de Guimarães apresenta paginação e mais de uma centena de obras, enquanto a versão anterior da Scout consultava apenas a pesquisa preditiva com limite máximo de 50 resultados. Isto confirma que a estratégia anterior podia omitir obras.

## Ficheiros

- `Caca_Arte_Scout.py`: motor principal actualizado.
- `test_p55_connector.py`: testes de paginação e disponibilidade do conector P55.
- Restantes ficheiros: preservados da versão 0.3.1.


## 0.3.3
- Resultados apresentados em páginas de 50 anúncios.
- Controlos Primeira, Anterior, Seguinte e Última quando existem mais de 50 resultados.
- Botão Nova pesquisa limpa os resultados e o campo de artista sem exigir F5.
- Enter no campo de artista inicia a pesquisa.
- Limpeza do estado de paginação ao mudar de área.
- Limite por fonte predefinido em 50.
- Testes de interface limitados a sintaxe e fluxo JavaScript; não representam validação dos catálogos externos.
