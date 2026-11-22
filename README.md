# Caça à Arte Scout

**Versão documentada: 0.4.5 (22/11/2026)**

Aplicação de pesquisa de oportunidades de arte, livros e artigos usados, com áreas de pesquisa independentes, histórico local e exportação.

## Áreas de pesquisa
- **Arte**
- **Livros**
- **Usados**

As áreas são pesquisadas separadamente. Não existe uma pesquisa global que execute todas simultaneamente.

## Estado da versão 0.4.5
A documentação de versão regista 45 testes automáticos aprovados e melhorias entre 0.4.1 e 0.4.5. Os testes automatizados não substituem a validação das fontes em execução no computador do utilizador.

### Melhorias documentadas
- Correcções de certificados e recolha documentada de 475 obras P55.art.
- Correcção do arranque para encerrar versões anteriores que ocupem a porta 8766.
- Correcção de paginação.
- Adição ou revisão de pesquisa para Underdogs, TwoArt, Centro Português de Serigrafia, Art4All e Culturas Galeria.
- Galeria 111 e In7Artes incluídas como fontes sem venda online.
- Ordenação por preço, data, fonte e título.
- Instalador e lançadores em Python para evitar bloqueios de ficheiros BAT descarregados.

## Instalação e utilização
Consultar [scout/LEIA-ME.txt](scout/LEIA-ME.txt) para instruções completas.

1. Instalar Python, se necessário.
2. Extrair a pasta Scout para um local novo.
3. Executar `INSTALAR_CACA_ARTE_SCOUT.py`.
4. Usar o atalho criado ou executar `ABRIR_CACA_ARTE_SCOUT.py`.
5. A interface abre em http://127.0.0.1:8766.

## Diagnóstico das fontes
Executar `scout/TESTAR_FONTES.py` para realizar testes de pesquisa reais e produzir um relatório diagnóstico. Os resultados dependem da disponibilidade, limitações e políticas de cada fonte.

## Dados
- Histórico local SQLite: `scout/data/scout_results.sqlite3`
- Registo: `scout/data/scout.log`
- Diagnósticos: pasta `diagnostico`

Não apagar a base de dados do histórico sem cópia de segurança.

## Limitações
- Algumas fontes usam motores de pesquisa externos limitados ao domínio.
- Alguns motores podem devolver limites, erros ou resultados incompletos.
- AbeBooks, IberLibro e ZVAB não são recolhidos por acesso automático directo quando as políticas/robots impedem essa recolha.
- Não são contornados logins, CAPTCHA nem bloqueios.
- Não se considera uma fonte operacional apenas por estar registada. Confirmar com diagnóstico real.

## Histórico
- [Alterações 0.4.5](scout/ALTERACOES_0.4.5.md)
- [Relatório técnico 0.4.0 e inventário de versões](scout/RELATORIO_TECNICO_0.4.0.md)
- [Guia de utilização](scout/LEIA-ME.txt)

