import streamlit as st
import pandas as pd
import json
import requests
import time
# Time Ops. libs
from datetime import datetime, timedelta, date
# IO and OS libs
import os, sys, gc, io

from typing import Dict, Any, Union, List
from google.oauth2 import service_account
import vertexai
from vertexai.generative_models import GenerativeModel


# --- CONFIGURAÇÃO DA API GEMINI ---
# NOTA: A chave da API é deixada em branco, assumindo que será fornecida pelo ambiente (Google Cloud).
API_KEY = ""
#MODEL_NAME = "gemini-2.5-flash-preview-09-2025"
PROJECT_ID = "bigdata-staging"
MODEL_NAME = "gemini-2.5-flash"

# Credenciais via JSON
credentials = service_account.Credentials.from_service_account_file( "bigdata-staging-vertexai-d12b90113f4b.json" )


# As margens de lucro são internas ao pipeline e não são visíveis ao cliente.
BANK_MARGIN = 0.015  # 1.5% de margem desejada
BANK_MIN_ACCEPTABLE_MARGIN = 0.008 # 0.8% margem mínima aceitável


# --- DADOS DE CONTEXTO DO CLIENTE (Mock Data) ---
CUSTOMER_PROFILE = {
    "profile_name": "Mr. Gonzalo Ruiz-Oriol",
    "activity_level": "Alto (High)",
    "current_volume_usd": 50000.00,
    "current_commission_tier": "0.15%",
    "relationship_status": "VIP - High Value"
}



# --- FUNÇÕES DE UTENSÍLIO ---

def make_gemini_vertexai_call(payload: Dict[str, Any]) -> Union[str, None]:
    """Handles the API request with exponential backoff."""
    
    # Inicializa Vertex AI
    vertexai.init(
    project=PROJECT_ID,
    location="us-central1",    # ajuste para a região correta
    credentials=credentials
)

    model = GenerativeModel(MODEL_NAME)

    try:
        response = model.generate_content(
            contents=payload['contents'][0]['parts'][0]['text'],
            generation_config={"temperature": 0.1}
        )
        analysis_text = response.text

        print(analysis_text)

        return analysis_text
        
    except Exception as e:
        print(f"FATAL ERROR: {e}")
        return None


def get_cotacoes(data_cotacao, lista_moedas):
    base_url = "https://olinda.bcb.gov.br/olinda/servico/PTAX/versao/v1/odata/CotacaoMoedaDia"
    df_final = pd.DataFrame()

    for moeda in lista_moedas:
        url = f"{base_url}(dataCotacao='{data_cotacao}',moeda='{moeda}')?$format=json"
        
        response = requests.get(url)
        
        if response.status_code == 200:
            data = response.json()
            df = pd.DataFrame(data['value'])
            df['simbolo'] = moeda
            df_final = pd.concat([df_final, df])
        else:
            print(f"Erro ao coletar dados para moeda {moeda} em {data_cotacao}. Status Code: {response.status_code}")

    return df_final


def tratamento_bacen(data_cotacao):
    lista_moedas = ['AUD', 'BRL', 'CAD', 'CHF', 'CNY', 'EUR', 'GBP', 'JPY', 'USD']

    df = get_cotacoes(data_cotacao, lista_moedas)
    if len(df) > 0:

        df = df.drop_duplicates()
        df['dataHoraCotacao'] = pd.to_datetime(df['dataHoraCotacao'])
        df = df[['dataHoraCotacao', 'tipoBoletim', 'simbolo', 'cotacaoVenda', 'cotacaoCompra', 'paridadeVenda', 'paridadeCompra']]
        df = df.rename(columns={
        'dataHoraCotacao': 'data_hora_cotacao',
        'tipoBoletim': 'tipo_boletim',
        'simbolo': 'simbolo',
        'cotacaoVenda': 'cotacao_venda',
        'cotacaoCompra': 'cotacao_compra',
        'paridadeVenda': 'paridade_venda',
        'paridadeCompra': 'paridade_compra'})
        df['engineering_insertion_time'] = datetime.today()
        df = df.loc[df['tipo_boletim'].isin(['Fechamento PTAX', 'Abertura'])]
        df['tipo_boletim'] = df['tipo_boletim'].replace('Fechamento PTAX','Fechamento')
    else:
        print("Sem dados e Sem tratamento")
    
    return df



