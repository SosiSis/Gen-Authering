# Troubleshooting Guide

## Quick Diagnostics

### System Health Check

Run the built-in diagnostic script:

```bash
# Run system diagnostics
python scripts/health_check.py

# Check specific components
python scripts/health_check.py --component=llm
python scripts/health_check.py --component=git
python scripts/health_check.py --component=storage
```

### Common Issues & Solutions

## Installation & Setup Issues

### 1. Dependency Installation Failures

**Problem**: `pip install -r requirements.txt` fails

**Symptoms**:
```
ERROR: Could not find a version that satisfies the requirement X
ERROR: No matching distribution found for X
```

**Solutions**:
```bash
# Update pip and setuptools
pip install --upgrade pip setuptools wheel

# Try with different index
pip install -r requirements.txt --index-url https://pypi.org/simple/

# Install specific problematic packages
pip install groq==0.4.0
pip install langgraph==0.1.0

# Use conda if pip fails
conda install -c conda-forge package_name
```

### 2. Environment Configuration Errors

**Problem**: Environment variables not loaded

**Symptoms**:
```
EnvironmentError: Set GROQ_API_KEY env var
ValidationError: Configuration validation failed
```

**Solutions**:
```bash
# Check if .env file exists
ls -la .env

# Copy from template if missing
cp .env.example .env

# Verify environment variables
python -c "from config.environment import get_config; print(get_config().export_config())"

# Load environment manually
source .env  # Linux/Mac
# or
set -a; source .env; set +a  # Linux/Mac with export
```

### 3. Port Binding Issues

**Problem**: Streamlit can't bind to port

**Symptoms**:
```
OSError: [Errno 98] Address already in use
StreamlitAPIException: Port 8501 is already in use
```

**Solutions**:
```bash
# Find process using port
lsof -i :8501
netstat -tulpn | grep :8501

# Kill existing process
kill -9 <PID>

# Use different port
streamlit run streamlit_app.py --server.port=8502

# Set in environment
export PORT=8502
```

## Runtime Issues

### 4. API Key Authentication Failures

**Problem**: Groq API authentication fails

**Symptoms**:
```
groq.AuthenticationError: Invalid API key
Error: Unable to generate response. API Error: 401
```

**Solutions**:
```bash
# Verify API key is set
echo $GROQ_API_KEY

# Test API key manually
curl -H "Authorization: Bearer $GROQ_API_KEY" \
     -H "Content-Type: application/json" \
     -d '{"messages":[{"role":"user","content":"Hello"}],"model":"llama-3.3-70b-versatile"}' \
     https://api.groq.com/openai/v1/chat/completions

# Check for spaces/newlines in key
python -c "import os; print(repr(os.getenv('GROQ_API_KEY')))"

# Regenerate key if needed (visit console.groq.com)
```

### 5. Repository Cloning Failures

**Problem**: Git repository cloning fails

**Symptoms**:
```
GitCommandError: Cmd('git') failed due to: exit code(128)
ValidationError: Only GitHub repositories are allowed
SecurityViolationError: URL contains suspicious pattern
```

**Solutions**:
```bash
# Test git access manually
git clone https://github.com/user/repo.git /tmp/test_clone

# Check URL format
python -c "from utils.validation import validate_github_url; print(validate_github_url('YOUR_URL'))"

# Verify network connectivity
ping github.com
curl -I https://github.com

# Check proxy settings if behind corporate firewall
git config --global http.proxy http://proxy:port
git config --global https.proxy https://proxy:port
```

### 6. Memory and Performance Issues

**Problem**: Application runs out of memory or becomes slow

**Symptoms**:
```
MemoryError: Unable to allocate memory
Process killed (OOM)
Slow response times
```

**Solutions**:
```bash
# Monitor memory usage
htop
docker stats  # if using Docker

# Reduce batch sizes in config
export MAX_FILE_SIZE_MB=25
export LLM_MAX_TOKENS=800

# Increase available memory
# Docker: docker run -m 4g ...
# System: Add swap file or increase RAM

# Enable garbage collection
export PYTHONMALLOC=malloc
```

### 7. File Permission Issues

**Problem**: Cannot read/write files

**Symptoms**:
```
PermissionError: [Errno 13] Permission denied
OSError: [Errno 30] Read-only file system
```

**Solutions**:
```bash
# Check file permissions
ls -la output/ logs/ tmp/

# Fix permissions
chmod 755 output/ logs/ tmp/
chown -R $USER:$USER output/ logs/ tmp/

# For Docker issues
docker run --user $(id -u):$(id -g) ...

# Create directories if missing
mkdir -p output logs tmp data
```

## UI and Interface Issues

### 8. Streamlit Interface Problems

**Problem**: UI not loading or behaving incorrectly

**Symptoms**:
- Blank page or loading forever
- Components not responding
- Session state errors

