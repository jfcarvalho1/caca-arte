# Caça à Arte Scout, REV4 correcções estruturais

## Correcções incluídas

1. Paginação interna: removidos os `onclick` inline regenerados; a navegação usa delegação de eventos, validação numérica e limites de página. Primeira, Anterior, Seguinte e Última apontam para páginas calculadas a partir do total real recolhido.
2. Estado das pesquisas: a interface distingue conclusão com falhas e indica quantas consultas terminaram sem erro e quantas falharam. Não apresenta uma conclusão limpa quando existem fontes com falhas.
3. Parser externo: respostas sem resultados e sem estrutura reconhecível passam a produzir erro de formato, em vez de serem automaticamente tratadas como pesquisa válida sem resultados. Respostas com âncoras mas apenas ligações fora do domínio continuam a ser tratadas como zero correspondências para esse domínio.
4. Arranque Windows: o BAT procura o Python no ambiente virtual local, em `%USERPROFILE%\\Desktop\\Arte\\.venv` e em localizações superiores habituais, sem exigir uma profundidade fixa.
5. SQLite: a ligação passa a ser fechada garantidamente através de context manager, evitando ligações abertas durante o ciclo de vida da aplicação.

## Testes executados

Executado `python -m unittest test_engine test_p55_connector test_search_parser -v`.
Resultado: 10 testes aprovados.

## Limitações que permanecem

- Os testes são automatizados e incluem respostas simuladas. Não comprovam que Bing, DuckDuckGo, Brave ou cada plataforma respondam correctamente em produção.
- As 65 fontes `domain_search` continuam a depender de motores externos, não são 65 conectores directos.
- HTTP 429, CAPTCHA, alterações de HTML e restrições das plataformas podem impedir consultas.
- A paginação interna percorre os resultados recolhidos pela Scout. Não implementa automaticamente paginação específica de todas as plataformas de origem.
- As fontes candidatas P55.art, São Mamede e alfarrabistas precisam de validação real individual.

Esta versão não deve ser considerada final até serem efectuadas pesquisas reais e verificadas nas três áreas.
