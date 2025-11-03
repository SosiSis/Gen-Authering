# Deployment Guide

## Overview

This guide covers deployment strategies for the Multi-Agent Publication Generator in different environments.

## Environment Setup

### Development Environment

For local development and testing:

```bash
# 1. Clone repository
git clone https://github.com/YourUsername/multiagent-publication-system.git
cd multiagent-publication-system

# 2. Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure environment
cp .env.example .env
# Edit .env with your settings

# 5. Run development server
streamlit run streamlit_app.py
```

### Production Environment

#### Option 1: Direct Deployment

```bash
# 1. Set production environment variables
export ENVIRONMENT=production
export DEBUG=false
export SECRET_KEY="your-secure-secret-key"
export GROQ_API_KEY="your-groq-api-key"

# 2. Install production dependencies
pip install -r requirements.txt

# 3. Run with production settings
streamlit run streamlit_app.py --server.port=8501 --server.address=0.0.0.0
```

#### Option 2: Docker Deployment

Create `Dockerfile`:

```dockerfile
FROM python:3.9-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create necessary directories
RUN mkdir -p logs output tmp data

# Set permissions
RUN chmod +x scripts/*.py

# Expose port
EXPOSE 8501

# Health check
HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
  CMD curl -f http://localhost:8501/health || exit 1

# Run application
CMD ["streamlit", "run", "streamlit_app.py", "--server.port=8501", "--server.address=0.0.0.0"]
```

Build and run:

```bash
# Build image
docker build -t multiagent-system .

# Run container
docker run -d \
  --name multiagent-app \
  -p 8501:8501 \
  --env-file .env \
  -v $(pwd)/logs:/app/logs \
  -v $(pwd)/output:/app/output \
  multiagent-system
```

#### Option 3: Docker Compose

Create `docker-compose.yml`:

```yaml
version: '3.8'

services:
  app:
    build: .
    ports:
      - "8501:8501"
    env_file:
      - .env
    volumes:
      - ./logs:/app/logs
      - ./output:/app/output
      - ./data:/app/data
    restart: unless-stopped
    depends_on:
      - redis
    networks:
      - multiagent-network

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data
    restart: unless-stopped
    networks:
      - multiagent-network

  nginx:
    image: nginx:alpine
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf
      - ./ssl:/etc/nginx/ssl
    depends_on:
      - app
    restart: unless-stopped
    networks:
      - multiagent-network

volumes:
  redis_data:

networks:
  multiagent-network:
    driver: bridge
```

## Cloud Deployment

### AWS Deployment

#### ECS (Elastic Container Service)

1. **Push to ECR:**
```bash
# Build and tag image
docker build -t multiagent-system .
docker tag multiagent-system:latest 123456789012.dkr.ecr.us-west-2.amazonaws.com/multiagent-system:latest

# Push to ECR
aws ecr get-login-password --region us-west-2 | docker login --username AWS --password-stdin 123456789012.dkr.ecr.us-west-2.amazonaws.com
docker push 123456789012.dkr.ecr.us-west-2.amazonaws.com/multiagent-system:latest
```

2. **Create ECS Task Definition:**
```json
{
  "family": "multiagent-system",
  "networkMode": "awsvpc",
  "requiresCompatibilities": ["FARGATE"],
  "cpu": "1024",
  "memory": "2048",
  "executionRoleArn": "arn:aws:iam::123456789012:role/ecsTaskExecutionRole",
  "containerDefinitions": [
    {
      "name": "multiagent-container",
      "image": "123456789012.dkr.ecr.us-west-2.amazonaws.com/multiagent-system:latest",
      "portMappings": [
        {
          "containerPort": 8501,
          "protocol": "tcp"
        }
      ],
      "environment": [
        {
          "name": "ENVIRONMENT",
          "value": "production"
        }
      ],
      "secrets": [
        {
          "name": "GROQ_API_KEY",
          "valueFrom": "arn:aws:secretsmanager:us-west-2:123456789012:secret:multiagent/groq-api-key"
        }
      ],
      "logConfiguration": {
        "logDriver": "awslogs",
        "options": {
          "awslogs-group": "/ecs/multiagent-system",
          "awslogs-region": "us-west-2",
          "awslogs-stream-prefix": "ecs"
        }
      }
    }
  ]
}
```

#### Lambda Deployment

For serverless deployment using AWS Lambda:

