# Caça à Arte Scout 0.3.1, revisão incremental

## Alterações desta revisão
- A lista de variantes de pesquisa passou a abranger os 13 artistas definidos no projecto, com normalização de acentos e capitalização.
- A pesquisa P55.art passou a consultar as variantes normalizadas de cada artista, não apenas José de Guimarães e João Cutileiro.
- Removida a rejeição rígida dos resultados P55 quando o nome do artista não aparece no título ou na descrição curta. O catálogo pode devolver o produto pela pesquisa do autor, mesmo quando a ficha omite o nome.
- A pesquisa externa por domínio passou a usar as variantes do artista em vez de ter sinónimos codificados apenas para dois nomes.
- Acrescentado teste automático que verifica a cobertura das variantes dos 13 artistas.

## Testes executados nesta revisão
- `python -m unittest -v`: 5 testes aprovados.
- Compilação sintáctica de `Caca_Arte_Scout.py` e dos módulos: aprovada.
- Não foram executadas pesquisas HTTP em plataformas externas neste ambiente. Portanto, não se declara validada a recolha real nem a paginação da P55 ou das restantes fontes.

## Limitações que permanecem
- A maioria das 66 fontes continua a usar pesquisa externa por domínio, não conectores próprios.
- O endpoint Shopify Predictive Search da P55 pode limitar o número de resultados; a paginação integral do catálogo não está demonstrada nesta versão.
- Imagens, preço, stock, envio e URL de cada anúncio dependem dos dados devolvidos por cada fonte e carecem de validação real.
- Fontes com bloqueio, autenticação ou ausência de catálogo pesquisável devem ser assinaladas como condicionadas, não como resultados vazios definitivos.

## Instalação
Substituir a pasta da versão anterior pela pasta incluída neste ZIP, mantendo uma cópia de segurança. O BAT aponta para o ambiente virtual externo já utilizado em `C:\Users\JFC\Desktop\Arte\.venv`.
