# Caça à Arte Scout 0.3.3

## Alterações

1. Os resultados são apresentados em páginas de 50 anúncios.
2. Quando existem mais de 50 resultados, aparecem controlos Primeira, Anterior, Seguinte e Última.
3. O botão Nova pesquisa limpa os resultados, a paginação e o campo de artista, permitindo pesquisar outro autor sem F5.
4. A tecla Enter no campo de artista inicia a pesquisa.
5. Ao mudar de área, a paginação e os resultados anteriores são limpos.
6. O limite predefinido de resultados por fonte passa para 50.

## Testes realizados

- Compilação Python: aprovada.
- test_engine.py: 5 testes aprovados.
- A paginação é feita sobre os resultados devolvidos pelo motor. Não aumenta, por si só, o número recolhido em cada fonte.
- Não foram realizados nesta versão testes reais de integração às 70 fontes.