```python
# lambda_handler.py
import json
import base64
from io import BytesIO
from agents.graph_spec import build_graph
from agents.nodes import create_mcp_message

def lambda_handler(event, context):
    """AWS Lambda handler for multiagent system"""
    
    try:
        # Parse request
        body = json.loads(event['body'])
        repo_url = body.get('repo_url')
        
        if not repo_url:
            return {
                'statusCode': 400,
                'body': json.dumps({'error': 'repo_url is required'})
            }
        
        # Initialize coordinator
        coordinator = build_graph()
        
        # Process request
        msg = create_mcp_message(
            role="agent",
            name="RepoNode", 
            content={"repo_url": repo_url}
        )
        
        coordinator.send(msg)
        coordinator.run_once()
        coordinator.run_once()
        
        # Get results
        events = coordinator.get_conversation_events(msg["metadata"]["conversation_id"])
        
        return {
            'statusCode': 200,
            'body': json.dumps({
                'conversation_id': msg["metadata"]["conversation_id"],
                'events': events
            })
        }
        
    except Exception as e:
        return {
            'statusCode': 500,
            'body': json.dumps({'error': str(e)})
        }
```

### Google Cloud Platform

#### Cloud Run Deployment

```bash
# Build and deploy to Cloud Run
gcloud run deploy multiagent-system \
  --image gcr.io/PROJECT_ID/multiagent-system \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated \
  --set-env-vars ENVIRONMENT=production \
  --set-secrets GROQ_API_KEY=multiagent-groq-key:latest
```

#### GKE (Google Kubernetes Engine)

Create `k8s-deployment.yaml`:

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: multiagent-system
spec:
  replicas: 3
  selector:
    matchLabels:
      app: multiagent-system
  template:
    metadata:
      labels:
        app: multiagent-system
    spec:
      containers:
      - name: multiagent-container
        image: gcr.io/PROJECT_ID/multiagent-system:latest
        ports:
        - containerPort: 8501
        env:
        - name: ENVIRONMENT
          value: "production"
        - name: GROQ_API_KEY
          valueFrom:
            secretKeyRef:
              name: multiagent-secrets
              key: groq-api-key
        resources:
          requests:
            memory: "1Gi"
            cpu: "500m"
          limits:
            memory: "2Gi"
            cpu: "1000m"
        livenessProbe:
          httpGet:
            path: /health
            port: 8501
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /health
            port: 8501
          initialDelaySeconds: 5
          periodSeconds: 5
---
apiVersion: v1
kind: Service
metadata:
  name: multiagent-service
spec:
  selector:
    app: multiagent-system
  ports:
  - port: 80
    targetPort: 8501
  type: LoadBalancer
```

### Azure Deployment

#### Container Instances

```bash
# Deploy to Azure Container Instances
az container create \
  --resource-group myResourceGroup \
  --name multiagent-system \
  --image myregistry.azurecr.io/multiagent-system:latest \
  --cpu 1 \
  --memory 2 \
  --registry-login-server myregistry.azurecr.io \
  --registry-username myUsername \
  --registry-password myPassword \
  --dns-name-label multiagent-system \
  --ports 8501 \
  --environment-variables ENVIRONMENT=production \
  --secure-environment-variables GROQ_API_KEY=your_api_key
```

## Configuration Management

### Environment-Specific Configurations

#### Development (`.env.development`)
```bash
ENVIRONMENT=development
DEBUG=true
LOG_LEVEL=DEBUG
RATE_LIMIT_PER_HOUR=10000
MAX_FILE_SIZE_MB=100
```

#### Staging (`.env.staging`)
```bash
ENVIRONMENT=staging
DEBUG=false
LOG_LEVEL=INFO
RATE_LIMIT_PER_HOUR=1000
MAX_FILE_SIZE_MB=50
ENABLE_SSL=true
```

#### Production (`.env.production`)
```bash
ENVIRONMENT=production
DEBUG=false
LOG_LEVEL=WARNING
RATE_LIMIT_PER_HOUR=500
MAX_FILE_SIZE_MB=25
ENABLE_SSL=true
ENABLE_AUDIT_LOGGING=true
```

### Secrets Management

#### AWS Secrets Manager
```bash
# Store API key
aws secretsmanager create-secret \
  --name multiagent/groq-api-key \
  --description "Groq API key for multiagent system" \
  --secret-string "your_groq_api_key"
```

#### Azure Key Vault
```bash
# Store API key
az keyvault secret set \
  --vault-name MultiagentKeyVault \
  --name groq-api-key \
  --value "your_groq_api_key"
