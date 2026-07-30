# Aplicação interativa de Mesa de Operações de Câmbio automatizada.

Este código constrói o protótipo de uma aplicação interativa em Streamlit para simular uma Mesa de Operações de Câmbio automatizada.
O sistema atua como um Operador de Câmbio virtual (Dealer) que negocia taxas de compra e venda de moedas estrangeiras (focado em USD para BRL) com clientes de perfil corporativo ou de alta renda. Para isso, ele combina o consumo de dados macroeconômicos oficiais com inteligência artificial generativa em tempo real.  


------------------------------
## Componentes Principais do Código## 1. Extração  das taxas oficiais de fechamento e abertura do dólar e de outras 8 moedas estrangeiras.

* Captura via API PTAX: As funções get_cotacoes e tratamento_bacen fazem requisições diretamente à API Olinda do BACEN para extrair as taxas oficiais de fechamento e abertura do dólar e de outras 8 moedas estrangeiras.
* Tratamento e Otimização: Filtra duplicatas, padroniza nomes de colunas, injeta metadados de engenharia de dados (como o horário de inserção) e utiliza o decorador @st.cache_data do Streamlit para reter os dados em memória e evitar chamadas excessivas e lentas à API pública.

## 2. Motores de Inteligência Artificial (Vertex AI)
O script expõe duas abordagens distintas utilizando o modelo Gemini 3.5 Flash:

* Busca em Tempo Real (Grounding via Google Search): A função get_current_exchange_rate instrui o modelo a realizar uma pesquisa ativa na internet para retornar a cotação comercial exata do momento. O modelo é forçado através do prompt a agir como um extrator de dados puramente numérico.
* Simulador de Negociação (generate_dealer_response): Atua como o núcleo cognitivo da conversa. O script injeta dinamicamente regras rígidas de negócios e margens financeiras proprietárias (ocultas para o cliente) em um bloco de instruções de contexto.

## 3. Regras de Negócio e Precificação Dinâmica
O robô é programado com parâmetros rígidos para proteger o spread financeiro da instituição:

* Spread Alvo: É calculada uma margem de lucro ideal de 1.5% (BANK_MARGIN) sobre a taxa spot de mercado capturada.
* Preço de Reserva (Hard Limit): Há uma margem mínima aceitável de 0.8% (BANK_MIN_ACCEPTABLE_MARGIN). O modelo é terminantemente proibido pelas instruções internas de aceitar qualquer contraproposta que reduza o lucro abaixo desse piso.
* Análise de Relacionamento: O prompt utiliza a variável CUSTOMER_PROFILE (que classifica o cliente fictício como VIP - High Value) para orientar o tom da argumentação, permitindo que o robô use o prestígio do cliente como justificativa comercial para conceder ou negar descontos.

## 4. Interface de Usuário (Streamlit UI)

* Embora a interface tenha sido cortada no final do código fornecido, as funções estão estruturadas para alimentar um chat interativo em tempo real, sustentando o histórico da conversa e simulando o fluxo de mensagens de uma negociação profissional de balcão de câmbio.

------------------------------
## Permissões IAM Necessárias (Vertex AI)
Para que o arquivo de credenciais informado no código (your-project-service-account-vertexai.json) funcione corretamente executando as chamadas do Gemini, a Conta de Serviço (Service Account) associada precisa possuir os seguintes papéis e permissões no Google Cloud Platform:

* Papel Recomendado: roles/aiplatform.user (Usuário do Vertex AI)
* Permissão crítica: aiplatform.endpoints.predict (Necessária para enviar os payloads de texto e receber as respostas do Gemini).
* Permissão Adicional para Grounding: Como o código faz uso da ferramenta de busca conectada do Google ("tools": [{"google_search": {}}]), certifique-se de que a API do Vertex AI (AI Platform API) esteja devidamente habilitada no console do projeto (PROJECT_ID).

------------------------------
