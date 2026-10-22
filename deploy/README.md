# deploy

Infraestructura en Azure de tacticAI. Esta carpeta va a contener la infraestructura como código (Bicep + `azd`) y la configuración de despliegue. Por ahora documenta la arquitectura planeada; nada de esto está desplegado todavía.

## Arquitectura planeada: generador de partidos en Internet

```
 Usuario / UI ──► API (Container App) ──► Cola (Service Bus) ──► Job generador (Container Apps Job)
                     │                                             │  imagen tai-engine
                     │                                             ▼
                     └──── estado (Cosmos DB) ◄──────────── Blob Storage
                                                             video.mp4 · tracking · events · meta
```

| Pieza | Servicio Azure | Para qué |
|---|---|---|
| Registro de imágenes | Azure Container Registry | Guarda la imagen `tai-engine` y nuestro código |
| Generador | Azure Container Apps Jobs (disparados por eventos) | Un contenedor por partido; escala a cero cuando nadie genera |
| Cola de pedidos | Azure Service Bus | La API encola y el job consume (escalado con KEDA) |
| API | Azure Container Apps | `POST /matches` para pedir un partido y `GET /matches/{id}` para el estado y los links |
| Resultados | Azure Blob Storage | Videos y JSON, servidos con links temporales (SAS) |
| Estado de pedidos | Azure Cosmos DB | Pendiente → generando → listo, con semilla y parámetros |
| Secretos e identidad | Managed Identity + Key Vault | Sin claves en el código |
| Observabilidad | Application Insights / Log Analytics | Logs, duración por partido, errores |

Un partido completo tarda unos 11 minutos con render por software. Por eso el plan combina dos cosas: una biblioteca de partidos pre-generados y situaciones cortas a pedido, de 1 a 2 minutos de render.

## Próximas capas (pendiente de definir)

- **Capa agéntica:** un agente en Microsoft Foundry traduce un pedido por voz o texto a una especificación de escenario y llama a la API como herramienta (OpenAPI o MCP).
- **Modo en vivo:** se reproduce `events.jsonl` al ritmo del reloj del partido vía Event Hubs o Web PubSub.
- **Interfaz gráfica:** Azure Static Web Apps.
