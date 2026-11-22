# REV9, correcção da paginação da interface

Os botões Primeira, Anterior, Seguinte e Última chamam agora directamente a função showPage() através de onclick. Foi removida a dependência do listener delegado no elemento de paginação. Mantém-se a paginação local dos resultados recolhidos, com 50 anúncios por página.

Validação: compilação sintáctica do ficheiro Python e verificação do bloco JavaScript. A interacção no browser Windows ainda necessita de confirmação na aplicação em execução.