**Solutions**:
```bash
# Clear Streamlit cache
streamlit cache clear

# Run with debug mode
streamlit run streamlit_app.py --logger.level=debug

# Check browser console for JavaScript errors
# Open Developer Tools (F12) and check Console tab

# Try incognito/private browsing mode

# Update Streamlit
pip install --upgrade streamlit

# Reset session state
# Refresh page or restart app
```

### 9. PDF Generation Failures

**Problem**: PDF creation fails or produces empty files

**Symptoms**:
```
ReportLabError: Unable to create PDF
Empty PDF file generated
Broken PDF formatting
```

**Solutions**:
```bash
# Test PDF library directly
python -c "from tools.pdf_tool import md_to_pdf; md_to_pdf('test.md', 'test.pdf')"

# Check markdown content
cat output/conversation_id.md

# Verify output directory permissions
ls -la output/

# Install additional fonts if needed (Linux)
sudo apt-get install fonts-liberation

# Check for special characters in content
python -c "
content = open('output/file.md', 'r', encoding='utf-8').read()
print([c for c in content if ord(c) > 127])
"
```

### 10. Agent Communication Issues

**Problem**: Agents not communicating properly

**Symptoms**:
- Pipeline stuck at specific stage
- Missing agent responses
- Conversation events empty

**Solutions**:
```bash
# Enable debug logging
export LOG_LEVEL=DEBUG

# Check agent registration
python -c "
from agents.graph_spec import build_graph
coordinator = build_graph()
print(list(coordinator.nodes.keys()))
"

# Test individual agents
python -c "
from agents.nodes import repo_node, create_mcp_message
msg = create_mcp_message('agent', 'RepoNode', {'repo_url': 'https://github.com/test/repo'})
print(repo_node(msg, print))
"

# Check message queue
# Add debug prints to coordinator.run_once()
```

## Network and Connectivity Issues

### 11. API Rate Limiting

**Problem**: API calls being rate limited

**Symptoms**:
```
HTTP 429: Too Many Requests
Rate limit exceeded
Circuit breaker open
```

**Solutions**:
```bash
# Check current rate limits
curl -I https://api.groq.com/openai/v1/models \
  -H "Authorization: Bearer $GROQ_API_KEY"

# Adjust rate limiting configuration
export LLM_RATE_LIMIT_RPM=30
export RATE_LIMIT_PER_HOUR=100

# Implement exponential backoff
# (already built into retry logic)

# Monitor API usage
grep "llm_call" logs/system.log | tail -20
```

### 12. SSL/TLS Certificate Issues

**Problem**: SSL certificate validation fails

**Symptoms**:
```
SSLError: certificate verify failed
requests.exceptions.SSLError
CERTIFICATE_VERIFY_FAILED
```

**Solutions**:
```bash
# Test SSL connectivity
openssl s_client -connect api.groq.com:443

# Update certificates (Ubuntu/Debian)
sudo apt-get update && sudo apt-get install ca-certificates

# For corporate proxies, may need to disable SSL verification (NOT RECOMMENDED)
export CURL_CA_BUNDLE=""
export REQUESTS_CA_BUNDLE=""

# Better: Add corporate certificates to trust store
sudo cp corporate_cert.crt /usr/local/share/ca-certificates/
sudo update-ca-certificates
```

## Docker-Specific Issues

### 13. Docker Build Failures

**Problem**: Docker image build fails

**Symptoms**:
```
ERROR: failed to solve: process "/bin/sh -c pip install -r requirements.txt" did not complete successfully
Docker build context too large
```

**Solutions**:
```bash
# Check .dockerignore exists
ls -la .dockerignore

# Clean Docker cache
docker system prune -a

# Build with no cache
docker build --no-cache -t multiagent-system .

# Check available disk space
df -h

# Use multi-stage build for smaller images
# (see Dockerfile.optimized)
```

### 14. Docker Runtime Issues

**Problem**: Container starts but application fails

**Symptoms**:
```
Container exits immediately
Application not accessible
Health check failing
```

**Solutions**:
```bash
# Check container logs
docker logs multiagent-app

# Run container interactively
docker run -it --entrypoint /bin/bash multiagent-system

# Check port mapping
docker port multiagent-app

# Verify environment variables
docker exec multiagent-app env | grep GROQ

# Test health endpoint
docker exec multiagent-app curl -f http://localhost:8501/health
```

## Production Issues

### 15. Performance Degradation

**Problem**: Application becomes slow in production

**Symptoms**:
- High response times
- Memory leaks
- CPU usage spikes

**Diagnostic Steps**:
```bash
# Monitor system resources
top -p $(pgrep -f streamlit)
iostat -x 1

# Profile Python application
python -m cProfile -o profile.stats streamlit_app.py

# Analyze memory usage
python -m memory_profiler streamlit_app.py

# Check database connections (if applicable)
netstat -an | grep :5432

# Review logs for patterns
grep ERROR logs/system.log | tail -50
```