```

## Monitoring and Logging

### Production Monitoring

#### Health Checks
```python
# Add to streamlit_app.py
@app.route('/health')
def health_check():
    """Health check endpoint for load balancers"""
    try:
        # Check database connection
        # Check external service connectivity
        # Check system resources
        
        return {
            'status': 'healthy',
            'timestamp': datetime.utcnow().isoformat(),
            'version': app_version,
            'components': {
                'database': 'healthy',
                'llm_service': 'healthy',
                'storage': 'healthy'
            }
        }, 200
    except Exception as e:
        return {
            'status': 'unhealthy',
            'error': str(e)
        }, 503
```

#### Logging Configuration
```yaml
# logging.yaml
version: 1
disable_existing_loggers: false

formatters:
  standard:
    format: '%(asctime)s [%(levelname)s] %(name)s: %(message)s'
  json:
    class: pythonjsonlogger.jsonlogger.JsonFormatter
    format: '%(asctime)s %(levelname)s %(name)s %(message)s'

handlers:
  console:
    class: logging.StreamHandler
    level: INFO
    formatter: standard
    stream: ext://sys.stdout
  
  file:
    class: logging.handlers.RotatingFileHandler
    level: INFO
    formatter: json
    filename: logs/app.log
    maxBytes: 10485760  # 10MB
    backupCount: 5
  
  error_file:
    class: logging.handlers.RotatingFileHandler
    level: ERROR
    formatter: json
    filename: logs/error.log
    maxBytes: 10485760
    backupCount: 5

loggers:
  agents:
    level: INFO
    handlers: [console, file]
    propagate: false
  
  tools:
    level: INFO
    handlers: [console, file]
    propagate: false
  
  security:
    level: WARNING
    handlers: [console, file, error_file]
    propagate: false

root:
  level: INFO
  handlers: [console, file]
```

## Security Considerations

### Production Security Checklist

- [ ] **API Keys**: Stored in secure secret management systems
- [ ] **SSL/TLS**: Enabled with valid certificates
- [ ] **Rate Limiting**: Configured for production load
- [ ] **Input Validation**: All inputs validated and sanitized
- [ ] **Audit Logging**: Security events logged and monitored
- [ ] **Access Control**: Proper authentication and authorization
- [ ] **Network Security**: Firewalls and VPC configured
- [ ] **Container Security**: Images scanned for vulnerabilities
- [ ] **Monitoring**: Real-time alerts for security events

### Firewall Rules

```bash
# Allow HTTPS traffic
sudo ufw allow 443/tcp

# Allow Streamlit port (if needed)
sudo ufw allow 8501/tcp

# Allow SSH (be careful with this)
sudo ufw allow 22/tcp

# Enable firewall
sudo ufw enable
```

## Scaling Considerations

### Horizontal Scaling

For high traffic, consider:

1. **Load Balancer**: Distribute requests across multiple instances
2. **Auto Scaling**: Automatically scale based on CPU/memory usage
3. **Database**: Use managed database services for persistence
4. **Caching**: Implement Redis for session and result caching
5. **CDN**: Use CloudFront/CloudFlare for static content

### Performance Optimization

1. **Connection Pooling**: Reuse database and API connections
2. **Async Processing**: Use async/await for I/O operations
3. **Caching**: Cache expensive operations and API responses
4. **Resource Limits**: Set appropriate CPU and memory limits
5. **Monitoring**: Track performance metrics and optimize bottlenecks

## Troubleshooting

### Common Deployment Issues

| Issue | Cause | Solution |
|-------|-------|----------|
| Port binding errors | Port already in use | Use different port or kill existing process |
| Permission denied | Insufficient file permissions | Check file ownership and permissions |
| Memory errors | Insufficient RAM | Increase memory allocation or optimize code |
| SSL certificate errors | Invalid or expired certificates | Renew certificates or update configuration |
| API key errors | Invalid or missing API keys | Verify keys in secrets management |

### Debug Commands

```bash
# Check container logs
docker logs multiagent-app

# Check system resources
docker stats multiagent-app

# Test health endpoint
curl -f http://localhost:8501/health

# Check network connectivity
docker exec -it multiagent-app ping groq.com

# View application logs
tail -f logs/app.log
```

## Maintenance

### Regular Tasks

1. **Update Dependencies**: Regularly update Python packages
2. **Security Patches**: Apply OS and container updates
3. **Log Rotation**: Archive and clean old log files
4. **Certificate Renewal**: Renew SSL certificates before expiration
5. **Backup**: Regular backups of configuration and data
6. **Monitoring**: Review metrics and performance trends

### Backup Strategy

```bash
# Backup configuration
tar -czf backup/config-$(date +%Y%m%d).tar.gz .env* config/

# Backup logs
tar -czf backup/logs-$(date +%Y%m%d).tar.gz logs/

# Backup output files
tar -czf backup/output-$(date +%Y%m%d).tar.gz output/
```