# BarkServer (FastAPI server)

## Bark Endpoint
```
curl -X POST https://bark-server-881599834430.us-central1.run.app/bark \
  -H "Content-Type: application/json" \
  -d '{
    "device_id": "test_id1",
    "timestamp": 1751525855,
    "volume": 0.55,
    "frequency": 0.66,
    "event": "8DC5F524-8879-437D-959F-4C7B697..."
  }'
```
