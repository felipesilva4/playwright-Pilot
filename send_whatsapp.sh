#!/bin/bash
# Script para enviar mensagem via WhatsApp usando a API

curl -X POST http://localhost:8000/api/whatsapp/send-message \
  -H "Content-Type: application/json" \
  -d '{"message": "Sua mensagem aqui"}'

