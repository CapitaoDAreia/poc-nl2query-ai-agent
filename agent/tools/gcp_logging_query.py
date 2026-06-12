from typing import List, Dict, Any, Tuple

def execute_gcp_logging_query(filter_query: str) -> Tuple[List[Dict[str, Any]], str]:
    """
    Simula o comportamento estrito do SDK google-cloud-logging 
    retornando estruturas baseadas em protoPayload (LogEntry padronizado).
    """
    print(f"📥 [Tool -> execute_gcp_logging_query] Executando busca estruturada no protoPayload: '{filter_query}'")
    
    if "protoPayload" not in filter_query:
        return [], "Sintaxe inválida: Queries direcionadas a microsserviços de infraestrutura requerem escopo de protoPayload."

    mock_proto_logs = [
        {
            "insertId": "60bc8ef7000bba1f",
            "logName": "projects/contabilizei-prod/logs/cloudaudit.googleapis.com%2Factivity",
            "resource": {
                "type": "cloud_run_revision",
                "labels": {
                    "configuration_name": "plataforma-web",
                    "location": "southamerica-east1"
                }
            },
            "protoPayload": {
                "@type": "[type.googleapis.com/google.cloud.audit.AuditLog](https://type.googleapis.com/google.cloud.audit.AuditLog)",
                "status": {
                    "code": 560,
                    "message": "FAILED_PRECONDITION: Downstream timeout from ImpostosService"
                },
                "authenticationInfo": {"principalEmail": "gateway-router@contabilizei.iam.gserviceaccount.com"},
                "resourceName": "/impostos/v4/impostos-a-pagar/init",
                "methodName": "GET"
            },
            "severity": "ERROR",
            "timestamp": "2026-06-11T22:15:00.124Z"
        },
        {
            "insertId": "60bc8ef7000bba20",
            "logName": "projects/contabilizei-prod/logs/cloudaudit.googleapis.com%2Factivity",
            "resource": {
                "type": "cloud_run_revision",
                "labels": {
                    "configuration_name": "plataforma-web",
                    "location": "southamerica-east1"
                }
            },
            "protoPayload": {
                "@type": "[type.googleapis.com/google.cloud.audit.AuditLog](https://type.googleapis.com/google.cloud.audit.AuditLog)",
                "status": {
                    "code": 560,
                    "message": "FAILED_PRECONDITION: HTTP 560 Bad Request from SaudeEmpresaService"
                },
                "authenticationInfo": {"principalEmail": "gateway-router@contabilizei.iam.gserviceaccount.com"},
                "resourceName": "/impostos/v4/impostos-a-pagar/init",
                "methodName": "GET"
            },
            "severity": "ERROR",
            "timestamp": "2026-06-11T22:16:30.881Z"
        }
    ]
    
    return mock_proto_logs, ""