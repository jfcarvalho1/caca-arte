# Estado de continuidade, Caça à Arte Scout

**Actualização documental: 22/11/2026**

## Base actual
- Código e pacote documentados: Scout 0.4.5.
- Base de desenvolvimento: 0.3.3 REV9.
- Código da aplicação e módulos de motores, histórico SQLite, normalização, adaptadores, testes, instalador e documentação estão no repositório.
- O pacote ZIP 0.4.5 está arquivado em `versoes/Caca_Arte_Scout_0.4.5.zip`.

## Testes e validação
A documentação da 0.4.5 indica 45 testes automáticos aprovados e verificações de paginação e ordenação em Chrome sem interface. Não equivale a validação de todas as fontes em pesquisa real no computador do utilizador.

## Fontes e limites
A versão distingue motores directos e fontes que recorrem a pesquisa externa por domínio. As fontes registadas com estado `not_validated` em `scout_engine/sources.json` não devem ser apresentadas como validadas.

## Prioridades de continuidade
1. Executar `TESTAR_FONTES.py` no Windows do utilizador e preservar o ZIP diagnóstico.
2. Analisar fonte a fonte os resultados, erros, bloqueios e falsos positivos.
3. Corrigir adaptadores de fontes com falhas, sem contornar CAPTCHA, autenticação ou bloqueios.
4. Confirmar separação das três áreas de pesquisa.
5. Confirmar persistência, exportação e deduplicação com testes e utilização real.
6. Manter backups e versões anteriores intactas.

## Preservação
Não substituir ZIPs antigos nem histórico de pesquisa. Criar versões novas e manter registos de alterações.
