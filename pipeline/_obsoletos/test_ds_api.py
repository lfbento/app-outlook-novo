import os
import time
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

api_key = os.getenv("DEEPSEEK_API_KEY")
client = OpenAI(api_key=api_key, base_url="https://api.deepseek.com")

print("Testando ping basico na API do DeepSeek...")
start = time.time()
try:
    response = client.chat.completions.create(
        model="deepseek-chat",
        messages=[
            {"role": "system", "content": "Voce responde sempre em JSON com a chave 'status' e valor 'ok'."},
            {"role": "user", "content": "Teste de rede, devolva ok"}
        ],
        response_format={'type': 'json_object'},
        timeout=60
    )
    tempo = time.time() - start
    print(f"Sucesso! Tempo de resposta: {tempo:.2f} segundos.")
    print("Corpo da resposta:", response.choices[0].message.content)
except Exception as e:
    tempo = time.time() - start
    print(f"Falha na API apos {tempo:.2f}s! Erro: {str(e)}")
