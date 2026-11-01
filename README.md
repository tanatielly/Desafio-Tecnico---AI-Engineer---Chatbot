# Empório da Música — Agente de Atendimento

Protótipo de um agente de atendimento por mensagens de texto para a **Empório da Música**,
loja fictícia de instrumentos musicais em Campo Grande/MS (desafio técnico AI Engineer — Artefact).

O agente se chama **Allegro** (o andamento musical "alegre e animado") e atende clientes respondendo sobre produtos, preços, estoque, promoções,
status de pedidos e políticas da loja (horário, pagamento, trocas, frete, garantia...).
Ele decide sozinho quando precisa consultar os **dados** (CSVs) e quando precisa consultar as
**políticas** (PDF), e recusa com educação o que está fora do escopo da loja.

- Linguagem: Python
- LLM: **Ollama local com Qwen 2.5 7B** (open source), com opção de usar o **Groq** (free tier) só mudando o `.env`
- Abordagem: **function calling** (sem framework de agentes)
- Interfaces: **terminal (CLI)** e **web com Streamlit**

---

## Sumário

1. [Como funciona](#como-funciona)
2. [Como rodar](#como-rodar)
3. [Estrutura do projeto](#estrutura-do-projeto)
4. [Decisões técnicas](#decisões-técnicas)
5. [Tratamento dos dados](#tratamento-dos-dados)
6. [Suposições](#suposições)
7. [Exemplos de conversa](#exemplos-de-conversa)
8. [Limitações conhecidas](#limitações-conhecidas)
9. [O que eu faria com mais tempo](#o-que-eu-faria-com-mais-tempo)
10. [Uso de assistentes de código](#uso-de-assistentes-de-código)

---

## Como funciona

```
Cliente ──> main.py (terminal) ou app_streamlit.py (web)
                │
                ▼
            agente.py ── prompt do Allegro + histórico + lista de ferramentas ─> LLM (Ollama ou Groq)
                ▲                                                                    │
                │                   o LLM pede uma ferramenta (tool call)            │
                └──── ferramentas.py <───────────────────────────────────────────────┘
                        ├─ buscar_produtos      → dados.py      (CSVs de produtos, categorias e promoções)
                        ├─ consultar_pedido     → dados.py      (CSVs de pedidos, itens e clientes)
                        ├─ consultar_politicas  → politicas.py  (PDF separado por seção)
                        └─ encaminhar_atendente → atendimentos/encaminhamentos.csv
```

1. O cliente manda uma mensagem.
2. O agente envia para o LLM: o prompt de sistema (persona + regras + data/hora atual), o histórico e a descrição das 4 ferramentas.
3. Se o LLM pedir uma ferramenta, o Python executa e devolve o resultado em JSON. Isso se repete (no máximo 5 vezes por mensagem).
4. Quando o LLM responde em texto, essa é a resposta para o cliente.

### Ferramentas

| Ferramenta | Quando o agente usa | O que faz |
|---|---|---|
| `buscar_produtos` | preço, estoque, disponibilidade, promoções | Filtra o catálogo por texto, categoria, preço máximo e promoção. Já devolve preço promocional, preço no PIX e parcelamento calculados. Separa produtos disponíveis dos esgotados/descontinuados e, se o produto procurado estiver indisponível, já sugere alternativas parecidas. |
| `consultar_pedido` | status, rastreio, prazos de um pedido | Só mostra o pedido se o e-mail ou telefone informado for do dono do pedido (LGPD). Calcula se está atrasado e se está dentro dos prazos de arrependimento/troca/garantia, e já traz as regras de devolução do manual que valem para o pedido. |
| `consultar_politicas` | endereço, horário, pagamento, trocas, frete, promoções, garantia, privacidade | Recebe um assunto (`loja_contato_e_horario`, `pagamento`, `trocas_e_devolucoes`, `frete_e_entrega`, `promocoes`, `garantia`, `privacidade`) e devolve o texto da seção do manual. |
| `encaminhar_atendente` | reclamação, atraso, cliente pedindo um humano | Registra o caso em `atendimentos/encaminhamentos.csv` e devolve um protocolo (`EM-AAAAMMDD-HHMMSS`), que sempre aparece na resposta ao cliente. |

---

## Como rodar

Testado no Windows 11 com Python 3.13. Precisa de Python 3.10 ou mais novo.

### 1. Instalar as dependências

```bash
git clone https://github.com/tanatielly/Desafio-Tecnico---AI-Engineer---Chatbot.git
cd Desafio-Tecnico---AI-Engineer---Chatbot

python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # Linux / Mac

pip install -r requirements.txt
```

### 2. Configurar o modelo

**Opção A — Ollama (padrão, roda local e é gratuito)**

1. Instale o Ollama: https://ollama.com/download (no Windows também dá com `winget install Ollama.Ollama`)
2. Baixe o modelo e crie a versão com contexto maior (ver [Modelfile](Modelfile)):

```bash
ollama pull qwen2.5:7b
ollama create emporio-qwen2.5 -f Modelfile
```

3. Copie o arquivo de configuração (os valores padrão já apontam para o Ollama):

```bash
cp .env.example .env          # Linux / Mac / Git Bash
copy .env.example .env        # Windows (cmd)
```

**Opção B — Groq (free tier, bem mais rápido se a máquina não tiver GPU)**

1. Crie uma chave gratuita em https://console.groq.com/keys
2. No `.env`, comente as linhas do Ollama e descomente as do Groq, colocando sua chave:

```
LLM_BASE_URL=https://api.groq.com/openai/v1
LLM_MODEL=llama-3.3-70b-versatile
LLM_API_KEY=sua_chave_aqui
```

**Opcional:** `DATA_REFERENCIA=2026-03-25` no `.env` faz o agente considerar essa data como "hoje".
Os pedidos dos CSVs vão só até março/2026, então com a data real todos os prazos já teriam vencido.
Os exemplos deste repositório foram gerados com essa data.

### 3. Conversar com o Allegro

```bash
# terminal
python main.py

# navegador (abre em http://localhost:8501)
streamlit run app_streamlit.py
```

No terminal, `sair` encerra e `limpar` começa uma conversa nova. Cada conversa é salva em `conversas/`.
As ferramentas chamadas aparecem na tela (`[ferramenta] ...`), para dar para acompanhar o raciocínio do agente.

Também dá para rodar um roteiro pronto (uma mensagem por linha), no cmd ou bash:

```bash
python main.py < exemplos/roteiros/03_devolucao_pedido.txt
```

### 4. Testes

```bash
pytest
```

Os testes cobrem as ferramentas (preço, promoção, PIX, parcelamento, verificação do pedido, prazos, regras de devolução, protocolo, extração das políticas) e partes do agente (horário da loja, protocolo e a trava de encaminhamento, usando um cliente falso no lugar do LLM). Nenhum teste chama o LLM de verdade.

---

## Estrutura do projeto

```
├── data/                     CSVs e PDF de políticas fornecidos pela loja
├── dados.py                  carrega e trata os CSVs
├── politicas.py              lê o PDF e separa por seção
├── ferramentas.py            as 4 ferramentas + descrição delas para o LLM
├── agente.py                 prompt do Allegro e o loop de function calling
├── main.py                   interface de terminal
├── app_streamlit.py          interface web
├── Modelfile                 qwen2.5:7b com contexto de 8192 tokens (Ollama)
├── tests/                    testes das ferramentas e do agente (sem LLM)
├── exemplos/                 conversas de exemplo + roteiros usados para gerar
├── .env.example              configuração do modelo
└── requirements.txt
```

---

## Decisões técnicas

### Abordagem: function calling, sem framework

Escolhi **function calling** porque a maior parte das perguntas é sobre **dados estruturados** (preço,
estoque, status de pedido). Para isso, um filtro exato em pandas é mais confiável do que busca semântica:
"violões até R$ 1000" precisa de `preço <= 1000`, não de "textos parecidos".

O LLM fica responsável por **entender a pergunta, escolher a ferramenta e escrever a resposta**.
O Python fica responsável por **buscar e calcular**.

Não usei LangChain/LlamaIndex porque o loop de function calling tem umas 60 linhas
([agente.py](agente.py)) e fica mais fácil de entender, depurar e explicar. Um framework faria sentido
se o projeto crescesse (mais ferramentas, memória longa, vários agentes).

Também descartei um **agente de SQL** (LLM escrevendo consultas): com modelos pequenos ele erra bastante,
e deixar o LLM consultar livremente a tabela de clientes seria um risco de vazar dados pessoais.
Com ferramentas fechadas, o agente só consegue ver o que a ferramenta deixa.

### Políticas: seções do PDF em vez de RAG com embeddings

O manual tem 8 páginas e já é dividido em seções numeradas (horário, pagamento, trocas, frete...).
Então o [politicas.py](politicas.py) extrai o texto com `pypdf`, separa por seção, e a ferramenta
`consultar_politicas` recebe o **assunto** (um enum) e devolve a seção inteira.

Por que não embeddings + banco vetorial:
- Com ~10 seções, quebrar em chunks e buscar por similaridade é complexidade sem ganho; a seção inteira cabe no contexto.
- A seção inteira traz todas as regras juntas (ex.: arrependimento + troca por defeito + itens não elegíveis), o que evita respostas com metade da regra.
- Funciona igual com qualquer provedor, sem precisar de um modelo de embeddings.

Se o manual crescer para dezenas de páginas, aí sim vale migrar para RAG vetorial (ver "com mais tempo").

A seção 7 (diretrizes de atendimento) não vira ferramenta: ela é instrução para a equipe, então virou o **prompt de sistema** do Allegro.

### Contas no Python, não no LLM

Preço promocional, preço no PIX (5%), parcelamento máximo, atraso de entrega e prazos de devolução são
calculados nas ferramentas. Modelos pequenos erram bastante em aritmética e em contas com datas, e
preço errado em atendimento pode configurar propaganda enganosa (o próprio manual fala disso).

### Modelo e provedor

- **Ollama + Qwen 2.5 7B (padrão):** open source, gratuito, roda local (nenhum dado de cliente sai da máquina) e o Qwen 2.5 tem bom suporte a tool calling e a português.
- **Groq (opcional):** usei o cliente `openai` apontando para a API compatível com OpenAI, que tanto o Ollama quanto o Groq oferecem. Assim a troca de provedor é só no `.env`, sem mudar código. O Groq tem free tier e roda modelos abertos (ex.: Llama 3.3 70B) muito mais rápido.
- **Testei o Qwen 2.5 3B** para ganhar velocidade, mas ele listou produtos esgotados como disponíveis e ignorou regras do prompt, então fiquei com o 7B.
- **Contexto:** o padrão do Ollama é 4096 tokens, e só o prompt + ferramentas já usam ~1600. Criei um [Modelfile](Modelfile) com `num_ctx 8192` para a conversa não "empurrar" o prompt de sistema para fora.
- `temperature=0` para respostas mais previsíveis (com 0.2 o modelo às vezes pulava a ferramenta e inventava dados).

### Estratégia de prompt

O prompt de sistema ([agente.py](agente.py)) é dividido em blocos curtos:
- **Persona:** Allegro, nome tirado do andamento musical que significa "alegre, animado", para combinar com uma loja de instrumentos. Informal mas profissional, "como um amigo que entende de música" (seção 7.1 do manual), respostas curtas no estilo WhatsApp.
- **Quando usar cada ferramenta:** regra explícita de nunca falar preço/estoque/prazo sem consultar.
- **Regras de atendimento** tiradas do manual: não prometer promoção que não está ativa, mostrar preço original + % + preço final, PIX não acumula com promoção, sugerir alternativas para produto esgotado.
- **Escopo:** só instrumentos (acessórios são redirecionados) e recusa gentil de assuntos fora da loja.
- **Dados corrigidos:** as divergências do manual (ver [Suposições](#suposições)).
- **Agora:** data/hora atual e se a loja está aberta. Se estiver fechada, o Allegro avisa quando a equipe volta (o manual pede isso). O cálculo de aberto/fechado é feito em Python.

As descrições das ferramentas também fazem parte da estratégia: elas dizem **quando** usar cada uma
(ex.: "só chame `consultar_pedido` depois que o cliente informar o número E o e-mail ou telefone").

### Segurança / LGPD

O agente só mostra dados de um pedido se o cliente informar o **número do pedido e o e-mail ou telefone**
do cadastro. A verificação é feita no Python (não depende do LLM "obedecer"). A resposta da ferramenta
traz só o primeiro nome do cliente, sem telefone, e-mail ou cidade.

Também existe uma trava para o agente não **prometer uma ação que não fez**: se ele disser que encaminhou
o caso para a equipe (ou citar um protocolo) sem ter chamado a ferramenta de encaminhamento, o código
não deixa essa resposta chegar ao cliente (ver [O que os testes com o modelo mostraram](#o-que-os-testes-com-o-modelo-mostraram)).

### Interface

- **CLI** ([main.py](main.py)): o mais simples, e aceita roteiros via arquivo, o que usei para gerar os exemplos.
- **Streamlit** ([app_streamlit.py](app_streamlit.py)): uma tela de chat para quem prefere testar no navegador. Tem a opção de mostrar quais ferramentas foram chamadas em cada resposta.

As duas usam a mesma classe `Agente`.

### Histórico da conversa

- **Durante a conversa:** o histórico fica em memória e é enviado ao LLM a cada mensagem, então o cliente pode dizer "e no PIX?" sem repetir o produto. Para não estourar o contexto, só as últimas 30 mensagens são enviadas (sempre cortando no início de uma mensagem do cliente, para não separar uma chamada de ferramenta do seu resultado).
- **Depois da conversa:** a transcrição é salva em `conversas/` (markdown), o que serve para a equipe revisar os atendimentos.
- **Não** retomo conversas antigas: num atendimento por mensagem cada conversa costuma ser independente, e reabrir histórico exigiria identificar o cliente de forma segura, o que vai além do protótipo.

---

## Tratamento dos dados

Olhando os dados encontrei várias inconsistências. O que fiz com cada uma:

**Produtos (65 itens)**
- As categorias *Instrumentos de Sopro (Madeiras e Metais)* e *Cordas Orquestrais* existem, mas não têm nenhum produto. O agente responde com base no que existe no catálogo.
- **Nos Baixos, Baterias e Teclados (ids 135 a 144) a descrição não bate com o nome do produto.** Ex.: "Music Man Bass 1X" está descrito como "Fender Jazz Bass"; "Korg Synth 1 Pro" está descrito como "workstation Roland com 88 teclas", mas as specs dizem 61 teclas. Para não passar informação errada para o cliente, **a descrição dessas 3 categorias é ignorada** (o agente usa nome, preço e specs).
- Produtos com status `discontinued` (ids 113 e 136), `coming_soon` (id 130) ou estoque zero (id 96) **não são oferecidos para compra**. A busca devolve eles numa lista separada (`produtos_indisponiveis`), para o agente avisar e sugerir alternativas. Fiz essa separação depois de ver o modelo oferecendo produto esgotado quando vinha tudo misturado.
- Até 2 unidades em estoque aparece como "últimas unidades". O número exato de estoque não é mostrado.
- A coluna `specs` é um JSON em texto e com formatação diferente entre as linhas; converto para dicionário.
- A busca por texto ignora acentos e maiúsculas, e dá prioridade aos produtos que batem mais palavras (assim "Takamine GD20" traz só o GD20, e não todos os Takamine).

**Promoções**
- São 25 promoções, mas só **4 estão ativas** (produtos 90, 94, 121 e 127). A tabela não tem datas, então uso só o `is_active`.
- Alguns produtos têm mais de uma promoção (93, 96, 99), todas inativas. Se algum dia tiver duas ativas para o mesmo produto, fica a de maior desconto, porque promoções não acumulam (seção 6.2).

**Pedidos**
- Os totais dos pedidos 3 (2 × R$ 1.749 = R$ 3.498, registrado R$ 3.450) e 20 (R$ 799 + R$ 689 = R$ 1.488, registrado R$ 1.400) não batem com os itens. Pode ser desconto ou frete não registrados, então o agente informa o **total registrado** e não recalcula.
- O pedido 3 foi entregue com um produto que está como "em breve" (id 130).
- Os pedidos 9 e 16 foram parcelados em 6x com parcela abaixo de R$ 80 (contra a regra 3.1), e o pedido 1 foi pago no PIX sem os 5% de desconto. Não interfere no atendimento, mas fica o registro.
- Pedidos ainda não enviados não têm rastreio nem previsão; trato esses campos vazios.
- O pedido 8 está "enviado" com previsão de entrega já vencida. A ferramenta marca isso como **atrasado** e o agente oferece encaminhar para a equipe.

**Clientes**
- Os clientes 11 e 43 têm o **mesmo e-mail**. Como a verificação do pedido compara com o dono daquele pedido específico, isso não gera ambiguidade.
- Telefones são comparados só pelos dígitos, então "(67) 99654-7821", "67996547821" e "99654-7821" funcionam.

**Manual de políticas (PDF)**
- A extração padrão do `pypdf` quebrava cada palavra numa linha; usei o modo `layout` e limpei cabeçalho, rodapé, marcadores e colunas de tabela.

---

## Suposições

Pontos ambíguos ou contraditórios e a decisão que tomei:

| Ponto | Decisão |
|---|---|
| WhatsApp aparece como (67) 3341-4444 (capa e seção 1.2) e como (67) 3321-4500 (seção 7). | Usei **(67) 3341-4444**, que aparece em mais lugares e está nos "Dados da Empresa". |
| E-mail aparece como `contato@empóriodamusica.com.br` (com acento, inválido) na tabela. | Usei `contato@emporiodamusica.com.br`, da capa. |
| A tabela de pagamento diz "cartão até 12x, parcela mínima R$ 100", mas a seção 3.1 tem regras por faixa. | Usei as regras da **3.1**, que são mais detalhadas. |
| "Até 3x sem valor mínimo de parcela (exceto abaixo de R$ 50,00)". | Interpretei como **parcela mínima de R$ 50** para 2x e 3x. |
| Não existe data real de recebimento do pedido. | Uso a **previsão de entrega** como aproximação para contar os prazos de arrependimento (7 dias) e garantia (90 dias). A troca por defeito (30 dias) conta da data da compra, como diz o manual. |
| Os dados vão até março/2026. | Criei a variável opcional `DATA_REFERENCIA` para simular a data de "hoje". Sem ela, o agente usa a data real. |
| Feriados não estão listados no manual. | O cálculo de loja aberta/fechada considera só o dia da semana. |
| Promoções não têm data de validade. | Vale o `is_active`. Campanhas do calendário (ex.: Black Friday em novembro) só são citadas se estiverem ativas no sistema. |

---

## Exemplos de conversa

Conversas reais com o agente (Qwen 2.5 7B no Ollama, `DATA_REFERENCIA=2026-03-25`), salvas em [exemplos/](exemplos/).
As linhas com 🔧 mostram as ferramentas que o agente chamou. Os roteiros usados estão em [exemplos/roteiros/](exemplos/roteiros/).

| # | Conversa | O que mostra |
|---|---|---|
| 1 | [Violões até R$ 1000](exemplos/01_catalogo.md) | Busca com filtro de categoria e preço, só com itens disponíveis, e recomendação para iniciante usando o histórico da conversa. |
| 2 | [Preço do Takamine GD20](exemplos/02_preco_e_pagamento.md) | Preço, preço no PIX e parcelamento calculados pela ferramenta. |
| 3 | [Devolução de pedido atrasado](exemplos/03_devolucao_pedido.md) — **não trivial** | Pede número do pedido + e-mail antes de consultar (LGPD), consulta o pedido em tempo real, aplica a regra de arrependimento a um pedido que ainda não chegou, explica as condições de devolução (embalagem, reembolso no cartão de débito em até 10 dias úteis) e encaminha o atraso para a equipe com protocolo (registro em `atendimentos/encaminhamentos.csv`). |
| 4 | [Endereço, horário e fora do escopo](exemplos/04_loja_e_fora_do_escopo.md) | Consulta às políticas, recusa educada de acessórios e de assunto que não tem a ver com a loja. |
| 5 | [Black Friday e produto esgotado](exemplos/05_promocao_e_esgotado.md) — **não trivial** | Não promete campanha que não está ativa, mostra as promoções reais (preço original, % e preço final) e sugere alternativas para um produto esgotado. |

### O que os testes com o modelo mostraram

Rodando os roteiros com o Qwen 2.5 7B apareceram erros que os testes unitários não pegavam. Em quase todos
a correção foi **no código da ferramenta** e não só no prompt, porque o modelo pequeno nem sempre obedece
uma instrução, mas sempre recebe o que a ferramenta devolve.

| O que aconteceu | Correção |
|---|---|
| Com o Qwen **3B**, listou produtos esgotados e descontinuados dizendo que "todos estão disponíveis". | A busca passou a devolver `produtos_disponiveis` e `produtos_indisponiveis` separados, e fiquei com o 7B. |
| Pedido enviado e atrasado: disse que "o prazo de 7 dias para desistir já terminou" (ele nem começou, porque o cliente não recebeu). | O campo `prazos` ficou explícito ("AINDA NÃO COMEÇOU..."), removi um campo de dias que confundia o modelo e o prompt manda consultar a política de trocas nesses casos. |
| "Qual o endereço? Vocês abrem sábado?": consultou só a seção da loja e respondeu que **não abre sábado** (abre das 9h às 13h). | Juntei endereço e horário num assunto só (`loja_contato_e_horario`) e o prompt pede para consultar cada assunto de perguntas compostas. |
| "Tem promoção de Black Friday?": chamou as promoções "Oferta Especial" e "Desconto Exclusivo" de Black Friday. | Com `apenas_promocao`, a busca devolve os nomes das campanhas ativas e um aviso de que qualquer outra campanha não está ativa. |
| Produto esgotado: só perguntava se o cliente queria alternativas, sem buscar nenhuma. | Quando o produto procurado está indisponível, a busca já devolve até 3 alternativas da mesma categoria e faixa de preço. |
| Disse "encaminhando seu caso para a equipe" **sem chamar** a ferramenta de encaminhamento, e não consultou a política de trocas. | O resultado da `consultar_pedido` traz `proximos_passos` (consultar a política de trocas; oferecer encaminhamento se atrasado) e o prompt só permite dizer que encaminhou depois de receber o protocolo. |
| Depois de trocar o nome do agente de "Tom" para "Allegro" (com uma frase a mais sobre a personalidade), ele respondeu "qual o endereço?" **sem chamar nenhuma ferramenta** e inventou endereço e horário. | Reforcei no prompt que ele não sabe nada da loja de cabeça e precisa chamar a ferramenta antes de responder, encurtei a frase da persona e passei para `temperature=0`. Mostrou como o modelo pequeno é sensível a mudanças pequenas no prompt. |

| Mesmo com o prompt pedindo, disse "Encaminhando seu caso... o número do protocolo é ANA-26032026-1" **sem chamar a ferramenta**: inventou o protocolo e o caso não foi registrado. | Coloquei uma **trava no código** ([agente.py](agente.py)): se a resposta afirma que encaminhou ou cita um protocolo, mas a ferramenta não foi chamada, o agente pede de novo ao modelo oferecendo **só a ferramenta de encaminhamento** (só o aviso não bastava: com as 4 ferramentas na lista ele continuava inventando). Se mesmo assim ele não chamar, o cliente recebe uma resposta honesta com o WhatsApp da loja em vez da promessa falsa. Esse fluxo tem teste com um cliente falso, sem LLM. |

| Explicava o prazo de devolução, mas **não detalhava as condições** (embalagem original, frete por conta da loja, reembolso em até 10 dias úteis), porque não fazia a segunda chamada para a política de trocas. E **não informava o número do protocolo** do encaminhamento, mesmo com o prompt pedindo. | A `consultar_pedido` passou a devolver as regras de devolução do manual (seção 4.1, e 4.2 para pedido entregue) e para qual forma de pagamento o reembolso volta, sem precisar de outra chamada. O protocolo é garantido no código: se o caso foi encaminhado e o número não está na resposta, ele é acrescentado no final. |

Os exemplos foram gerados de novo depois dessas correções. A última correção não mexeu no prompt e só afeta conversas sobre pedidos e encaminhamento, então só o exemplo 3 precisou ser gerado de novo.

---

## Limitações conhecidas

- **Velocidade no Ollama sem GPU:** na minha máquina (Intel Core 7 150U, 16 GB de RAM, sem GPU) cada resposta levou de 1 a 4 minutos, e cada conversa de exemplo (2 ou 3 mensagens) levou de 5 a 10 minutos. Respostas que usam ferramenta fazem duas chamadas ao modelo, e listas longas de produtos demoram mais para gerar. Com GPU ou com o Groq isso deve cair para poucos segundos.
- **Modelo pequeno ainda erra às vezes:** apesar das correções, o 7B nem sempre segue todas as instruções e é sensível a mudanças pequenas no prompt (ver a tabela acima). Com `temperature=0` os 5 roteiros ficaram corretos, mas outras formas de perguntar podem fazer ele pular uma ferramenta. No exemplo 3, ele explica a embalagem e o reembolso, mas não menciona que o frete de devolução é por conta da loja, mesmo com a regra vindo no resultado da ferramenta. A parte crítica (preços, estoque, prazos, verificação do pedido, encaminhamento) fica no Python justamente para reduzir esse risco. Um modelo maior (ex.: Llama 3.3 70B no Groq) deve seguir melhor o prompt.
- **Groq não testado:** o código usa a mesma API, mas eu só rodei os testes de ponta a ponta com o Ollama.
- **Verificação do cliente é simples:** número do pedido + e-mail/telefone. Quem souber esses dados de outra pessoa consegue ver o pedido. Num canal real (WhatsApp) o telefone viria do próprio canal.
- **Dados estáticos:** os CSVs são carregados quando o programa inicia; mudanças nos arquivos só valem depois de reiniciar.
- **Busca por texto simples:** não entende sinônimos ("violão de aço" funciona porque está na descrição, mas erros de digitação no nome do produto podem não achar nada).
- **Encaminhamento é só um CSV:** não existe integração com um sistema de tickets de verdade.
- **Prazos aproximados:** usam a previsão de entrega, porque não existe a data real de recebimento.
- **Sem avaliação automática:** a qualidade das respostas foi verificada manualmente nos roteiros, não com um conjunto de testes do LLM.

## O que eu faria com mais tempo

- **Avaliação automática do agente:** um conjunto de perguntas com respostas esperadas (ferramenta certa, valores certos) rodando a cada mudança de prompt ou modelo, e comparando modelos (Qwen 7B, Llama 3.3 70B no Groq etc.).
- **RAG vetorial** se o manual de políticas crescer, com embeddings locais (ex.: `nomic-embed-text` no Ollama) e chunks por subseção.
- **Integração com WhatsApp** (que é o canal principal da loja), usando o telefone do próprio canal para identificar o cliente.
- **Banco de dados** (SQLite/Postgres) no lugar dos CSVs, com estoque e pedidos atualizados em tempo real.
- **Histórico persistente por cliente** (com consentimento), para retomar conversas.
- **Busca de produtos melhor**, tolerante a erros de digitação (fuzzy matching) e com sinônimos.
- **Handoff de verdade** para a equipe humana, com fila de atendimento e retorno do protocolo.
- **Observabilidade:** log estruturado das ferramentas chamadas, tempo de resposta e custo por conversa.
- Corrigir os dados com a loja (descrições trocadas, totais de pedidos, divergências do manual).

---

## Uso de assistentes de código

Usei o **Claude Code** (extensão do VS Code) como par de programação durante o desafio. Meu fluxo foi:

1. **Entender o problema:** pedi para o assistente ler o enunciado, o manual de políticas e os CSVs e me trazer um resumo. Ele ajudou a levantar as inconsistências dos dados (descrições trocadas, totais de pedidos que não batem, contradições no manual) e propôs como tratar cada uma no plano.
2. **Planejar antes de codar:** usei o modo de planejamento. Passei as minhas restrições (Python simples, sem framework pesado, prioridade para ferramentas open source ou com free tier, código legível e comentado) e, a partir das opções levantadas, escolhi **Ollama como padrão com Groq como alternativa** e **CLI + Streamlit** como interface. A implementação só começou depois que aprovei o plano.
3. **Implementar em etapas:** o assistente escreveu os rascunhos de cada módulo, um de cada vez (dados → políticas → ferramentas → agente → interfaces → testes), e cada etapa virou um commit, para o histórico mostrar a evolução real do projeto.
4. **Testar com o modelo de verdade e ajustar:** rodando o agente no Ollama apareceram problemas que viraram commits próprios: o `pypdf` quebrando cada palavra numa linha, o PowerShell colocando um BOM na entrada, o contexto padrão de 4096 tokens do Ollama e os erros de resposta descritos em [O que os testes com o modelo mostraram](#o-que-os-testes-com-o-modelo-mostraram). O assistente rodava os roteiros, apontava os erros nas respostas e propunha a correção, de preferência na ferramenta e não só no prompt.
5. **Documentar:** o assistente me ajudou a organizar este README a partir das decisões tomadas ao longo do projeto.

**O que ficou comigo:** as restrições do projeto (simplicidade, open source/free tier, estilo do código), a escolha de provedor e de interface, e a aprovação do plano antes da implementação (que já incluía a persona, o tratamento dos dados e a verificação do pedido por LGPD).
**Onde o assistente mais ajudou:** acelerar a leitura dos materiais, escrever o código e os testes, rodar o agente e investigar os erros que apareceram durante os testes.
