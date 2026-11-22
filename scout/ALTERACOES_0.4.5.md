# Caça à Arte Scout 0.4.5 (22-11-2026)

Resumo das versões 0.4.1 a 0.4.5, feitas com base nos registos reais do PC do utilizador:

- 0.4.1/0.4.2 P55.art: o Python do Windows recusava o certificado ("certificate has expired") e o erro ficava escondido. Agora usa certifi e o verificador do Windows (truststore); a verificação nunca é desligada. Resultado real: 475 obras P55 recolhidas.
- 0.4.2 Ao arrancar, fecha a versão antiga que tenha ficado aberta na porta 8766.
- 0.4.3 Paginação: deixava de funcionar durante a pesquisa (voltava sempre à página 1). Corrigido; paginação também no topo.
- 0.4.4 Motores directos de galerias, verificados nos sites reais: Underdogs (Shopify), TwoArt (WooCommerce), Centro Português de Serigrafia, Art4All, Culturas Galeria; Galeria 111 e In7Artes como galerias sem venda online. Oito galerias com endereço que não abre retiradas da pesquisa (lista em DISABLED_SOURCES).
- 0.4.5 Ordenação dos resultados: preço crescente/decrescente, data mais recente/mais antiga (publicação ou primeira vez que a Scout viu o anúncio), fonte, título. Instalador e iniciadores em Python (.py): o Controlo Inteligente de Aplicações do Windows bloqueia .bat descarregados.

Testes: 45 testes automáticos aprovados; ordenação e paginação verificadas em Chrome sem interface.