**Solutions**:
```bash
# Optimize database queries
# Add connection pooling
# Implement caching
# Scale horizontally
# Increase resource limits
```

### 16. High Error Rates

**Problem**: Many requests failing in production

**Symptoms**:
- 5xx HTTP status codes
- Circuit breakers opening
- High error rates in logs

**Diagnostic Steps**:
```bash
# Analyze error patterns
grep ERROR logs/system.log | cut -d' ' -f5- | sort | uniq -c | sort -nr

# Check external service status
curl -I https://api.groq.com/health
ping github.com

# Monitor error rates
tail -f logs/system.log | grep ERROR

# Check resource exhaustion
ulimit -a
free -h
```

## Debugging Tools

### Log Analysis

```bash
# Real-time log monitoring
tail -f logs/system.log | jq .

# Search for specific errors
grep -r "ValidationError" logs/

# Analyze patterns
awk '/ERROR/ {print $1, $5}' logs/system.log | sort | uniq -c

# Generate log summary
python scripts/log_analyzer.py --file=logs/system.log --summary
```

### Configuration Validation

```python
# scripts/validate_config.py
from config.environment import get_config

def validate_configuration():
    """Validate current configuration"""
    try:
        config = get_config()
        print("✅ Configuration loaded successfully")
        
        # Check required settings
        if not config.llm.api_key:
            print("❌ Missing GROQ_API_KEY")
        else:
            print("✅ API key configured")
        
        # Check directories
        for dir_name in [config.data_dir, config.output_dir, config.logs_dir]:
            if os.path.exists(dir_name):
                print(f"✅ Directory exists: {dir_name}")
            else:
                print(f"❌ Directory missing: {dir_name}")
        
        # Test external connectivity
        test_groq_connectivity()
        test_github_connectivity()
        
    except Exception as e:
        print(f"❌ Configuration error: {e}")

if __name__ == "__main__":
    validate_configuration()
```

### Health Monitoring

```python
# scripts/health_monitor.py
import requests
import time
import json

def monitor_health():
    """Continuous health monitoring"""
    while True:
        try:
            # Check main application
            response = requests.get('http://localhost:8501/health', timeout=10)
            
            if response.status_code == 200:
                health_data = response.json()
                print(f"✅ Application healthy: {health_data['status']}")
            else:
                print(f"❌ Application unhealthy: {response.status_code}")
            
            # Check external dependencies
            check_external_services()
            
        except Exception as e:
            print(f"❌ Health check failed: {e}")
        
        time.sleep(30)

def check_external_services():
    """Check external service health"""
    services = {
        'Groq API': 'https://api.groq.com',
        'GitHub': 'https://api.github.com'
    }
    
    for name, url in services.items():
        try:
            response = requests.head(url, timeout=5)
            if response.status_code < 400:
                print(f"✅ {name} accessible")
            else:
                print(f"⚠️ {name} returned {response.status_code}")
        except Exception as e:
            print(f"❌ {name} unavailable: {e}")
```

## Getting Help

### Support Channels

1. **Documentation**: Check the `docs/` directory
2. **GitHub Issues**: Report bugs and request features
3. **Discussions**: General questions and community support
4. **Security Issues**: security@yourcompany.com

### Diagnostic Information to Include

When reporting issues, please include:

```bash
# System information
python --version
pip list | grep -E "(streamlit|groq|langgraph)"
uname -a  # Linux/Mac
systeminfo  # Windows

# Configuration (redact sensitive data)
python -c "from config.environment import get_config; print(get_config().export_config())"

# Recent logs (last 50 lines)
tail -50 logs/system.log

# Error traceback (full stack trace)
```

### Self-Help Resources

- **FAQ**: [docs/FAQ.md](./FAQ.md)
- **Architecture**: [docs/ARCHITECTURE.md](./ARCHITECTURE.md)  
- **API Reference**: [docs/API.md](./API.md)
- **Security Guide**: [docs/SECURITY.md](./SECURITY.md)
- **Deployment Guide**: [docs/DEPLOYMENT.md](./DEPLOYMENT.md)

## Prevention

### Best Practices

1. **Regular Updates**: Keep dependencies and system packages updated
2. **Monitoring**: Implement comprehensive logging and monitoring
3. **Testing**: Run full test suite before deployment
4. **Backups**: Regular backups of configuration and data
5. **Documentation**: Keep documentation updated with changes

### Proactive Monitoring

```bash
# Set up automated monitoring
# Add to crontab:
*/5 * * * * /path/to/scripts/health_monitor.py >> /var/log/health.log 2>&1

# Log rotation
# Add to logrotate.d/multiagent:
/app/logs/*.log {
    daily
    rotate 30
    compress
    delaycompress
    missingok
    notifempty
    create 644 appuser appuser
}
```