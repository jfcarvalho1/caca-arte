# Caça à Arte Scout 0.3.3 REV3
## Correcção do parser dos motores de pesquisa

### Alterações
- Substituída a extracção exclusivamente dependente de classes HTML rígidas por uma estratégia em duas fases.
- Mantida a extracção específica de Bing, DuckDuckGo e Brave quando os marcadores conhecidos existem.
- Acrescentada passagem alternativa por âncoras HTML quando os marcadores específicos não são reconhecidos.
- As ligações são filtradas pelo domínio exacto da fonte seleccionada, incluindo subdomínios.
- Desembrulhadas ligações de redireccionamento `uddg` do DuckDuckGo.
- Identificadas páginas de CAPTCHA/bloqueio como falhas explícitas.
- Deduplicação de ligações por URL canónica simples.

### Testes executados
`python -m unittest test_engine test_p55_connector test_search_parser -v`

Resultado: 10 testes aprovados.

Os três testes novos verificam:
1. Fallback de âncoras quando a estrutura do Bing muda.
2. Desembrulhamento de redireccionamentos DuckDuckGo.
3. Rejeição de resultados fora do domínio da fonte.

### Limitações que permanecem
- HTTP 429 do Brave não é resolvido por um parser. É necessário respeitar o limite de pedidos e voltar a tentar mais tarde.
- Os testes de parser usam HTML controlado e não comprovam que os motores externos aceitam pedidos reais nesta sessão.
- Esta revisão não transforma automaticamente todas as fontes registadas em conectores directos. As fontes `domain_search` continuam dependentes de motores externos.
- Não foi possível confirmar recolha real de anúncios da P55.art, galerias, livrarias, OLX ou outras plataformas nesta execução.

### Instalação
Extrair para uma pasta nova, mantendo a versão anterior intacta. Usar o ambiente virtual existente e iniciar com `INICIAR_CACA_ARTE_SCOUT.bat`.