@st.cache_data
def get_rates():

    data_hoje = datetime.now() - timedelta(days=0)
    data_cotacao = data_hoje.strftime('%m-%d-%Y')

    df = tratamento_bacen(data_cotacao)

    df_currencies  = df.groupby('simbolo').nth(-1)
    column_list = ['Symbol', 'Sell CCY','Buy CCY']
    df_currencies = df_currencies[ ['simbolo','cotacao_venda','cotacao_compra'] ]
    df_currencies.columns = column_list

    return df_currencies 






@st.cache_data
def get_current_exchange_rate(currency="USD to BRL"):
    """
    Usa o Gemini com Grounding (Google Search) para obter a taxa de câmbio atual.
    """
    system_prompt = (
        "Você é um assistente de pesquisa de mercado financeiro. Use o Google Search para encontrar "
        "a taxa de câmbio atual de compra e venda de {currency}. Responda APENAS com um número, "
        "usando ponto decimal (ex: 5.2050), que represente o valor de R$1,00 por US$1,00."
    ).format(currency=currency)

    payload = {
        "contents": [{"parts": [{"text": "Qual a taxa de câmbio atual?"}]}],
        "systemInstruction": {"parts": [{"text": system_prompt}]},
        "tools": [{"google_search": {}}],  # Ativa a pesquisa na web
        "generationConfig": {"temperature": 0.0}
    }

    try:
        #response = requests.post(API_URL, headers={'Content-Type': 'application/json'}, json=payload, timeout=20)
        #response.raise_for_status()
        #result = response.json()
        #text_result = result.get('candidates')[0]['content']['parts'][0]['text'].strip()

        analysis_text = make_gemini_vertexai_call(payload) 

        text_result = analysis_text.strip()

        # Limpar e converter a string (ex: 'R$ 5,20' -> 5.20)
        rate = text_result.replace(',', '.').replace('R$', '').strip()
        return float(rate)
    except Exception as e:
        st.error(f"Erro ao buscar taxa de câmbio: {e}. Usando taxa mock.")
        return 5.25  # Taxa de fallback

def generate_dealer_response(history: List[Dict[str, str]], current_rate: float, user_message: str):
    """
    Gera a resposta do Dealer, incorporando a persona, a taxa de câmbio e a negociação.
    """
    
    # 1. Montar a persona e a instrução complexa
    
    # Contexto da Negociação: Instruções internas para o agente
    negotiation_context = f"""
    --- CONTEXTO DE NEGOCIAÇÃO (INSTRUÇÕES INTERNAS) ---
    - PERSONA: Operador de Câmbio de Alto Nível (Dealer) do Banco.
    - OBJETIVO: Negociar a taxa de câmbio de US$ para BRL, maximizando o lucro do Banco.
    - REGRAS: 
      1. TOME SEMPRE O TOM DE UM EXPERT PROFISSIONAL, EDUCADO E FIRME.
      2. Taxa de Câmbio Spot (Base de Mercado, referencial): R$ {current_rate:.4f} por US$ 1.00.
      3. Margem MÁXIMA que você deve oferecer primeiro (Lucro Ideal): R$ {current_rate * (1 + BANK_MARGIN):.4f}.
      4. Margem MÍNIMA aceitável (Limite de Perda): R$ {current_rate * (1 + BANK_MIN_ACCEPTABLE_MARGIN):.4f}.
      5. Nunca aceite uma taxa abaixo da Margem MÍNIMA.
      6. Use o perfil do cliente ('{CUSTOMER_PROFILE['relationship_status']}') para justificar a oferta, mencionando que já é uma condição especial.
      7. Se o cliente pedir uma taxa muito agressiva, oferte a Margem MÁXIMA e justifique.
      8. Mantenha a conversa focada na negociação de COMPRA ou VENDA (apenas US$).
      9. Inicie sempre a conversa em Inglês.
    --- FIM DAS INSTRUÇÕES ---
    """
    
    # Montar a entrada do usuário incluindo o histórico
    full_prompt = (
        negotiation_context +
        "\n--- HISTÓRICO DA CONVERSA ---\n" + 
        "\n".join([f"{msg['role']}: {msg['content']}" for msg in history]) + 
        f"\nCliente: {user_message}" +
        "\n--- SUA RESPOSTA COMO OPERADOR DE CÂMBIO ---"
    )

    # 2. Montar o payload
    payload = {
        "contents": [{"parts": [{"text": full_prompt}]}],
        "generationConfig": {"temperature": 0.5, "maxOutputTokens": 500}
    }

    # 3. Chamar a API (sem grounding, pois a taxa já foi obtida)
    try:
    #    response = requests.post(API_URL, headers={'Content-Type': 'application/json'}, json=payload, timeout=20)
    #    response.raise_for_status()
    #    result = response.json()
    #    return result.get('candidates')[0]['content']['parts'][0]['text'].strip()


        analysis_text = make_gemini_vertexai_call(payload)

        return analysis_text.strip()

    except Exception as e:
        return f"Desculpe, houve um erro de processamento na nossa central de câmbio. Por favor, tente novamente. (Erro: {e})"




