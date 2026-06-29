"""Deploy agent — infrastructure design → deployment artifacts.

Generates infrastructure-as-code and container configs. The artifacts are
produced deterministically from the design (in both mock and live modes the
shape is identical) so the UI always has something concrete to render and the
output stays valid IaC rather than free-form LLM text.
"""
from __future__ import annotations

from typing import Any

from agent.state import GraphState

_DOCKER_COMPOSE = """\
services:
  backend:
    build: ./backend
    ports:
      - "8000:8000"
    env_file:
      - .env
    depends_on:
      - postgres
      - redis

  frontend:
    build: ./frontend
    ports:
      - "3000:3000"
    environment:
      - NEXT_PUBLIC_API_BASE=http://localhost:8000

  postgres:
    image: postgres:16-alpine
    environment:
      POSTGRES_USER: user
      POSTGRES_PASSWORD: password
      POSTGRES_DB: agent_infra
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"

volumes:
  postgres_data:
"""

_DOCKERFILE_BACKEND = """\
FROM python:3.12-slim
WORKDIR /app
COPY pyproject.toml ./
RUN pip install --no-cache-dir -e .
COPY . .
EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
"""


def _terraform(infra: dict[str, Any], spec: dict[str, Any]) -> str:
    tier = infra.get("tier", "balanced")
    task_count = 1 if tier == "cost-optimized" else 2
    instance = "db.t4g.micro" if tier == "cost-optimized" else "db.t4g.medium"
    return f"""\
terraform {{
  required_providers {{
    aws = {{ source = "hashicorp/aws", version = "~> 5.0" }}
  }}
}}

provider "aws" {{
  region = "us-east-1"
}}

# Backend service ({spec.get('application_type', 'app')})
resource "aws_ecs_cluster" "main" {{
  name = "agent-infra-cluster"
}}

resource "aws_ecs_service" "backend" {{
  name            = "backend"
  cluster         = aws_ecs_cluster.main.id
  desired_count   = {task_count}
  launch_type     = "FARGATE"
}}

resource "aws_db_instance" "postgres" {{
  engine            = "postgres"
  engine_version    = "16"
  instance_class    = "{instance}"
  allocated_storage = 20
  multi_az          = {str(tier != 'cost-optimized').lower()}
}}

resource "aws_elasticache_cluster" "redis" {{
  cluster_id      = "agent-infra-redis"
  engine          = "redis"
  node_type       = "cache.t4g.micro"
  num_cache_nodes = 1
}}
"""


def _k8s(infra: dict[str, Any]) -> str:
    replicas = 1 if infra.get("tier") == "cost-optimized" else 2
    return f"""\
apiVersion: apps/v1
kind: Deployment
metadata:
  name: backend
spec:
  replicas: {replicas}
  selector:
    matchLabels:
      app: backend
  template:
    metadata:
      labels:
        app: backend
    spec:
      containers:
        - name: backend
          image: agent-infra/backend:latest
          ports:
            - containerPort: 8000
---
apiVersion: v1
kind: Service
metadata:
  name: backend
spec:
  selector:
    app: backend
  ports:
    - port: 80
      targetPort: 8000
"""


def deploy_node(state: GraphState) -> dict[str, Any]:
    infra = state["infrastructure"]
    spec = state.get("requirements", {})
    artifacts = {
        "docker_compose": _DOCKER_COMPOSE,
        "dockerfile_backend": _DOCKERFILE_BACKEND,
        "terraform": _terraform(infra, spec),
        "k8s_manifest": _k8s(infra),
    }
    deployment = {
        "artifacts": artifacts,
        "notes": "Generated Docker Compose, backend Dockerfile, Terraform (AWS ECS/RDS/"
        "ElastiCache), and Kubernetes manifests from the approved design.",
    }
    return {"deployment": deployment, "steps": [{"agent": "deploy", "output": deployment}]}
