# Test end-to-end — Módulo Agendatorio

Todos los comandos se ejecutan desde la **raíz** del proyecto (`BIGA/`).

---

## Paso 1 — Levantar el stack

```bash
docker compose up -d
```

`storage-init` crea el bucket automáticamente. Esperar a que todos los servicios estén `Up`.

---

## Paso 2 — Seed: estudiante y acudiente

```bash
docker compose exec api python -m scripts.seed_agendatorio
```

Anota el `student_id` que imprime — lo necesitas en el paso 7.

---

## Paso 3 — Login

```bash
TOKEN=$(curl -s -X POST http://localhost:8000/auth/login -H "Content-Type: application/x-www-form-urlencoded" -d "username=demo@biga.app&password=Test1234!" | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")
```

---

## Paso 4 — Crear artículo del manual

```bash
curl -s -X POST http://localhost:8000/agendatorio/articles -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" -d '{"code":"Art.15","title":"Uso inadecuado del celular","description":"Prohibido el uso de celular en clase","severity":"LEVE"}' | python3 -m json.tool
```

---

## Paso 5 — Guardar IDs en variables

```bash
ARTICLE_ID=$(curl -s http://localhost:8000/agendatorio/articles -H "Authorization: Bearer $TOKEN" | python3 -c "import sys,json; print(json.load(sys.stdin)[0]['id'])")
```

Copia el `student_id` que imprimió el paso 2 directamente:
```bash
STUDENT_ID=<pega-el-uuid-aqui>
```

---

## Paso 6 — PNG de firma de prueba

```bash
python3 -c "import base64; open('/tmp/firma.png','wb').write(base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=='))"
```

---

## Paso 7 — Crear registro disciplinario

```bash
curl -s -X POST http://localhost:8000/agendatorio/records -H "Authorization: Bearer $TOKEN" -F "data={\"student_id\":\"$STUDENT_ID\",\"article_ids\":[\"$ARTICLE_ID\"],\"observations\":\"Uso del celular durante evaluacion\",\"date\":\"2026-05-21\"}" -F "signature=@/tmp/firma.png;type=image/png" | python3 -m json.tool
```

---

## Paso 8 — Listar registros del estudiante

```bash
curl -s "http://localhost:8000/agendatorio/records?student_id=$STUDENT_ID" -H "Authorization: Bearer $TOKEN" | python3 -m json.tool
```

---

## Paso 9 — Ver detalle con URL presignada de la firma

```bash
RECORD_ID=$(curl -s "http://localhost:8000/agendatorio/records?student_id=$STUDENT_ID" -H "Authorization: Bearer $TOKEN" | python3 -c "import sys,json; print(json.load(sys.stdin)[0]['id'])")
```

```bash
curl -s "http://localhost:8000/agendatorio/records/$RECORD_ID" -H "Authorization: Bearer $TOKEN" | python3 -m json.tool
```

---

## Paso 10 — Errores esperados

**Artículo duplicado → 409:**
```bash
curl -s -X POST http://localhost:8000/agendatorio/articles -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" -d '{"code":"Art.15","title":"Duplicado","description":"test","severity":"LEVE"}' | python3 -m json.tool
```

**Artículo inexistente → 400:**
```bash
curl -s -X POST http://localhost:8000/agendatorio/records -H "Authorization: Bearer $TOKEN" -F "data={\"student_id\":\"$STUDENT_ID\",\"article_ids\":[\"00000000-0000-0000-0000-000000000000\"],\"observations\":\"test\",\"date\":\"2026-05-21\"}" -F "signature=@/tmp/firma.png;type=image/png" | python3 -m json.tool
```

**Sin token → 401:**
```bash
curl -s http://localhost:8000/agendatorio/articles | python3 -m json.tool
```
