# Generic Webhook API (Standalone)

API mínima para receber qualquer requisição HTTP, sempre retornar `OK` e salvar o conteúdo em arquivo JSON local.

## Comportamento

- Aceita qualquer rota (`/`, `/projuris`, `/qualquer/coisa`).
- Aceita métodos `GET`, `POST`, `PUT`, `PATCH`, `DELETE`, `OPTIONS`, `HEAD`.
- Sempre responde HTTP `200` com:

```json
{
  "status": "OK",
  "message": "Webhook recebido.",
  "request_id": "..."
}
```

- Cada requisição é salva em `data/requests.json`.

## Como rodar

1. Criar e ativar ambiente virtual (opcional).
2. Instalar dependências:

```bash
pip install -r requirements.txt
```

3. Subir a API:

```bash
python app.py
```

Por padrão, sobe na porta `8080`.
Para mudar:

```bash
PORT=5000 python app.py
```

No PowerShell:

```powershell
$env:PORT="5000"; python app.py
```

## Exemplo de teste (Postman)

- Método: `POST`
- URL: `http://localhost:8080/projuris/evento-x`
- Headers:
  - `Content-Type: application/json`
  - `X_Projuris_Signature: qualquer_valor` (se quiser simular)
- Body:

```json
{
  "contexto": "financeiro",
  "tipo_evento": "titulo_atualizado",
  "id": 123
}
```

Depois confira os dados recebidos em `data/requests.json`.