# --- STREAMLIT UI ---

def app():
    st.set_page_config(page_title="Currency Exchange Agent - Dealer", layout="centered")
    st.title("👨‍💼 Digital Currency Exchange Agent")
    st.markdown("Welcome! My name is Gemini, and I am your foreign exchange trader.")

    # Inicialização do estado
    if 'chat_history' not in st.session_state:
        st.session_state.chat_history = []
        st.session_state.market_rate = None

    # Obter a taxa de mercado atual (só na primeira execução)
    if st.session_state.market_rate is None:
        df_dollar = pd.DataFrame()
        df_currencies = get_rates()

        if len(df_currencies) > 0:

            df_dollar['Sell CCY'] = df_currencies.loc[df_currencies['Symbol'] == 'USD','Sell CCY']
            rate=df_dollar['Sell CCY'].tolist()


            st.dataframe(df_currencies, use_container_width=True) 


        with st.spinner("Buscando taxas de mercado..."):
            #st.session_state.market_rate = get_current_exchange_rate()
            st.session_state.market_rate = rate[0]




    current_rate = st.session_state.market_rate

    # Exibir o contexto atual
    st.sidebar.header("Negotiation Context")
    st.sidebar.markdown(f"**Customer:** {CUSTOMER_PROFILE['profile_name']}")
    st.sidebar.markdown(f"**Relationship Status:** {CUSTOMER_PROFILE['relationship_status']}")
    st.sidebar.markdown(f"**Current Rate: (Base US$):** R$ {current_rate:.4f}")
    st.sidebar.markdown(f"*(Maximum bank margin: R$ {current_rate * (1 + BANK_MARGIN):.4f})*")



    # --- 1. Exibir Histórico ---
    chat_display = st.container(height=350)
    for message in st.session_state.chat_history:
        with chat_display:
            st.chat_message(message["role"]).markdown(message["content"])

    # --- 2. Campo de Entrada do Usuário ---
    user_input = st.chat_input("Enter your negotiation proposal...")

    if user_input:
        # Adicionar mensagem do cliente ao histórico
        st.session_state.chat_history.append({"role": "user", "content": user_input})
        
        with chat_display:
            st.chat_message("user").markdown(user_input)

        # Gerar resposta do Dealer
        with st.spinner("Analisando proposta e consultando margens..."):
            dealer_response = generate_dealer_response(
                st.session_state.chat_history, 
                current_rate, 
                user_input
            )

        # Adicionar resposta do Dealer ao histórico
        st.session_state.chat_history.append({"role": "assistant", "content": dealer_response})

        # Reexibir histórico para mostrar a nova resposta
        st.rerun()

if __name__ == "__main__":
    app()


