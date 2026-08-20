import os
import time
import json
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

api_key = os.getenv("DEEPSEEK_API_KEY")
client = OpenAI(api_key=api_key, base_url="https://api.deepseek.com")

prompt = """
Extraia entidades deste texto: "O engenheiro Luis enviou o cronograma do tanque TQ-9050 para a Indorama."
Retorne em JSON com keys 'nodes' e 'edges'.
"""

print("Testando prompt de extracao real no DeepSeek...")
start = time.time()
try:
    response = client.chat.completions.create(
        model="deepseek-chat",
        messages=[
            {"role": "system", "content": "Voce e um extrator de grafos."},
            {"role": "user", "content": prompt}
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
