# Caça à Arte Scout 0.3.3 REV8, correcções de pesquisa

## Alterações

1. Corrigida a paginação do fallback HTML da P55. A recolha já não termina quando uma página apresenta menos de 12 produtos.
2. A recolha de produtos da P55 passa a procurar endereços de produtos também em atributos de dados e conteúdo JSON/JavaScript escapado.
3. Quando o endpoint público `.js` de um produto falha, a aplicação tenta ler os dados estruturados JSON-LD da página pública do produto.
4. A paginação HTML passa a admitir até 20 páginas e interrompe apenas quando deixa de encontrar novos produtos.
5. A interface identifica as plataformas que terminaram sem resultados e pergunta se devem ser excluídas. Não as exclui automaticamente.
6. Mantida a mesma lógica de pesquisa para todos os artistas da lista.

## Validação

- 17 testes automatizados passaram em Python 3.
- Incluído teste de regressão para páginas HTML com menos de 12 produtos.
- Os testes usam respostas simuladas. A ligação real à P55 e às restantes plataformas não foi validada neste ambiente. A versão deve, por isso, ser considerada uma correcção candidata até ser executada no Windows com acesso à Internet.
